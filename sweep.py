#!/usr/bin/env python3
"""
sweep.py — 本走行の掃引ドライバ

64 セル × 40 シード = 2,560 走行を、中断に耐える形で回す。
★ abm/ を一切変更しない。run_longitudinal を呼ぶ側だけのスクリプト。

使い方
  python sweep.py --config config/sweep_main.json --dry-run
  python sweep.py --config config/sweep_main.json --calibrate 8
  python sweep.py --config config/sweep_main.json

出所
  格子      決定台帳 T-030（f 0〜0.5 の 8 点）／T-044（等間隔）／
            試験 1-10（θ′ 4 点）／U-008（罰の射程 実質 2 点）／T-043（λ_mix は軸でない）
  T         決定台帳 T-010（T ≈ 1,740）
  シード     決定台帳 T-016（40）／依頼L §7-2（ΔAUC は 40 で足りる）
"""
from __future__ import annotations

import argparse
import json
import math
import os
import shutil
import subprocess
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from abm.domains import AgentConfig, AgentState, CorrectionMode, RepairScope
from abm.ledger import Ledger, RunHeader
from abm.loop import run_longitudinal
from abm.seed import load_seed
from abm.world import generate_world


# --------------------------------------------------------------------------
# f は f(agent_id, t) の署名を保つ（★ 将来の非一様 f のため。クロージャは pickle できない）
# --------------------------------------------------------------------------
class UniformF:
    def __init__(self, value: float) -> None:
        self.value = float(value)

    def __call__(self, agent_id: str, t: int) -> float:
        return self.value


# --------------------------------------------------------------------------
def code_commit() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True,
            stderr=subprocess.DEVNULL).strip()
    except Exception:
        return "unknown"


def cell_name(f_value: float, theta: float, scope: str,
              verbatim_theta: float | None = None) -> str:
    base = f"f{f_value:.4f}_th{theta:.4f}"
    if verbatim_theta is not None and verbatim_theta != theta:
        base += f"_vt{verbatim_theta:.4f}"
    return f"{base}_{scope}"


def parse_cell_name(name: str) -> dict:
    parts = name.split("_")
    f_part, th_part, rest = parts[0], parts[1], parts[2:]
    verbatim = None
    if rest and rest[0].startswith("vt"):
        verbatim = float(rest[0][2:])
        rest = rest[1:]
    return {"f": float(f_part[1:]), "theta_prime": float(th_part[2:]),
            "repair_scope": "_".join(rest), "verbatim_theta": verbatim}


def enumerate_runs(cfg: dict) -> list[dict]:
    ax = cfg["axes"]
    seeds = cfg["seeds"]
    out = []
    for scope in ax["repair_scope"]:
        for theta in ax["theta_prime"]:
            for f_value in ax["f"]:
                for verbatim in ax.get("verbatim_theta", [None]):
                    cell = cell_name(f_value, theta, scope, verbatim)
                    for i in range(seeds["count"]):
                        out.append({"cell": cell, "f": f_value, "theta_prime": theta,
                                    "repair_scope": scope, "verbatim_theta": verbatim,
                                    "seed": seeds["start"] + i})
    # ★ 割り当ての順序を決定的にする（並列で完了する順序は変わってよい）
    out.sort(key=lambda r: (r["cell"], r["seed"]))
    return out


# --------------------------------------------------------------------------
def run_one(task: dict) -> dict:
    """一走行を最後まで実行して .done を書く。★ 引数は基本型だけ（pickle のため）"""
    cfg = task["cfg"]
    out_dir = Path(cfg["output"]["dir"]) / "cells" / task["cell"]
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = f"seed{task['seed']:03d}"
    compress = bool(cfg["output"].get("compress", True))
    ledger_path = out_dir / (stem + (".jsonl.gz" if compress else ".jsonl"))
    done_path = out_dir / (stem + ".done")

    if done_path.exists():
        return {"cell": task["cell"], "seed": task["seed"], "skipped": True}

    # ★ .done が無いのに台帳が残っていたら未完了。消してから走り直す
    #   （Ledger は open("x") で新規作成しかしないため）
    if ledger_path.exists():
        ledger_path.unlink()

    fixed = cfg["fixed"]
    seed = load_seed()
    world = generate_world(task["seed"], cfg["trial_count"], tuple(cfg["agent_ids"]), seed=seed)

    header = RunHeader(
        arm_alpha=fixed["alpha"], arm_beta=fixed["beta"], arm_w=fixed["w"],
        arm_kappa=fixed["kappa"], arm_repair_scope=task["repair_scope"],
        arm_verbatim_theta=task["verbatim_theta"],
        arm_holdout_repr=fixed.get("holdout_repr", "first_order_binary"),
        arm_f_profile=f"uniform:{task['f']:.6f}",
        arm_lambda_mix=fixed["lambda_mix"],
        arm_abstain_charge=fixed["abstain_charge"],
        arm_temperature=fixed.get("temperature"), arm_d_shared=fixed.get("d_shared"),
        arm_adaptation_table=fixed.get("adaptation_table"),
        run_seed=task["seed"], trial_count=cfg["trial_count"],
        agent_ids=tuple(cfg["agent_ids"]),
        seed_file_sha256=getattr(seed, "file_sha256", None) or task["seed_file_sha256"],
        world_hash=world.world_hash, code_commit=task["code_commit"],
        theta_prime=task["theta_prime"], tau_acc=fixed["tau_acc"],
        f_setting=task["f"],
    )

    states = {a: AgentState() for a in cfg["agent_ids"]}
    configs = {a: AgentConfig(
        fixed["threshold"], CorrectionMode(fixed["correction_mode"]),
        theta_prime=task["theta_prime"], tau_acc=fixed["tau_acc"],
        verbatim_theta=task["verbatim_theta"],
        nsim_threshold=fixed["nsim_threshold"],
        alpha=fixed["alpha"], beta=fixed["beta"], w=fixed["w"], kappa=fixed["kappa"],
        lambda_mix=fixed["lambda_mix"], abstain_charge=fixed["abstain_charge"],
        repair_scope=RepairScope(task["repair_scope"]),
        pending_claims=fixed.get("pending_claims", False),
        pending_gamma=fixed.get("pending_gamma", 0.0),
        pending_hold_cost=fixed.get("pending_hold_cost", 0.0),
    ) for a in cfg["agent_ids"]}

    t0 = time.time()
    with Ledger(ledger_path, header, compress=compress) as ledger:
        result = run_longitudinal(
            world, states, configs, ledger,
            frequency=UniformF(task["f"]),
            snapshot_mode=cfg["output"].get("snapshot_mode", "delta"),
            snapshot_every=int(cfg["output"].get("snapshot_every", 1)),
        )
    elapsed = time.time() - t0

    st = result.states[cfg["agent_ids"][0]]
    record = {
        "cell": task["cell"], "seed": task["seed"],
        "f": task["f"], "theta_prime": task["theta_prime"],
        "verbatim_theta": task["verbatim_theta"],
        "repair_scope": task["repair_scope"],
        "world_hash": result.world_hash, "trial_count": result.trial_count,
        "code_commit": task["code_commit"],
        "seed_file_sha256": header.seed_file_sha256,
        "snapshot_mode": cfg["output"].get("snapshot_mode", "delta"),
        "snapshot_every": int(cfg["output"].get("snapshot_every", 1)),
        "ledger_bytes": ledger_path.stat().st_size,
        "elapsed_sec": round(elapsed, 2),
        "final_def_count": len(st.definitions),
        "final_m_live_total": sum(d.m_live for d in st.definitions.values()),
        "finished_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    # ★ 台帳を閉じた後に .done を書く。これが完了の唯一の印
    done_path.write_text(json.dumps(record, ensure_ascii=False) + "\n", encoding="utf-8")
    return {**record, "skipped": False}


# --------------------------------------------------------------------------
def validate(cfg: dict) -> None:
    ax = cfg["axes"]
    for key in ("f", "theta_prime", "repair_scope"):
        if not ax.get(key):
            raise SystemExit(f"★ 設定の axes.{key} が空です")
    if "verbatim_theta" in ax:
        invalid = [value for value in ax["verbatim_theta"]
                   if isinstance(value, bool) or not isinstance(value, (int, float))
                   or not math.isfinite(value) or value <= 0]
        if invalid:
            raise SystemExit(f"★ axes.verbatim_theta は0より大きい有限の実数にしてください: {invalid}")
    for scope in ax["repair_scope"]:
        try:
            RepairScope(scope)
        except ValueError:
            raise SystemExit(f"★ 未知の repair_scope: {scope}")
    if cfg["seeds"]["count"] < 1 or cfg["trial_count"] < 1:
        raise SystemExit("★ seeds.count と trial_count は 1 以上")
    try:
        CorrectionMode(cfg["fixed"]["correction_mode"])
    except ValueError:
        raise SystemExit(f"★ 未知の correction_mode: {cfg['fixed']['correction_mode']}")
    known = set(AgentConfig.__dataclass_fields__)
    unknown = sorted(set(cfg["fixed"]) - known - {"holdout_repr", "temperature",
                                                  "d_shared", "adaptation_table"})
    if unknown:
        raise SystemExit(f"★ fixed に AgentConfig に無いキー: {unknown}")
    mode = cfg["output"].get("snapshot_mode", "delta")
    if mode != "delta" and int(cfg["output"].get("snapshot_every", 1)) != 1:
        raise SystemExit("★ snapshot_every は snapshot_mode='delta' のときだけ 1 以外にできます")


def done_count(cfg: dict, runs: list[dict]) -> int:
    base = Path(cfg["output"]["dir"]) / "cells"
    return sum(1 for r in runs
               if (base / r["cell"] / f"seed{r['seed']:03d}.done").exists())


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--workers", type=int, default=None)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--cells", default=None, help="セル名をカンマ区切りで")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--calibrate", type=int, default=0)
    ap.add_argument("--no-resume", action="store_true")
    ap.add_argument("--trial-count", type=int, default=None)
    args = ap.parse_args()

    cfg = json.loads(Path(args.config).read_text(encoding="utf-8"))
    if args.trial_count:
        cfg["trial_count"] = args.trial_count
    validate(cfg)

    runs = enumerate_runs(cfg)
    if args.cells:
        wanted = set(args.cells.split(","))
        runs = [r for r in runs if r["cell"] in wanted]
    if args.limit:
        runs = runs[:args.limit]

    workers = args.workers or max(1, (os.cpu_count() or 2) - 2)
    commit = code_commit()
    import hashlib
    seed_sha = hashlib.sha256((ROOT / "U-011_seed_v1.json").read_bytes()).hexdigest()

    out_root = Path(cfg["output"]["dir"])
    if args.calibrate:
        out_root = out_root / "_calibration"
        cfg = json.loads(json.dumps(cfg))
        cfg["output"]["dir"] = str(out_root)
        cfg["trial_count"] = args.trial_count or 200
        runs = runs[:args.calibrate]

    print(f"設定        {args.config}")
    print(f"格子        f {len(cfg['axes']['f'])}点 × θ′ {len(cfg['axes']['theta_prime'])}点"
          f" × 射程 {len(cfg['axes']['repair_scope'])}点"
          f" = {len(cfg['axes']['f'])*len(cfg['axes']['theta_prime'])*len(cfg['axes']['repair_scope'])} セル")
    print(f"シード      {cfg['seeds']['start']}〜{cfg['seeds']['start']+cfg['seeds']['count']-1}"
          f"（{cfg['seeds']['count']} 本）")
    print(f"T           {cfg['trial_count']}")
    print(f"走行数      {len(runs)}")
    print(f"並列        {workers}（cpu_count = {os.cpu_count()}）")
    print(f"出力        {out_root}")
    print(f"snapshot    {cfg['output'].get('snapshot_mode','delta')}"
          f" / every {cfg['output'].get('snapshot_every',1)}"
          f" / compress {cfg['output'].get('compress',True)}")
    print(f"コミット     {commit[:12]}")
    print(f"種          {seed_sha[:16]}…")
    free = shutil.disk_usage(".").free
    print(f"空き容量     {free/1e9:.1f} GB")

    if args.dry_run:
        print("\n--dry-run。最初の 5 走行:")
        for r in runs[:5]:
            print(f"  {r['cell']}  seed{r['seed']:03d}")
        return

    out_root.mkdir(parents=True, exist_ok=True)
    (out_root / "sweep_config.json").write_text(
        json.dumps({"config": cfg, "workers": workers, "code_commit": commit,
                    "seed_file_sha256": seed_sha,
                    "started_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")},
                   ensure_ascii=False, indent=2), encoding="utf-8")

    if not args.no_resume:
        already = done_count(cfg, runs)
        if already:
            print(f"\n再開：完了済み {already}/{len(runs)} を飛ばします")

    tasks = [{**r, "cfg": cfg, "code_commit": commit, "seed_file_sha256": seed_sha}
             for r in runs]

    # ---- 較正モード ----
    if args.calibrate:
        print(f"\n=== 較正（T={cfg['trial_count']} × {len(tasks)} 走行）===")
        t0 = time.time()
        for t in tasks:
            run_one(t)
        seq = time.time() - t0
        shutil.rmtree(out_root / "cells", ignore_errors=True)
        t0 = time.time()
        with ProcessPoolExecutor(max_workers=workers) as ex:
            list(ex.map(run_one, tasks))
        par = time.time() - t0
        sizes = [p.stat().st_size for p in (out_root / "cells").rglob("*.jsonl*")]
        avg = sum(sizes) / max(len(sizes), 1)
        eff = seq / par if par else 0.0
        full_runs = (len(cfg["axes"]["f"]) * len(cfg["axes"]["theta_prime"])
                     * len(cfg["axes"]["repair_scope"]) * cfg["seeds"]["count"])
        scale = (1740 / cfg["trial_count"]) ** 1.63          # 走行時間の伸び（実測）
        size_scale = (1740 / cfg["trial_count"]) ** 1.85     # 台帳の伸び（実測）
        per = seq / len(tasks) * scale
        print(f"\n  逐次 {seq:.1f} 秒 / {len(tasks)} 走行 = {seq/len(tasks):.1f} 秒")
        print(f"  {workers} 並列 {par:.1f} 秒 → ★ 実効並列度 {eff:.2f}")
        print(f"  1 走行の台帳 {avg/1e6:.2f} MB")
        print(f"\n  ★ 本走行への外挿（T=1,740 × {full_runs} 走行）")
        print(f"    1 走行     {per:.0f} 秒")
        print(f"    総時間     {per*full_runs/max(eff,1e-9)/3600:.1f} 時間")
        print(f"    総容量     {avg*size_scale*full_runs/1e9:.0f} GB")
        print(f"    空き容量   {free/1e9:.0f} GB")
        (out_root / "calibration.json").write_text(json.dumps({
            "sequential_sec": seq, "parallel_sec": par, "workers": workers,
            "effective_parallelism": eff, "avg_ledger_bytes": avg,
            "calibration_trial_count": cfg["trial_count"], "n_runs": len(tasks),
            "extrapolated": {"per_run_sec": per, "total_hours": per*full_runs/max(eff,1e-9)/3600,
                             "total_bytes": avg*size_scale*full_runs},
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\n  → {out_root/'calibration.json'}")
        return

    # ---- 本走行 ----
    manifest = out_root / "manifest.jsonl"
    print(f"\n=== 走行開始 {datetime.now().strftime('%H:%M:%S')} ===")
    t0 = time.time()
    done = skipped = 0
    with ProcessPoolExecutor(max_workers=workers) as ex:
        futures = {ex.submit(run_one, t): t for t in tasks}
        for fut in as_completed(futures):
            try:
                rec = fut.result()
            except Exception as exc:                      # 一走行の失敗で全体を止めない
                t = futures[fut]
                print(f"  ★ 失敗 {t['cell']} seed{t['seed']:03d}: {exc}")
                continue
            if rec.get("skipped"):
                skipped += 1
                continue
            done += 1
            with manifest.open("a", encoding="utf-8") as fh:   # ★ 親だけが追記する
                fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
            n = done + skipped
            el = time.time() - t0
            eta = el / max(done, 1) * (len(tasks) - n)
            print(f"  [{n:>5}/{len(tasks)}] {rec['cell']} seed{rec['seed']:03d}  "
                  f"{rec['elapsed_sec']:>6.1f}秒  {rec['ledger_bytes']/1e6:>6.1f}MB  "
                  f"def {rec['final_def_count']:>3}  残り {eta/3600:>5.1f}h", flush=True)
    el = time.time() - t0
    print(f"\n=== 完了 {done} 走行 / 飛ばし {skipped} / {el/3600:.2f} 時間 ===")
    print(f"  {out_root}")


if __name__ == "__main__":
    main()

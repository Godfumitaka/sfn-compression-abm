"""仕組みの表（受け箱の指示 11）。成績の表とは別に、一本ごとの記録から仕組みの数を出す（読むだけ。模型は走らせない）。

使い方：
  nice -n 15 ionice -c3 python3.12 ~/surface/mechanism.py [--jobs 4] [--redo]
      configs.json の群（成績を保留した群 results_hold も含む）の、完了の印がある本を読み、~/surface/out/ に書く：
        mechanism_<構成>.csv             一本ごと（世界・種）の M1〜M6
        mechanism_trajectory_<構成>.csv  一本ごと・100 試行ごとの定義の数など（M1 の推移、M3 の区間ごとの数）
  python3.12 ~/surface/mechanism.py --run <本の出力先> --config 名 --world W --seed S [--time-log PATH] --out DIR
      完了の印の無い本（走っている本・途中で止めた本）を、読める所まで読んで試す（書きかけの末尾は読まない）。
  種 21〜40 は読まない。

数え方と出どころ（新しい版 e9ed84a の出力の形。control/2026-10-08_合わせた版の記憶が空になる診断_Codex2.md と同じ欄）：
  M1 定義の数：side の jsonl の kind=v39 の defs（その試行の学習・忘却の後）。100 試行ごとの区間の最後の試行の値
     （試行番号は 0 始まり。区間 1 の最後は試行 99）。試行 200 以降（試行番号 200〜最後）で defs が 1 以下の試行の割合。
  M2 Δr：第二段の本流 stage2/<セル>/seedNNN.jsonl.gz の、開示の試行（f_fired が真、reason=evaluated）の rows の各席の delta
     （照合し直した Δr）が 0・負・正の数と割合。分母は測った席。測る席が無い開示の試行は別に数える（0 に混ぜない）。
  M3 誕生・退役：誕生＝side の jsonl の kind=birth の行の数（同化 kind=assim は別の欄）。退役＝kind=v39 の retire に並ぶ定義の数。
     確かめ：誕生−退役＝最後の試行の defs。
  M4 同じ試行で同じ定義の二つ以上の席が薄くなった件数：kind=v39 の conv（実行された F→H・H→U、[種類, R, 席, V, 解放量, 理由, 同点数]）を
     (試行, R) でまとめ、違う席が二つ以上ある組の数（と、その組の席の数）。
  M5 実時間・最大常駐：実時間は manifest.jsonl の elapsed_sec。最大常駐は、/usr/bin/time -v の記録（configs.json の time_log、
     Maximum resident set size）があればそれ、無ければ manifest.jsonl の peak_rss_mb（tools/v3_run.py が Linux の ru_maxrss〈KiB〉を
     1e6 で割った値。×1e6 KiB に直して GiB で出す。0.1 刻みなので約 0.1GB の粗さ）。
  M6 第二段の価値（V）が正の席の割合：researcher/<セル>/seedNNN.calibration.jsonl.gz（忘却の実行を止めた較正の本だけにある）の
     candidates の V（reference が偽の席＝本番の候補関数の値）の符号。本番の本にはこの記録が無いので NA（報告の問いを見る）。
     参考：stage2 の .initial.jsonl.gz（出生の仮の問い）の delta_by_slot（席ごとの出生の初期値）の符号も別の欄に出す。
"""
import argparse
import gzip
import hashlib
import json
import os
import re
import sys
import time
import zlib
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from surface import BASE, NA, discover, fmt, load_json, one, stat_key, write_csv  # noqa: E402

MSCHEMA = 1
OUT = BASE / "out"
CACHE = BASE / "cache_mechanism"
BLOCK = 100
AFTER = 200


def iter_records(path, note):
    """jsonl（.gz も）を読める所まで読む。書きかけの末尾（壊れた行・gzip の途中）で止まり、note に書く。"""
    opener = gzip.open if str(path).endswith(".gz") else open
    try:
        with opener(path, "rt", encoding="utf-8") as f:
            for line in f:
                if not line.endswith("\n"):
                    note["書きかけの末尾"] = note.get("書きかけの末尾", 0) + 1
                    return
                try:
                    yield json.loads(line)
                except json.JSONDecodeError:
                    note["壊れた行で止めた"] = note.get("壊れた行で止めた", 0) + 1
                    return
    except (EOFError, zlib.error, OSError) as e:
        note["gzip の途中で止めた"] = type(e).__name__


def sign(x):
    if x is None or x != x or x in (float("inf"), float("-inf")):
        return "nonfinite"
    return "pos" if x > 0 else "neg" if x < 0 else "zero"


def time_log_rss(path):
    if not path or not Path(path).exists():
        return None, None
    rss = wall = None
    for line in Path(path).read_text(errors="replace").splitlines():
        line = line.strip()
        if line.startswith("Maximum resident set size"):
            rss = int(line.split(":")[-1]) * 1024
        elif line.startswith("Elapsed (wall clock) time"):
            v = line.split(": ", 1)[-1].split(":")
            try:
                wall = sum(float(x) * 60 ** i for i, x in enumerate(reversed(v)))
            except ValueError:
                pass
    return rss, wall


def files(run):
    rd, s = run["run_dir"], run["seed"]
    tl = run.get("time_log")
    if tl:
        tl = str(Path(os.path.expanduser(tl.format(run_dir=rd, seed=s))).resolve())
    return {"side": one((rd, f"side/*/seed{s:03d}.jsonl")),
            "stage2": one((rd, f"stage2/*/seed{s:03d}.jsonl.gz")),
            "initial": one((rd, f"stage2/*/seed{s:03d}.jsonl.gz.initial.jsonl.gz")),
            "calib": one((rd, f"researcher/*/seed{s:03d}.calibration.jsonl.gz")),
            "manifest": Path(rd) / "manifest.jsonl" if (Path(rd) / "manifest.jsonl").exists() else None,
            "time_log": Path(tl) if tl and Path(tl).exists() else None}


def compute(run):
    t0 = time.monotonic()
    fs = files(run)
    notes = {}
    res = {"run_dir": run["run_dir"], "seed": run["seed"], "complete": bool(run.get("done"))}
    flag = Path(run["run_dir"]) / "flag.json"
    res["run_commit"] = str(load_json(flag).get("commit", ""))[:7] if flag.exists() else ""
    # ---- side：M1・M3・M4
    traj = []
    births = Counter()
    assim = Counter()
    retire = Counter()
    m4_cases = m4_seats = 0
    defs_after = {}
    last = None
    if fs["side"] is None:
        res["side_status"] = "side の jsonl なし"
    else:
        sn = {}
        v39 = {}
        for r in iter_records(fs["side"], sn):
            k = r.get("kind")
            if k == "birth":
                births[r["trial"]] += 1
            elif k == "assim":
                assim[r["trial"]] += 1
            elif k == "v39":
                t = r["trial"]
                v39[t] = (r["defs"], r["F"], r["H"], r["U"], r["bits_after"])
                retire[t] += len(r.get("retire") or [])
                grp = defaultdict(set)
                for c in r.get("conv") or []:
                    grp[c[1]].add(c[2])
                for R, slots in grp.items():
                    if len(slots) >= 2:
                        m4_cases += 1
                        m4_seats += len(slots)
        res["side_status"] = "ok" + (f"（{sn}）" if sn else "")
        if v39:
            ts = sorted(v39)
            last = ts[-1]
            if ts != list(range(len(ts))):
                notes["v39 の試行が 0 から続いていない"] = 1
            defs_after = {t: v39[t][0] for t in ts}
            for b in range(0, last + 1, BLOCK):
                end = min(b + BLOCK - 1, last)
                d, F, H, U, bits = v39[end]
                traj.append({"block_first_trial": b, "block_last_trial": end, "defs_after": d, "F": F, "H": H, "U": U,
                             "bits_after": bits,
                             "births_in_block": sum(births[t] for t in range(b, end + 1)),
                             "assim_in_block": sum(assim[t] for t in range(b, end + 1)),
                             "retire_in_block": sum(retire[t] for t in range(b, end + 1))})
    res["trials_read"] = (last + 1) if last is not None else 0
    after = [d for t, d in defs_after.items() if t >= AFTER]
    res["m1_trials_from200"] = len(after)
    res["m1_defs_le1_frac_from200"] = fmt(sum(d <= 1 for d in after) / len(after)) if after else NA
    res["m1_defs_le1_trials_from200"] = sum(d <= 1 for d in after) if after else NA
    res["m1_defs0_trials_from200"] = sum(d == 0 for d in after) if after else NA
    res["m1_defs_last"] = defs_after[last] if last is not None else NA
    lim = (lambda t: last is not None and t <= last)
    res["m3_births"] = sum(v for t, v in births.items() if lim(t))
    res["m3_assim"] = sum(v for t, v in assim.items() if lim(t))
    res["m3_retire"] = sum(v for t, v in retire.items() if lim(t))
    res["m3_check_births_minus_retire_eq_defs_last"] = (
        NA if last is None else "yes" if res["m3_births"] - res["m3_retire"] == defs_after[last] else "no")
    res["m4_cases"] = m4_cases if fs["side"] else NA
    res["m4_seats_in_cases"] = m4_seats if fs["side"] else NA
    # ---- 第二段の本流：M2
    if fs["stage2"] is None:
        res["m2_status"] = "第二段の記録（stage2/…/seedNNN.jsonl.gz）なし"
        for k in ("m2_disclosed", "m2_disclosed_no_seats", "m2_seats", "m2_zero", "m2_neg", "m2_pos", "m2_nonfinite",
                  "m2_zero_frac", "m2_neg_frac", "m2_pos_frac"):
            res[k] = NA
    else:
        sn = {}
        c = Counter()
        n2 = 0
        for r in iter_records(fs["stage2"], sn):
            if last is not None and r["trial"] > last:
                break
            n2 += 1
            if not r.get("f_fired"):
                continue
            c["disclosed"] += 1
            rows = r.get("rows") or []
            if not rows:
                c["no_seats"] += 1
            for x in rows:
                c[sign(x.get("delta"))] += 1
        seats = c["zero"] + c["neg"] + c["pos"] + c["nonfinite"]
        res["m2_status"] = f"ok（本流 {n2} 試行を読んだ）" + (f"（{sn}）" if sn else "")
        res.update(m2_disclosed=c["disclosed"], m2_disclosed_no_seats=c["no_seats"], m2_seats=seats, m2_zero=c["zero"],
                   m2_neg=c["neg"], m2_pos=c["pos"], m2_nonfinite=c["nonfinite"])
        for k in ("zero", "neg", "pos"):
            res[f"m2_{k}_frac"] = fmt(c[k] / seats) if seats else NA
    # ---- M5
    rss, wall = time_log_rss(fs["time_log"])
    man = None
    if fs["manifest"] is not None:
        for line in open(fs["manifest"], encoding="utf-8"):
            if line.strip():
                x = json.loads(line)
                if x.get("seed") in (None, run["seed"]):
                    man = x
                    break
    if man is not None and man.get("elapsed_sec") is not None:
        res["m5_elapsed_sec"], res["m5_elapsed_source"] = man["elapsed_sec"], "manifest.jsonl の elapsed_sec"
    elif wall is not None:
        res["m5_elapsed_sec"], res["m5_elapsed_source"] = round(wall, 2), "time -v の Elapsed (wall clock)"
    else:
        res["m5_elapsed_sec"], res["m5_elapsed_source"] = NA, "manifest も time -v の記録も無い（走り終えていない本など）"
    if rss is not None:
        res["m5_peak_rss_gib"], res["m5_rss_source"] = fmt(rss / 2 ** 30, 3), "time -v の Maximum resident set size"
    elif man is not None and man.get("peak_rss_mb") is not None:
        res["m5_peak_rss_gib"] = fmt(man["peak_rss_mb"] * 1e6 * 1024 / 2 ** 30, 3)
        res["m5_rss_source"] = "manifest.jsonl の peak_rss_mb（ru_maxrss KiB÷1e6。×1e6 KiB に直した。約 0.1GB の粗さ）"
    else:
        res["m5_peak_rss_gib"], res["m5_rss_source"] = NA, "最大常駐の記録が無い"
    # ---- M6
    if fs["calib"] is None:
        res["m6_status"] = "NA：researcher の calibration の記録なし（忘却の実行を止めた較正の本にだけある）"
        for k in ("m6_values", "m6_pos", "m6_zero", "m6_neg", "m6_pos_frac", "m6_FH_pos_frac", "m6_HU_pos_frac", "m6_ref_HU_pos_frac"):
            res[k] = NA
    else:
        sn = {}
        c = Counter()
        n6 = 0
        for r in iter_records(fs["calib"], sn):
            if last is not None and r["trial"] > last:
                break
            n6 += 1
            for x in r.get("candidates") or []:
                key = ("ref_" if x.get("reference") else "") + x["kind"]
                c[(key, sign(x["V"]))] += 1
        act = [k for k in ("FH", "HU")]
        tot = sum(v for (k, s), v in c.items() if k in act)
        pos = sum(v for (k, s), v in c.items() if k in act and s == "pos")
        res["m6_status"] = f"ok（calibration {n6} 試行を読んだ）" + (f"（{sn}）" if sn else "")
        res["m6_values"] = tot
        res["m6_pos"] = pos
        res["m6_zero"] = sum(v for (k, s), v in c.items() if k in act and s == "zero")
        res["m6_neg"] = sum(v for (k, s), v in c.items() if k in act and s == "neg")
        res["m6_pos_frac"] = fmt(pos / tot) if tot else NA

        def frac(k):
            n = sum(v for (kk, s), v in c.items() if kk == k)
            return fmt(c[(k, "pos")] / n) if n else NA
        res["m6_FH_pos_frac"], res["m6_HU_pos_frac"], res["m6_ref_HU_pos_frac"] = frac("FH"), frac("HU"), frac("ref_HU")
    if fs["initial"] is None:
        res["birth_init_status"] = "第二段の出生の記録（.initial.jsonl.gz）なし"
        for k in ("birth_init_seats", "birth_init_pos", "birth_init_zero", "birth_init_neg"):
            res[k] = NA
    else:
        sn = {}
        c = Counter()
        n0 = 0
        for r in iter_records(fs["initial"], sn):
            if last is not None and r["trial"] > last:
                break
            n0 += 1
            for v in (r.get("delta_by_slot") or {}).values():
                c[sign(v)] += 1
        res["birth_init_status"] = f"ok（出生の記録 {n0} 件）" + (f"（{sn}）" if sn else "")
        res.update(birth_init_seats=sum(c.values()), birth_init_pos=c["pos"], birth_init_zero=c["zero"], birth_init_neg=c["neg"])
    res["notes"] = json.dumps(notes, ensure_ascii=False) if notes else ""
    res["trajectory"] = traj
    res["wall_seconds"] = round(time.monotonic() - t0, 2)
    return res


def mkey(run):
    fs = files(run)
    return {"schema": MSCHEMA, "done": stat_key(run.get("done")), **{k: stat_key(v) for k, v in fs.items()}}


def cached(args):
    run, redo, cache_dir = args
    key = mkey(run)
    cp = Path(cache_dir) / (hashlib.sha1(run["run_dir"].encode()).hexdigest()[:16] + ".json")
    if cp.exists() and not redo:
        c = load_json(cp)
        if c.get("key") == key:
            return c["result"], False
    res = compute(run)
    cp.parent.mkdir(parents=True, exist_ok=True)
    tmp = cp.with_suffix(".tmp")
    tmp.write_text(json.dumps({"key": key, "result": res}, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp, cp)
    return res, True


FIELDS = ["config", "lambda", "world", "seed", "run_commit", "complete", "trials_read", "results_hold",
          "m1_defs_le1_frac_from200", "m1_defs_le1_trials_from200", "m1_defs0_trials_from200", "m1_trials_from200", "m1_defs_last",
          "m2_disclosed", "m2_disclosed_no_seats", "m2_seats", "m2_zero", "m2_neg", "m2_pos", "m2_nonfinite",
          "m2_zero_frac", "m2_neg_frac", "m2_pos_frac", "m2_status",
          "m3_births", "m3_assim", "m3_retire", "m3_check_births_minus_retire_eq_defs_last",
          "m4_cases", "m4_seats_in_cases",
          "m5_elapsed_sec", "m5_elapsed_source", "m5_peak_rss_gib", "m5_rss_source",
          "m6_pos_frac", "m6_values", "m6_pos", "m6_zero", "m6_neg", "m6_FH_pos_frac", "m6_HU_pos_frac", "m6_ref_HU_pos_frac", "m6_status",
          "birth_init_seats", "birth_init_pos", "birth_init_zero", "birth_init_neg", "birth_init_status",
          "side_status", "notes", "run_dir"]
TFIELDS = ["config", "lambda", "world", "seed", "complete", "block_first_trial", "block_last_trial", "defs_after", "F", "H", "U",
           "bits_after", "births_in_block", "assim_in_block", "retire_in_block"]


def safe(name):
    return re.sub(r'[\\/:*?"<>|\s]', lambda m: "star" if m.group() == "*" else "_", name)


def write_tables(out, runs, results):
    by = defaultdict(list)
    for run, res in zip(runs, results):
        by[run["config"]].append((run, res))
    written = []
    for cfg, items in by.items():
        items.sort(key=lambda x: (x[0]["world"], x[0]["seed"]))
        rows, trows = [], []
        for run, res in items:
            base = {"config": cfg, "lambda": run["lambda"], "world": run["world"], "seed": run["seed"],
                    "complete": "yes" if res["complete"] else "no（途中まで）"}
            rows.append({**{k: res.get(k, "") for k in FIELDS}, **base, "results_hold": "yes" if run.get("results_hold") else ""})
            trows += [{**base, **t} for t in res["trajectory"]]
        f1, f2 = out / f"mechanism_{safe(cfg)}.csv", out / f"mechanism_trajectory_{safe(cfg)}.csv"
        write_csv(f1, rows, FIELDS)
        write_csv(f2, trows, TFIELDS)
        written += [f1.name, f2.name]
    return written


def main():
    ap = argparse.ArgumentParser(description="仕組みの表（読むだけ）")
    ap.add_argument("--configs", default=str(BASE / "configs.json"))
    ap.add_argument("--jobs", type=int, default=4)
    ap.add_argument("--redo", action="store_true")
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--cache", default=str(CACHE))
    ap.add_argument("--run", help="試し：完了の印の無い本も読む（--config・--world・--seed と一緒に）")
    ap.add_argument("--config")
    ap.add_argument("--world", type=int)
    ap.add_argument("--seed", type=int)
    ap.add_argument("--time-log")
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    t0 = time.monotonic()
    if a.run:
        if a.seed in range(21, 41):
            sys.exit("種 21〜40 は読まない")
        run = {"run_dir": str(Path(a.run).resolve()), "seed": a.seed, "config": a.config, "world": a.world, "lambda": "",
               "done": None, "time_log": a.time_log, "results_hold": False}
        res = compute(run)
        print(write_tables(out, [run], [res]), f"{time.monotonic() - t0:.1f} 秒")
        return
    cfg = load_json(a.configs)
    runs, notes = discover(cfg, include_held=True)
    jobs = max(1, min(4, a.jobs))
    results, fresh = [], 0
    if runs:
        with ProcessPoolExecutor(max_workers=jobs) as ex:
            for res, new in ex.map(cached, [(r, a.redo, a.cache) for r in runs]):
                results.append(res)
                fresh += new
    # 前に書いた表で、今は構成が無いものは消さない（他の構成の表を書き直すだけ）
    written = write_tables(out, runs, results)
    (out / "mechanism_meta.json").write_text(json.dumps({
        "作った時刻": datetime.now().isoformat(timespec="seconds"), "本数": len(runs), "今回読み直した本": fresh,
        "時間_秒": round(time.monotonic() - t0, 1), "表": sorted(written),
        "成績を保留した本（仕組みの表だけ出す）": sum(1 for r in runs if r.get("results_hold")),
        "数え方": __doc__.split("数え方と出どころ", 1)[1].strip()}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"{datetime.now():%F %T} 仕組みの表：本 {len(runs)}（読み直し {fresh}）、{time.monotonic() - t0:.1f} 秒", flush=True)


if __name__ == "__main__":
    main()

"""第 2 波（#8・#10〜#13・#15〜#18）の成績の表（受け箱の指示 68 の 1・84 の 3）。読むだけ。

決まりは第 1 波の表（~/surface/wave1.py）と同じ。wave1.py を import して、その one_run・rate・boot_diff・mean・fmt・B・RNG_SEED・METRICS を
そのまま使う（wave1.py は書き換えない。meta.json に wave1.py の sha256 を書く）。
  - 一本ごと：台帳の試行の行から正解・棄権・誤答。capable＝注意の記録 attention/<セル>/seedNNN.jsonl.gz の candidates に gate_passed かつ hit の候補がある
    （第 2 波の行も 1a も注意の記録を使う。2a の再生の道は通らない）。選び間違い＝誤答で capable、不在＝capable でない（全課題）。分母は全課題・全部の日。
  - 比べ：各行 対 1a（1a/1b、全部入り L50、第 1 波の表と同じ本＝~/surface/wave1_view/selection.tsv）、世界ごと、量は選び間違いの率と不在の率。
    差＝（行の種の平均）−（1a の同じ種の平均）。範囲＝同じ種の番号どうしの対を選び直す 4,000 回の百分位 2.5%・97.5%
    （乱数は比べごとに random.Random(f"{RNG_SEED}-{行}-{世界}-{量}")）。判定＝「候補」（0 をまたがない）／「候補でない」。
    20 種がそろっていない比べは「未完（n/20）」で、範囲と判定を出さない（wave1.py と同じ）。
  - 参考（判定ではない）：走行の列 2026-10-08 の「種の方針」（第 2 波はまず 10 本。後半を足すのは、10 本で比の 95% の範囲（種の選び直し
    4,000 回）が 1 をまたぐ比べだけ）のための、そろっている種での平均の比の範囲。reference_ratio_ci.csv に別に書く。
  - 記憶のビット：side の jsonl の kind=v39 の記録の bits_after（surface.py の memory_stats と同じ読み方。configs.json の memory）。
    mem_bits_mean＝一本の全試行の平均、mem_bits_last＝最後の試行の値。memory_bits_vs_errors.csv は surface.py の MB_FIELDS の形
    （構成・世界・範囲・日ごとの種の平均）。率は上の capable（注意の記録）で数える。
  - 量が重なる範囲（台帳 D-07f）：memory_bits_overlap.csv。定義は meta.json。
使い方：
  nice -n 15 python3 -B ~/surface/wave2.py --out DIR [--jobs 3]
"""
import argparse
import csv
import hashlib
import json
import math
import random
import shutil
import statistics
import sys
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

sys.dont_write_bytecode = True                      # ~/surface/__pycache__ を書き換えない
sys.path.insert(0, str(Path.home() / "surface"))
import wave1  # noqa: E402  決まりの本体（書き換えない）

V1 = Path.home() / "surface/wave1_view"
V2 = Path.home() / "surface/wave2_view"
CFG = Path.home() / "surface/configs_wave2.json"
B, RNG_SEED, METRICS = wave1.B, wave1.RNG_SEED, wave1.METRICS
rate, fmt, mean, boot_diff = wave1.rate, wave1.fmt, wave1.mean, wave1.boot_diff
SCOPES = ("全課題", "ドア課題")
DAYS = ("例外", "通常", "全日")
L25, L50 = 0.00010926774617357411, 0.00035129738499384776
# 走行の列の第 2 波の欄・命令の一覧（wave2_s55_commands.json・wave2d_commands.json）から、flag.json で確かめる値
EXPECT = {
    "1": dict(commit=("c79215980a913cc426a63f25048e0dfc6fd1f758", "4ceadf63f6924bdab8013d3e39b1549a8c5c0966"), v39_price=L50, shop_exc=0.2, use_forget=None, use_forget_attn=None, stage2="on"),
    "8": dict(commit=("c79215980a913cc426a63f25048e0dfc6fd1f758",), v39_price=L25, shop_exc=0.2, use_forget=None, use_forget_attn=None, stage2="on"),
    "10": dict(commit=("daf69efd196db28b29f1e564ebf6dc57c6c39f60",), v39_price=L50, shop_exc=0.2, use_forget=0.4, use_forget_attn=None, stage2=None),
    "11": dict(commit=("daf69efd196db28b29f1e564ebf6dc57c6c39f60",), v39_price=L50, shop_exc=0.2, use_forget=0.15, use_forget_attn=None, stage2=None),
    "12": dict(commit=("daf69efd196db28b29f1e564ebf6dc57c6c39f60",), v39_price=L50, shop_exc=0.2, use_forget=0.4, use_forget_attn=True, stage2=None),
    "13": dict(commit=("daf69efd196db28b29f1e564ebf6dc57c6c39f60",), v39_price=L50, shop_exc=0.2, use_forget=0.15, use_forget_attn=True, stage2=None),
    "15": dict(commit=("c79215980a913cc426a63f25048e0dfc6fd1f758",), v39_price=L50, shop_exc=0.1, use_forget=None, use_forget_attn=None, stage2="on"),
    "16": dict(commit=("c79215980a913cc426a63f25048e0dfc6fd1f758",), v39_price=L50, shop_exc=0.3, use_forget=None, use_forget_attn=None, stage2="on"),
    "17": dict(commit=("daf69efd196db28b29f1e564ebf6dc57c6c39f60",), v39_price=L50, shop_exc=0.1, use_forget=0.4, use_forget_attn=True, stage2=None),
    "18": dict(commit=("daf69efd196db28b29f1e564ebf6dc57c6c39f60",), v39_price=L50, shop_exc=0.3, use_forget=0.4, use_forget_attn=True, stage2=None),
}
ROWS2 = ["8", "10", "11", "12", "13", "15", "16", "17", "18"]
MAIN = {"10", "11", "12", "13", "17", "18"}          # 指示 84 の 3：揃っている行（D・D＋注意）
MEMROWS = ["1", "8", "10", "11", "12", "13"]         # 指示 68 の 1・84 の 3：memory_bits_vs_errors に入れる行（1a は比べの相手）
MB_FIELDS = ["config", "lambda", "world", "scope", "day", "n_seeds", "seeds", "mem_bits_mean", "mem_bits_mean_sd",
             "mem_bits_last_mean", "defs_mean", "F_mean", "H_mean", "U_mean",
             "n_seeds_with_candidates", "rate_selection_error_mean", "rate_selection_error_sd",
             "rate_absent_mean", "rate_absent_sd", "rate_distinction_loss_mean", "rate_wrong_mean", "rate_silent_mean"]


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def arms_info():
    d = json.loads(CFG.read_text())
    info = {}
    for g in d["groups"]:
        for arm, a in g.get("arms", {}).items():
            info[arm] = a
    return info, d["memory"]


def memory_stats(run_dir, seed, mem):
    """surface.py の memory_stats と同じ読み方（side/*/seedNNN.jsonl の kind=v39 の記録）。"""
    ps = sorted(Path(run_dir).glob(f"side/*/seed{seed:03d}.jsonl"))
    if len(ps) != 1:
        return None, "side の jsonl が無いか二つ以上"
    kind = mem.get("kind", "v39")
    f = mem.get("fields")
    tag = f'"kind": "{kind}"'
    rows = []
    with open(ps[0], encoding="utf-8") as fh:
        for line in fh:
            if tag not in line[:40]:
                continue
            r = json.loads(line)
            if r.get("kind") == kind:
                rows.append(r)
    if not rows:
        return None, f"side の jsonl に kind={kind} の記録なし"
    rows.sort(key=lambda r: r["trial"])
    out = {"mem_trials": len(rows)}
    for k, name in (("mem_bits", "bits"), ("defs", "defs"), ("F", "F"), ("H", "H"), ("U", "U")):
        vals = [r.get(f[name]) for r in rows]
        if any(v is None for v in vals):
            return None, f"kind={kind} の記録に {f[name]} が無い試行がある"
        out[k + "_mean"] = float(statistics.fmean(vals))
        out[k + "_last"] = vals[-1]
    return out, "ok"


def flag_check(run_dir, key, world):
    p = Path(run_dir) / "flag.json"
    if not p.exists():
        return "flag.json が無い"
    fl = json.loads(p.read_text())
    e = EXPECT[key]
    bad = []
    if fl.get("commit") not in e["commit"]:
        bad.append(f"commit={fl.get('commit')}")
    for k in ("v39_price", "shop_exc", "use_forget", "use_forget_attn", "stage2"):
        if fl.get(k) != e[k]:
            bad.append(f"{k}={fl.get(k)}")
    if fl.get("shop_world") != world:
        bad.append(f"shop_world={fl.get('shop_world')}")
    return "ok" if not bad else "違う：" + "、".join(bad)


def run_one(view, row, world, seed, run, version, key, mem):
    wave1.V = view                                   # wave1.one_run は V/<行>/q<行>_w<世界>/seedNNN を読む
    o, c = wave1.one_run(row, world, seed, run, version)
    rd = view / row / f"q{row}_w{world}" / f"seed{seed:03d}"
    o["flag_check"] = flag_check(rd, key, world) if rd.exists() else ""
    m, mst = (memory_stats(rd, seed, mem) if rd.exists() else (None, "本が無い"))
    o["memory_status"] = mst
    if m:
        o.update(mem_bits_mean=fmt(m["mem_bits_mean"]), mem_bits_last=m["mem_bits_last"], defs_last=m["defs_last"], mem_trials=m["mem_trials"])
    return o, c, m


def boot_ratio(x, y, rng):
    n = len(x)
    rs, und = [], 0
    for _ in range(B):
        idx = [rng.randrange(n) for _ in range(n)]
        a, b = sum(x[i] for i in idx) / n, sum(y[i] for i in idx) / n
        if b == 0:
            if a == 0:
                und += 1
                continue
            rs.append(float("inf"))
        else:
            rs.append(a / b)
    if not rs:
        return float("nan"), float("nan"), und
    rs.sort()
    return rs[int(math.floor(0.025 * len(rs)))], rs[int(math.ceil(0.975 * len(rs))) - 1], und


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--jobs", type=int, default=3)
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    arms, mem = arms_info()
    sel1 = [s for s in csv.DictReader(open(V1 / "selection.tsv"), delimiter="\t") if s["row"] in ("1a", "1b")]
    sel2 = list(csv.DictReader(open(V2 / "selection.tsv"), delimiter="\t"))
    per, counts, mems = [], {}, {}
    jobs = []
    for s, view, key in [(s, V1, "1") for s in sel1] + [(s, V2, s["row"]) for s in sel2]:
        w, sd = int(s["world"]), int(s["seed"])
        if not s["run"]:
            why = "未完（走らせていない：第 2 波は種 1〜10）" if key != "1" and sd > 10 else "未完（持ち帰っていない）"
            per.append(dict(row=s["row"], world=w, seed=sd, run="", version="", status=why, source="", trials=0))
            continue
        jobs.append((len(per), key, w, sd, (view, s["row"], w, sd, s["run"], s["version"], key, mem)))
        per.append(None)
    with ProcessPoolExecutor(max_workers=a.jobs) as ex:
        futs = {ex.submit(run_one, *args): (i, key, w, sd) for i, key, w, sd, args in jobs}
        for fu in as_completed(futs):
            i, key, w, sd = futs[fu]
            o, c, m = fu.result()
            per[i] = o
            if c is not None:
                counts[(key, w, sd)] = c
            if m is not None:
                mems[(key, w, sd)] = m
            print(f"{o['row']} w{w} s{sd} {o['status']} {o.get('flag_check')} {o.get('memory_status')}", flush=True)

    def cfg(key, w):
        arm = "q1a_w%d" % w if key == "1" else f"q{key}_w{w}"
        return arms[arm]["config"], arms[arm]["lambda"]

    # ---- per_run.csv
    pf = ["row", "world", "seed", "run", "version", "status", "source", "trials", "tasks",
          "rate_selection_error", "rate_absent", "rate_distinction_loss", "rate_wrong", "rate_silent", "rate_correct",
          "door_exception_tasks", "door_exception_rate_selection_error", "door_exception_rate_absent",
          "config", "lambda", "flag_check", "memory_status", "mem_trials", "mem_bits_mean", "mem_bits_last", "defs_last"]
    with open(out / "per_run.csv", "w", newline="", encoding="utf-8") as f:
        w_ = csv.DictWriter(f, fieldnames=pf)
        w_.writeheader()
        for p in per:
            key = "1" if p["row"] in ("1a", "1b") else p["row"]
            c = counts.get((key, p["world"], p["seed"]))
            r = dict(p)
            r["config"], r["lambda"] = cfg(key, p["world"])
            if c:
                r.update(tasks=c[("全課題", "全日", "tasks")], **{f"rate_{k}": fmt(rate(c, "全課題", "全日", k)) for k in
                         ("selection_error", "absent", "distinction_loss", "wrong", "silent", "correct")},
                         door_exception_tasks=c.get(("ドア課題", "例外", "tasks"), 0),
                         door_exception_rate_selection_error=fmt(rate(c, "ドア課題", "例外", "selection_error")),
                         door_exception_rate_absent=fmt(rate(c, "ドア課題", "例外", "absent")))
            w_.writerow(r)

    # ---- comparisons.csv（wave1.py と同じ列・同じ決まり）＋ 参考の比の範囲
    cf = ["row", "row_config", "vs", "world", "metric", "n_seeds_both", "status", "mean_row", "mean_1a", "diff",
          "ci95_lo", "ci95_hi", "judgment", "ratio_of_means", "door_exception_mean_row", "door_exception_mean_1a",
          "boot_resamples", "rng_seed"]
    rf = ["row", "row_config", "vs", "world", "metric", "n_seeds_both", "seeds", "ratio_of_means", "ratio_ci95_lo",
          "ratio_ci95_hi", "ratio_ci_contains_1", "boot_undefined", "boot_resamples", "rng_seed", "note"]
    comps, refs, seedcount = [], [], []
    for r in ROWS2:
        for wd in (1, 2):
            if f"q{r}_w{wd}" not in arms:
                continue
            present = [s for s in range(1, 21) if (r, wd, s) in counts]
            both = [s for s in range(1, 21) if (r, wd, s) in counts and ("1", wd, s) in counts]
            seedcount.append(dict(row=r, world=wd, n=len(present), seeds=present))
            for m in METRICS:
                x = [rate(counts[(r, wd, s)], "全課題", "全日", m) for s in both]
                y = [rate(counts[("1", wd, s)], "全課題", "全日", m) for s in both]
                xd = [rate(counts[(r, wd, s)], "ドア課題", "例外", m) for s in both]
                yd = [rate(counts[("1", wd, s)], "ドア課題", "例外", m) for s in both]
                mx, my = mean(x), mean(y)
                row = dict(row=f"#{r}", row_config=cfg(r, wd)[0], vs="1a/1b（全部入り_L50）", world=wd, metric=m,
                           n_seeds_both=len(both), mean_row=fmt(mx), mean_1a=fmt(my), diff=fmt(mx - my) if both else "NA",
                           ratio_of_means=fmt(mx / my) if both and my else "NA",
                           door_exception_mean_row=fmt(mean(xd)), door_exception_mean_1a=fmt(mean(yd)),
                           boot_resamples=B, rng_seed=RNG_SEED)
                if len(both) < 20:
                    row.update(status=f"未完（{len(both)}/20）", ci95_lo="", ci95_hi="", judgment="")
                else:
                    rng = random.Random(f"{RNG_SEED}-{r}-{wd}-{m}")
                    lo, hi = boot_diff(x, y, rng)
                    row.update(status="20/20", ci95_lo=fmt(lo), ci95_hi=fmt(hi),
                               judgment="候補" if (lo > 0 or hi < 0) else "候補でない")
                comps.append(row)
                if both:
                    rng = random.Random(f"{RNG_SEED}-ratio-{r}-{wd}-{m}")
                    lo, hi, und = boot_ratio(x, y, rng)
                    refs.append(dict(row=f"#{r}", row_config=cfg(r, wd)[0], vs="1a/1b（全部入り_L50）", world=wd, metric=m,
                                     n_seeds_both=len(both), seeds=",".join(map(str, both)),
                                     ratio_of_means=fmt(mx / my) if my else "NA", ratio_ci95_lo=fmt(lo), ratio_ci95_hi=fmt(hi),
                                     ratio_ci_contains_1=("NA" if math.isnan(lo) else "yes" if lo <= 1 <= hi else "no"),
                                     boot_undefined=und, boot_resamples=B, rng_seed=RNG_SEED,
                                     note="参考（判定ではない）：走行の列の種の方針（後半を足すか）の目安"))
    with open(out / "comparisons.csv", "w", newline="", encoding="utf-8") as f:
        w_ = csv.DictWriter(f, fieldnames=cf)
        w_.writeheader()
        w_.writerows(comps)
    with open(out / "reference_ratio_ci.csv", "w", newline="", encoding="utf-8") as f:
        w_ = csv.DictWriter(f, fieldnames=rf)
        w_.writeheader()
        w_.writerows(refs)

    # ---- memory_bits_vs_errors.csv（surface.py の MB_FIELDS の形）
    mrows = []
    for wd in (1, 2):
        for key in MEMROWS:
            seeds = sorted(s for (k, w2, s) in counts if k == key and w2 == wd)
            if not seeds:
                continue
            ms = [mems[(key, wd, s)] for s in seeds if (key, wd, s) in mems]
            for scope in SCOPES:
                for day in DAYS:
                    c_, l_ = cfg(key, wd)
                    r = {"config": c_, "lambda": l_, "world": wd, "scope": scope, "day": day, "n_seeds": len(seeds),
                         "seeds": ",".join(map(str, seeds))}
                    for k, src in (("mem_bits_mean", "mem_bits_mean"), ("mem_bits_last_mean", "mem_bits_last"),
                                   ("defs_mean", "defs_mean"), ("F_mean", "F_mean"), ("H_mean", "H_mean"), ("U_mean", "U_mean")):
                        r[k] = fmt(float(statistics.fmean([m[src] for m in ms]))) if ms else "NA"
                    r["mem_bits_mean_sd"] = fmt(float(statistics.stdev([m["mem_bits_mean"] for m in ms]))) if len(ms) > 1 else "NA"
                    r["n_seeds_with_candidates"] = len(seeds)
                    for m in ("selection_error", "absent", "distinction_loss", "wrong", "silent"):
                        v = [rate(counts[(key, wd, s)], scope, day, m) for s in seeds]
                        v = [x for x in v if not math.isnan(x)]
                        r[f"rate_{m}_mean"] = fmt(float(statistics.fmean(v))) if v else "NA"
                        if m in ("selection_error", "absent"):
                            r[f"rate_{m}_sd"] = fmt(float(statistics.stdev(v))) if len(v) > 1 else "NA"
                    mrows.append(r)
    with open(out / "memory_bits_vs_errors.csv", "w", newline="", encoding="utf-8") as f:
        w_ = csv.DictWriter(f, fieldnames=MB_FIELDS)
        w_.writeheader()
        w_.writerows(mrows)

    # ---- memory_bits_overlap.csv（台帳 D-07f：記憶のビットが重なる範囲での比べ。一本ごとの mem_bits_mean で範囲を決める）
    of = ["world", "config", "reference", "n_runs_config", "n_runs_reference", "config_bits_min", "config_bits_max",
          "reference_bits_min", "reference_bits_max", "overlap_lo", "overlap_hi", "n_config_in_overlap", "n_reference_in_overlap",
          "config_seeds_in_overlap", "reference_runs_in_overlap", "metric", "mean_config_in_overlap", "mean_reference_in_overlap",
          "diff_in_overlap"]
    orows = []
    REFS = {"1a（全部入り_L50）": ["1"], "全部入り（1a の L50 と #8 の L25 を合わせる）": ["1", "8"]}
    for wd in (1, 2):
        for key in ("10", "11", "12", "13"):
            cr = [(s, mems[(key, wd, s)]["mem_bits_mean"]) for (k, w2, s) in counts if k == key and w2 == wd and (k, w2, s) in mems]
            for rname, rkeys in REFS.items():
                rr = [(k, s, mems[(k, w2, s)]["mem_bits_mean"]) for (k, w2, s) in counts
                      if k in rkeys and w2 == wd and (k, w2, s) in mems]
                if not cr or not rr:
                    continue
                cmin, cmax = min(b for _, b in cr), max(b for _, b in cr)
                rmin, rmax = min(b for *_, b in rr), max(b for *_, b in rr)
                lo, hi = max(cmin, rmin), min(cmax, rmax)
                cin = sorted(s for s, b in cr if lo <= b <= hi) if lo <= hi else []
                rin = sorted((k, s) for k, s, b in rr if lo <= b <= hi) if lo <= hi else []
                for m in METRICS:
                    mc = mean([rate(counts[(key, wd, s)], "全課題", "全日", m) for s in cin]) if cin else float("nan")
                    mr = mean([rate(counts[(k, wd, s)], "全課題", "全日", m) for k, s in rin]) if rin else float("nan")
                    orows.append(dict(world=wd, config=cfg(key, wd)[0], reference=rname, n_runs_config=len(cr), n_runs_reference=len(rr),
                                      config_bits_min=fmt(cmin), config_bits_max=fmt(cmax), reference_bits_min=fmt(rmin),
                                      reference_bits_max=fmt(rmax), overlap_lo=fmt(lo) if lo <= hi else "重ならない",
                                      overlap_hi=fmt(hi) if lo <= hi else "重ならない", n_config_in_overlap=len(cin),
                                      n_reference_in_overlap=len(rin), config_seeds_in_overlap=",".join(map(str, cin)),
                                      reference_runs_in_overlap=",".join(("1a" if k == "1" else "#" + k) + f"_s{s}" for k, s in rin),
                                      metric=m, mean_config_in_overlap=fmt(mc), mean_reference_in_overlap=fmt(mr),
                                      diff_in_overlap=fmt(mc - mr) if cin and rin else "NA"))
    with open(out / "memory_bits_overlap.csv", "w", newline="", encoding="utf-8") as f:
        w_ = csv.DictWriter(f, fieldnames=of)
        w_.writeheader()
        w_.writerows(orows)

    # ---- meta.json
    st = Counter((p["row"], p["world"], p["status"] if not p["status"].startswith("NA") else p["status"]) for p in per)
    meta = dict(
        made_at=datetime.now().isoformat(timespec="seconds"),
        rule="受け箱の指示 68 の 1・84 の 3。決まりは第 1 波の表（wave1.py：受け箱の指示 44、理解の場の決定 1〜6、台帳 75 節）と同じ",
        wave1_py_sha256=sha(Path.home() / "surface/wave1.py"),
        rule_code="wave1.py を import して one_run・rate・boot_diff・mean・fmt・B・RNG_SEED・METRICS をそのまま使った（wave1.py は変えていない）",
        rng_seed=RNG_SEED, rng_note="比べごとに random.Random(f'{RNG_SEED}-{行}-{世界}-{量}')（行は 8・10…18）。参考の比の範囲は random.Random(f'{RNG_SEED}-ratio-{行}-{世界}-{量}')",
        resamples=B, percentiles=[2.5, 97.5], denominators="全課題・全部の日",
        capable_definition="注意の記録（attention/<セル>/seedNNN.jsonl.gz）の candidates に gate_passed かつ hit の候補がある（第 2 波の全行と 1a）",
        incomplete_rule="20 種がそろっていない比べは「未完（n/20）」で、範囲と判定を出さない（wave1.py と同じ）",
        wave2_seeds_note="第 2 波は走行の列 2026-10-08 の「種の方針」（第 2 波以降はまず 10 本、前半＝種 1〜10）で、種 1〜10 だけを走らせた。種 11〜20 の本は無い",
        reference_ratio_ci=("reference_ratio_ci.csv は判定ではない参考。走行の列の種の方針（10/7 に先に決めた規則：10 本で、全課題を分母にした選び間違いの率又は"
                            "正答できる定義の不在の率の比の 95% の範囲（種の選び直し 4,000 回）が 1 をまたぐ比べだけ後半を足す）のための数。"
                            "比＝（行の種の平均）／（1a の同じ種の平均）。選び直しごとに比を出し、1a の平均が 0 で行の平均も 0 の回は数えず（boot_undefined）、"
                            "1a の平均が 0 で行の平均が正の回は無限大として並べ、百分位 2.5%・97.5% を取った"),
        selection_1a="~/surface/wave1_view/selection.tsv の 1a・1b（第 1 波の表と同じ本）",
        selection_wave2="~/surface/wave2_view/selection.tsv（wave2_view.py の選び方：#8・#15・#16 は c7921598 の _c792、D・D＋注意は daf69efd の _cdaf。旗なし c57467ea の写しは使わない）",
        configs="~/surface/configs_wave2.json（configs.json の写し。#8・#10〜#13・#15〜#18 の群の root を wave2_view に、todo を外し、results_hold を false に。理解の場の決定 11:06）",
        flag_check="一本ごとに flag.json の commit・v39_price・shop_exc・use_forget・use_forget_attn・stage2・shop_world を、走行の列の第 2 波の欄・命令の一覧の値と突き合わせた（per_run.csv の flag_check）",
        memory_definition=("記憶のビット：side/<セル>/seedNNN.jsonl の kind=v39 の記録の bits_after（試行の後の記憶の総ビット。surface.py の memory_stats と同じ読み方）。"
                           "mem_bits_mean＝一本の全試行（試行 0〜最後）の平均、mem_bits_last＝最後の試行の値。memory_bits_vs_errors.csv は surface.py の形"
                           "（構成・世界・範囲・日ごとに、一本の値の種の平均・標準偏差）。率は注意の記録の capable で数えた（wave1.py の one_run）"),
        memory_rows="memory_bits_vs_errors.csv の構成：全部入り_L50（1a/1b、種 1〜20）・全部入り_L25（#8）・D_τ0.4（#10）・D_τ0.15（#11）・D＋注意_τ0.4（#12）・D＋注意_τ0.15（#13）。世界 1・2 別",
        overlap_definition=("memory_bits_overlap.csv（台帳 D-07f：D と D＋注意は、記憶のビットを横軸に、量が重なる範囲で全部入りと比べる）。"
                            "世界ごと・D／D＋注意の構成ごとに、一本ごとの mem_bits_mean の最小〜最大を、相手（1a だけ、又は 1a と #8 を合わせた全部入り）の"
                            "最小〜最大と重ねた区間 [max(二つの最小), min(二つの最大)] を重なる範囲とした。その範囲に入る本だけで、全課題・全部の日の率の"
                            "本の平均を両方に出し、差（構成 − 相手）を並べる。範囲や判定は出さない。重ならなければ「重ならない」"),
        seeds_present=[dict(row="#" + x["row"], world=x["world"], n_seeds=x["n"], seeds=x["seeds"],
                            status=("20/20" if x["n"] >= 20 else f"未完（{x['n']}/20）")) for x in seedcount],
        runs_ok=sum(1 for p in per if p["status"] == "ok"), runs_total=len(per),
        status_counts={f"{r}_w{w}:{s}": n for (r, w, s), n in sorted(st.items(), key=str)},
        not_read=[dict(row=p["row"], world=p["world"], seed=p["seed"], run=p["run"], status=p["status"])
                  for p in per if p["status"] != "ok"],
        memory_not_read=[dict(row=p["row"], world=p["world"], seed=p["seed"], run=p["run"], memory_status=p.get("memory_status"))
                         for p in per if p.get("run") and p.get("memory_status") != "ok"],
        flag_mismatch=[dict(row=p["row"], world=p["world"], seed=p["seed"], run=p["run"], flag_check=p.get("flag_check"))
                       for p in per if p.get("run") and p.get("flag_check") != "ok"],
        not_used_copies="wave2_8_w1_s1_c574・（#15 の世界 2・種 1 の c57467ea は止まり、持ち帰りなし）：旗なしの写しは使わない",
    )
    (out / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    sd = out / "scripts"
    sd.mkdir(exist_ok=True)
    for p in ("wave2.py", "wave2_view.py", "wave1.py", "configs_wave2.json"):
        shutil.copy2(Path.home() / "surface" / p, sd / p)
    shutil.copy2(V2 / "selection.tsv", sd / "selection_wave2.tsv")
    shutil.copy2(V1 / "selection.tsv", sd / "selection_wave1.tsv")
    print(f"表を書いた：{out}（読めた本 {meta['runs_ok']}/{meta['runs_total']}）")


if __name__ == "__main__":
    sys.exit(main())

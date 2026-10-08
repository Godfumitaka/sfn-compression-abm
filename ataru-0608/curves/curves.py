"""100 試行ごとの区切りの率の推移（受け箱の指示 15）。読むだけ。模型・再生は走らせない。見張りの道具（surface.py など）は変えない。

使い方：nice -n 15 ionice -c3 python3.12 ~/surface/curves.py [--jobs 4]
対象：configs.json の「古い主の条件」の群（~/smeprod_a/sme の 4 構成 × 世界 1・2 × 種 1〜20＝160 本）。
      候補の記録は ~/sme_analysis/replay/<条件>/seedNNN/sme.candidates.jsonl.gz（surface.py と同じ探し方）。種 21〜40 は読まない。
出力（~/surface/curves_out/）：
  curves_per_seed.csv  条件・種・範囲・日・区切りごとの数と率
  curves_summary.csv   条件・範囲・日・区切り・率ごとの、種の平均・第 1／第 3 四分位・最小・最大・使った種の数・課題の数
  plateau.csv          率ごとの「落ち着く区切り」（決め方は下と欄 rule）
  check.json           区切りの数の和と ~/surface/out/per_run.csv の一本ごとの数の突き合わせ
定義（~/surface/surface.py の per_run と同じ。区切りごとに数える）：
  区切り＝台帳の prediction_order（0 始まり）で 0〜99、100〜199、…、1700〜1739（最後は 40 試行）。
  範囲＝全課題／ドア課題（held_out_is_door）。日＝例外（shop_cue＝e）・通常（n）・全日（両方）。
  正答＝hit。黙り＝答えなし。選び間違い＝誤答のうち門を通って正しく答える定義があった件（correct_gate_passed）。
  区別の喪失＝誤答のうち、それが無かった件。不在＝課題のうち、門を通って正しく答える定義が無かった件（棄権を含む）。
  率＝その区切り・範囲・日の課題の数を分母。課題が 0 の種は、その区切りの率の統計から外す（n_seeds に出す）。
  四分位：statistics.quantiles(method="inclusive")（線形の補間。numpy の既定と同じ）。
落ち着く区切り（指示の読み）：区切り b（2 番目以降）で |平均(b)−平均(b−1)| ＜ 四分位幅(b) が成り立ち、b 以降の全部の区切りでも
  成り立つ、最初の b。並べる別の読み：(alt_le) 「＜」を「≦」にしたもの（四分位幅が 0 で差も 0 の区切りを、落ち着いたと数える）。
  (alt_iqr_prev) 四分位幅を前の区切り b−1 のものにしたもの（「＜」）。どの区切りでも成り立たないときは「なし」。
"""
import argparse
import csv
import gzip
import json
import statistics
import sys
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

sys.dont_write_bytecode = True          # ~/surface に __pycache__ を作らない
sys.path.insert(0, str(Path(__file__).resolve().parent))
from surface import DAY, candidate_file, discover, fmt, load_json, one  # noqa: E402

BASE = Path(__file__).resolve().parent
OUT = BASE / "curves_out"
BLOCK = 100
METRICS = ("correct", "selection_error", "distinction_loss", "absent", "silent")
COUNT_KEYS = ("tasks", "correct", "wrong", "silent", "selection_error", "distinction_loss", "absent")
SCOPES = ("全課題", "ドア課題")
DAYS = ("例外", "通常", "全日")


def run_counts(run):
    rd, seed = Path(run["run_dir"]), run["seed"]
    cf, _, _ = candidate_file(run)
    if cf is None:
        raise RuntimeError(f"候補の記録が無い：{rd}")
    led = one((rd, f"ledgers/cells/*/seed{seed:03d}.jsonl.gz"))
    cands = gzip.open(cf, "rt", encoding="utf-8")
    c = Counter()
    with gzip.open(led, "rt", encoding="utf-8") as f:
        for line in f:
            row = json.loads(line)
            if row.get("record_type", "trial") != "trial":
                continue
            t = row["prediction_order"]
            cr = json.loads(next(cands))
            assert cr["trial"] == t
            hit = bool(row["hit"])
            outcome = "correct" if hit else "silent" if row["predicted_edge"] is None else "wrong"
            keys = ["tasks", outcome]
            if outcome == "wrong":
                keys.append("selection_error" if cr["correct_gate_passed"] else "distinction_loss")
            if not cr["correct_gate_passed"]:
                keys.append("absent")
            b = t // BLOCK
            d = DAY.get(row.get("shop_cue"), "なし")
            for scope in ("全課題",) + (("ドア課題",) if row.get("held_out_is_door") else ()):
                for dd in (d, "全日"):
                    for k in keys:
                        c[(scope, dd, b, k)] += 1
    assert next(cands, None) is None
    return [[*k, v] for k, v in c.items()]


def q(v):
    if len(v) == 1:
        return v[0], v[0]
    qs = statistics.quantiles(v, n=4, method="inclusive")
    return qs[0], qs[2]


def plateau(series, rule):
    """series：区切り順の (平均, 四分位幅) の並び（None は統計なし）。rule による最初の区切りの番号、無ければ None。"""
    ok = []
    for i in range(1, len(series)):
        a, b = series[i - 1], series[i]
        if a is None or b is None:
            ok.append(False)
            continue
        diff = abs(b[0] - a[0])
        if rule == "lt":
            ok.append(diff < b[1])
        elif rule == "le":
            ok.append(diff <= b[1])
        else:  # iqr_prev
            ok.append(diff < a[1])
    for i in range(len(ok)):
        if all(ok[i:]):
            return i + 1
    return None


def write_csv(path, rows, fields):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in fields})


def label(b, last_trial):
    lo = b * BLOCK
    return f"{lo}〜{min(lo + BLOCK - 1, last_trial)}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--jobs", type=int, default=4)
    a = ap.parse_args()
    cfg = load_json(BASE / "configs.json")
    runs, _ = discover(cfg)
    runs = [r for r in runs if r["family"] == "古い主の条件"]
    assert all(r["seed"] not in range(21, 41) for r in runs)
    with ProcessPoolExecutor(max_workers=max(1, min(4, a.jobs))) as ex:
        results = list(ex.map(run_counts, runs))
    OUT.mkdir(exist_ok=True)
    per = {}
    for run, res in zip(runs, results):
        c = defaultdict(int)
        for s, d, b, k, v in res:
            c[(s, d, b, k)] = v
        per[(run["arm"], run["seed"])] = (run, c)
    nblocks = 1 + max(b for _, c in per.values() for (_, _, b, _) in c)
    last_trial = 1739
    arms = sorted({k[0] for k in per}, key=lambda x: (x[:2], x))
    # 一本ごと
    prow = []
    for (arm, seed), (run, c) in sorted(per.items()):
        for s in SCOPES:
            for d in DAYS:
                for b in range(nblocks):
                    n = c[(s, d, b, "tasks")]
                    r = {"condition": arm, "config": run["config"], "world": run["world"], "seed": seed, "scope": s, "day": d,
                         "block": b + 1, "trials": label(b, last_trial), **{k: c[(s, d, b, k)] for k in COUNT_KEYS}}
                    for m in METRICS:
                        r[f"rate_{m}"] = fmt(c[(s, d, b, m)] / n) if n else "NA"
                    prow.append(r)
    write_csv(OUT / "curves_per_seed.csv", prow, ["condition", "config", "world", "seed", "scope", "day", "block", "trials",
                                                  *COUNT_KEYS, *[f"rate_{m}" for m in METRICS]])
    # 種の平均とばらつき・落ち着く区切り
    srow, plrow = [], []
    for arm in arms:
        seeds = sorted(s for (a2, s) in per if a2 == arm)
        for s in SCOPES:
            for d in DAYS:
                for m in METRICS:
                    series = []
                    for b in range(nblocks):
                        tasks = [per[(arm, sd)][1][(s, d, b, "tasks")] for sd in seeds]
                        v = [per[(arm, sd)][1][(s, d, b, m)] / n for sd, n in zip(seeds, tasks) if n]
                        r = {"condition": arm, "scope": s, "day": d, "metric": f"rate_{m}", "block": b + 1,
                             "trials": label(b, last_trial), "n_seeds": len(v), "tasks_total": sum(tasks),
                             "tasks_per_seed_mean": fmt(statistics.fmean(tasks)), "tasks_per_seed_min": min(tasks),
                             "tasks_per_seed_max": max(tasks)}
                        if v:
                            q1, q3 = q(v)
                            mean = statistics.fmean(v)
                            r.update(mean=fmt(mean), q1=fmt(q1), q3=fmt(q3), iqr=fmt(q3 - q1), min=fmt(min(v)), max=fmt(max(v)))
                            series.append((mean, q3 - q1))
                        else:
                            r.update(mean="NA", q1="NA", q3="NA", iqr="NA", min="NA", max="NA")
                            series.append(None)
                        if b > 0 and series[-1] is not None and series[-2] is not None:
                            r["abs_diff_from_prev"] = fmt(abs(series[-1][0] - series[-2][0]))
                        srow.append(r)
                    pl = {"condition": arm, "scope": s, "day": d, "metric": f"rate_{m}",
                          "tasks_per_seed_per_block_mean": fmt(statistics.fmean(
                              per[(arm, sd)][1][(s, d, b, "tasks")] for sd in seeds for b in range(nblocks)))}
                    for key, rule in (("plateau_block", "lt"), ("alt_le_block", "le"), ("alt_iqr_prev_block", "iqr_prev")):
                        p = plateau(series, rule)
                        pl[key] = "なし" if p is None else p + 1
                        pl[key.replace("_block", "_trials")] = "" if p is None else label(p, last_trial)
                    pl["rule"] = ("|平均(b)−平均(b−1)| ＜ 四分位幅(b) が b 以降の全区切りで成り立つ最初の b（alt_le：≦、"
                                  "alt_iqr_prev：四分位幅(b−1) と ＜）")
                    plrow.append(pl)
    write_csv(OUT / "curves_summary.csv", srow, ["condition", "scope", "day", "metric", "block", "trials", "n_seeds", "mean",
                                                 "q1", "q3", "iqr", "min", "max", "abs_diff_from_prev", "tasks_total",
                                                 "tasks_per_seed_mean", "tasks_per_seed_min", "tasks_per_seed_max"])
    write_csv(OUT / "plateau.csv", plrow, ["condition", "scope", "day", "metric", "plateau_block", "plateau_trials",
                                           "alt_le_block", "alt_le_trials", "alt_iqr_prev_block", "alt_iqr_prev_trials",
                                           "tasks_per_seed_per_block_mean", "rule"])
    # 確かめ：区切りの和＝per_run.csv
    pr = {}
    arm_of = {(r["config"], r["world"]): r["arm"] for r in runs}
    for r in csv.DictReader(open(BASE / "out/per_run.csv", encoding="utf-8")):
        arm = arm_of.get((r["config"], int(r["world"])))
        if arm:
            pr[(arm, int(r["seed"]), r["scope"], r["day"])] = r
    cells = diffs = 0
    bad = []
    for (arm, seed), (run, c) in per.items():
        for s in SCOPES:
            for d in DAYS:
                ref = pr.get((arm, seed, s, d))
                for k in COUNT_KEYS:
                    cells += 1
                    tot = sum(c[(s, d, b, k)] for b in range(nblocks))
                    if ref is None or str(tot) != ref[k]:
                        diffs += 1
                        bad.append([arm, seed, s, d, k, tot, ref and ref[k]])
    chk = {"本": len(per), "区切り": nblocks, "突き合わせた数の欄": cells, "違い": diffs, "違いの例": bad[:20],
           "相手": "~/surface/out/per_run.csv（~/sme_analysis/out/error_types_*.csv と違い 0 を確かめ済みの表）"}
    (OUT / "check.json").write_text(json.dumps(chk, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({k: chk[k] for k in ("本", "区切り", "突き合わせた数の欄", "違い")}, ensure_ascii=False))


if __name__ == "__main__":
    main()

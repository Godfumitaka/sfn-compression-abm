"""第 1 波（新しい版 #1a〜#7b）の成績の表（受け箱の指示 44、理解の場の決定 1〜6、台帳 75 節）。読むだけ。

一本ごと（~/surface/wave1_view/<行>/q<行>_w<世界>/seedNNN、写しの選び方は wave1_view.py）：
  - 台帳（ledgers/cells/*/seedNNN.jsonl.gz）の試行の行から、正解（hit）・棄権（predicted_edge が無い）・誤答。日は shop_cue（e＝例外、n＝通常）、ドア課題は held_out_is_door。
  - 正答できる定義があるか（capable）：
      2a 以外：注意の記録 attention/<セル>/seedNNN.jsonl.gz の各行（試行ごと）の candidates に、gate_passed かつ hit の候補が一つ以上あるか。
      2a：注意の記録が無いので、再生（~/surface/replay/<arm>/seedNNN/sme.candidates.jsonl.gz、replay.json の status が ok）の correct_gate_passed。
    台帳と注意の記録は試行の番号で突き合わせ、数か番号が合わなければ、その本は「突き合わせの誤り」として数えない（理由を書く）。
  - 選び間違い＝誤答で capable、区別の喪失＝誤答で capable でない、正答できる定義の不在＝capable でない（全課題）。
  - 率は、全課題・全部の日を分母にする（決まり 1・6）。例外の日のドアの課題だけの率は並べて書くだけ。
比べ（決まり 1・6）：2a〜7a のそれぞれ 対 1a、世界ごと（6 × 2 世界 × 2 つの量 ＝ 24）。種 1〜20（a と b を合わせる）。
  差＝（比べる行の 20 種の平均）−（1a の 20 種の平均）。範囲＝同じ種の番号どうしを対にして、種を選び直す 4,000 回の百分位 2.5%・97.5%（乱数の種は固定、下の RNG_SEED）。
  判定＝「候補」（95% の範囲が 0 をまたがない）／「候補でない」。比（平均の比）と、例外の日のドアの課題だけの率は並べるだけ。
  20 種がそろっていない比べは「未完（n/20）」で、範囲と判定を出さない。
使い方：
  python3 ~/surface/wave1.py --check            道具が動くことだけを確かめる（読めた本の数・試行の数の突き合わせ・NA の欄と理由）。率は出さない
  python3 ~/surface/wave1.py --final --out DIR  表（per_run.csv・comparisons.csv・meta.json）を DIR に書く（10/10 06:00 からだけ使う、指示 44 の 4）
"""
import argparse
import csv
import glob
import gzip
import hashlib
import json
import math
import random
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

V = Path.home() / "surface/wave1_view"
REPLAY = Path.home() / "surface/replay"
ACCEPT = json.loads((Path.home() / "surface/replay_accept.json").read_text()) if (Path.home() / "surface/replay_accept.json").exists() else {}
RNG_SEED = 20261009
B = 4000
METRICS = ("selection_error", "absent")
ROWNAME = {"1": "全部入り_L50", "2": "基準_L50", "3": "注意を外す_L50", "4": "第二段をCに_L50", "5": "C*を外す_L50",
           "6": "logPを外す_L50", "7": "名前の忘却なし"}
DAY = {"e": "例外", "n": "通常"}


def rows_gz(p):
    with gzip.open(p, "rt", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                yield json.loads(line)


def one(d, pat):
    p = sorted(Path(d).glob(pat))
    return p[0] if len(p) == 1 else None


def capable_from_attention(run_dir, seed):
    a = one(run_dir, f"attention/*/seed{seed:03d}.jsonl.gz")
    if a is None:
        return None, "注意の記録が無い"
    cap = {}
    for r in rows_gz(a):
        t = r.get("trial")
        if t is None or t in cap:
            return None, f"注意の記録の試行の番号が無いか重なる（{t}）"
        cap[t] = any(c.get("gate_passed") and c.get("hit") for c in (r.get("candidates") or []))
    return cap, "注意の記録"


def capable_from_replay(arm, seed):
    d = REPLAY / arm / f"seed{seed:03d}"
    rj = d / "replay.json"
    if not rj.exists():
        return None, "再生の記録が無い"
    rep = json.loads(rj.read_text())
    # 指示 73 の 1：status が failed でも、replay_accept.py の確かめ（違いが設定の置き場の文字列だけで中身の sha256 が同じ）で採用した本は使う。
    acc = ACCEPT.get(f"{arm}/seed{seed:03d}", {})
    cf = d / "sme.candidates.jsonl.gz"
    if rep.get("status") != "ok" and acc.get("adopted"):
        cf = Path(acc["candidates_path"])   # 採用した本の候補の記録は、残した一時の置き場（replay_accept.json に置き場と sha256）
        if hashlib.sha256(cf.read_bytes()).hexdigest() != acc["candidates_sha256"]:
            return None, "採用した再生の候補の記録の sha256 が記録と違う"
    if not (rep.get("status") == "ok" or acc.get("adopted")) or not cf.exists():
        return None, f"再生が ok でない（{rep.get('status')}）"
    cap = {}
    for r in rows_gz(cf):
        cap[r["trial"]] = bool(r["correct_gate_passed"])
    return cap, f"再生 {rep.get('replay_code_commit', '')}"


def one_run(row, world, seed, run_name, version):
    arm = f"q{row}_w{world}"
    rd = V / row / arm / f"seed{seed:03d}"
    out = dict(row=row, world=world, seed=seed, run=run_name, version=version, status="", source="", trials=0)
    led = one(rd, f"ledgers/cells/*/seed{seed:03d}.jsonl.gz")
    if led is None:
        out["status"] = "NA：台帳が無い"
        return out, None
    cap, src = (capable_from_replay(arm, seed) if row[0] == "2" else capable_from_attention(rd, seed))
    out["source"] = src
    if cap is None:
        out["status"] = f"NA：{src}"
        return out, None
    counts = Counter()
    seen = []
    for r in rows_gz(led):
        if r.get("record_type", "trial") != "trial":
            continue
        t = r["prediction_order"]
        seen.append(t)
        if t not in cap:
            out["status"] = f"NA：突き合わせの誤り（台帳の試行 {t} が {src} に無い）"
            return out, None
        outcome = "correct" if r["hit"] else "silent" if r["predicted_edge"] is None else "wrong"
        c = cap[t]
        kinds = [outcome] + (["selection_error"] if outcome == "wrong" and c else []) + \
                (["distinction_loss"] if outcome == "wrong" and not c else []) + ([] if c else ["absent"])
        day = DAY.get(r.get("shop_cue"), "なし")
        for scope in ("全課題",) + (("ドア課題",) if r.get("held_out_is_door") else ()):
            for dd in (day, "全日"):
                counts[(scope, dd, "tasks")] += 1
                for k in kinds:
                    counts[(scope, dd, k)] += 1
    if len(seen) != len(cap) or sorted(seen) != sorted(cap):
        out["status"] = f"NA：突き合わせの誤り（台帳 {len(seen)} 試行、{src} {len(cap)} 試行）"
        return out, None
    out["status"] = "ok"
    out["trials"] = len(seen)
    return out, counts


def rate(c, scope, day, k):
    n = c.get((scope, day, "tasks"), 0)
    return c.get((scope, day, k), 0) / n if n else float("nan")


def boot_diff(x, y, rng):
    n = len(x)
    ds = []
    for _ in range(B):
        idx = [rng.randrange(n) for _ in range(n)]
        ds.append(sum(x[i] for i in idx) / n - sum(y[i] for i in idx) / n)
    ds.sort()
    return ds[int(math.floor(0.025 * B))], ds[int(math.ceil(0.975 * B)) - 1]


def mean(v):
    v = [a for a in v if not math.isnan(a)]
    return sum(v) / len(v) if v else float("nan")


def fmt(x):
    return "NA" if x is None or (isinstance(x, float) and math.isnan(x)) else f"{x:.6f}"


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--check", action="store_true")
    g.add_argument("--final", action="store_true")
    ap.add_argument("--out")
    a = ap.parse_args()
    sel = list(csv.DictReader(open(V / "selection.tsv"), delimiter="\t"))
    per, counts = [], {}
    for s in sel:
        if not s["run"]:
            per.append(dict(row=s["row"], world=int(s["world"]), seed=int(s["seed"]), run="", version="", status="未完（持ち帰っていない）", source="", trials=0))
            continue
        o, c = one_run(s["row"], int(s["world"]), int(s["seed"]), s["run"], s["version"])
        per.append(o)
        if c is not None:
            counts[(s["row"][0], int(s["world"]), int(s["seed"]))] = c
    if a.check:
        st = Counter(p["status"] if not p["status"].startswith("NA") else p["status"].split("（")[0] for p in per)
        print("本の状態：", dict(st))
        print("読めた本（ok）の試行の数：", Counter(p["trials"] for p in per if p["status"] == "ok"))
        for p in per:
            if p["status"].startswith("NA"):
                print("NA の本：", p["row"], p["world"], p["seed"], p["run"], p["status"])
        print("出どころ：", Counter(p["source"] for p in per if p["status"] == "ok"))
        return
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    pf = ["row", "world", "seed", "run", "version", "status", "source", "trials", "tasks",
          "rate_selection_error", "rate_absent", "rate_distinction_loss", "rate_wrong", "rate_silent", "rate_correct",
          "door_exception_tasks", "door_exception_rate_selection_error", "door_exception_rate_absent"]
    with open(out / "per_run.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=pf)
        w.writeheader()
        for p in per:
            c = counts.get((p["row"][0], p["world"], p["seed"]))
            r = dict(p)
            if c:
                r.update(tasks=c[("全課題", "全日", "tasks")], **{f"rate_{k}": fmt(rate(c, "全課題", "全日", k)) for k in
                         ("selection_error", "absent", "distinction_loss", "wrong", "silent", "correct")},
                         door_exception_tasks=c.get(("ドア課題", "例外", "tasks"), 0),
                         door_exception_rate_selection_error=fmt(rate(c, "ドア課題", "例外", "selection_error")),
                         door_exception_rate_absent=fmt(rate(c, "ドア課題", "例外", "absent")))
            w.writerow(r)
    cf = ["row", "row_config", "vs", "world", "metric", "n_seeds_both", "status", "mean_row", "mean_1a", "diff",
          "ci95_lo", "ci95_hi", "judgment", "ratio_of_means", "door_exception_mean_row", "door_exception_mean_1a",
          "boot_resamples", "rng_seed"]
    comps = []
    for r in "234567":
        for wd in (1, 2):
            both = [s for s in range(1, 21) if (r, wd, s) in counts and ("1", wd, s) in counts]
            for m in METRICS:
                x = [rate(counts[(r, wd, s)], "全課題", "全日", m) for s in both]
                y = [rate(counts[("1", wd, s)], "全課題", "全日", m) for s in both]
                xd = [rate(counts[(r, wd, s)], "ドア課題", "例外", m) for s in both]
                yd = [rate(counts[("1", wd, s)], "ドア課題", "例外", m) for s in both]
                mx, my = mean(x), mean(y)
                row = dict(row=f"{r}a/{r}b", row_config=ROWNAME[r], vs="1a/1b（全部入り_L50）", world=wd, metric=m,
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
    with open(out / "comparisons.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cf)
        w.writeheader()
        w.writerows(comps)
    meta = dict(made_at=datetime.now().isoformat(timespec="seconds"), rule="受け箱の指示 44、理解の場の決定 1〜6、台帳 75 節",
                rng_seed=RNG_SEED, rng_note="比べごとに random.Random(f'{RNG_SEED}-{行}-{世界}-{量}') で選び直す",
                resamples=B, percentiles=[2.5, 97.5], denominators="全課題・全部の日",
                replay_adoption="2a の再生は、status が ok の本と、replay_accept.json で採用した本（違いが flag.json の config の置き場の書き方だけ：本番は AWS の /home/ubuntu/wave1/...、再生はデスクトップの /home/tatsu/cloud/wave1/...。設定ファイルの中身の sha256 は各本で同じ）を使う",
                                capable_definition={"2a 以外": "注意の記録の candidates に gate_passed かつ hit の候補がある",
                                    "2a": "再生（selcands_sme）の候補の記録の correct_gate_passed"},
                selection="~/surface/wave1_view/selection.tsv（wave1_view.py の選び方）",
                runs_ok=sum(1 for p in per if p["status"] == "ok"), runs_total=len(per))
    (out / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"表を書いた：{out}（読めた本 {meta['runs_ok']}/{meta['runs_total']}）")


if __name__ == "__main__":
    sys.exit(main())

"""動詞の「試行 1〜1000 の窓」が全長をどれだけ映すかの確かめ（受け箱の指示 85、探索。記録を読むだけ）。

使う本（~/cloud/ops/verb_fetched.tsv の state が completed のものだけ。#19 の本は読まない・開かない）：
  - 22c（基準）：22_seedNNN_birth0
  - #21（D＋注意 τ0.4）：21_seed001・002・003・005・006・009、と 008・010（完走していれば）
  - #21b（τ0.15）：21b_seedNNN
包み（/mnt/d/sfn_runs/cloud/verb/<機械>/<根>/<本>.tar.gz）を流しながら読み、同じ読みで sha256 を表と突き合わせる。
包みから読むのは spec.json・status.json・result.json・output/flag.json・台帳（ledgers/cells/*/seedNNN.jsonl.gz）・
注意の記録（attention/*/seedNNN.jsonl.gz、#21・#21b だけにある）だけ。展開した写しは作らない。

一試行の分け方（~/surface/wave1.py と同じ）：
  - 正解＝台帳の hit、棄権＝predicted_edge が無い、誤答＝それ以外。
  - capable（正答できる定義がある）：
      #21・#21b：注意の記録の candidates に gate_passed かつ hit の候補が一つ以上ある（wave1.py と同じ）。
      22c：注意の記録が無い（--attn-sme なし）。再生（tools/verb/analyze.py や selcands_sme の答え直し）は計算なので、ここでは行わない。
           代わりに台帳だけで「台帳の門の定義」：hit＝1、または counterfactual_predictions（選ばれなかった τ 門通過の定義
           tau_passed_defs ごとの答え直し、abm/loop.py・tools/v39.py の counterfactuals）に hit＝1 がある。
           同じ台帳の定義を全部の本で並べて出し（*_ledgerdef）、#21・#21b では注意の記録との一致の試行数も出す。
  - 選び間違い＝誤答で capable、区別の喪失＝誤答で capable でない、定義の不在＝capable でない（全課題）。
  - 率の分母は、その窓の全課題（試行）。
試行の番号は台帳の prediction_order＋1（prediction_order 0 が試行 1）。
動詞ごと：held_out_is_past が真の課題（過去形を問う課題）のうち、predicted_edge の predicate が REG の数。
  頻度の順＝tools/verbworld.py の training_items("default") の確率（規則 Vj＝0.30/(H32·j)、不規則 V(32+k)＝0.70/(H8·k)）の降順。

使い方：nice -n 15 python3 verb_window.py --out DIR [--workers 3]
"""
import argparse
import csv
import gzip
import hashlib
import json
import re
import sys
import tarfile
import time
from collections import Counter, defaultdict
from datetime import datetime
from multiprocessing import Pool
from pathlib import Path

TSV = Path.home() / "cloud/ops/verb_fetched.tsv"
ARCH = Path("/mnt/d/sfn_runs/cloud/verb")
FORBID = re.compile(r"(^19_|19_seed|prefix_gate|gate100_|production34)")
ALLOW = re.compile(r"^(22_seed(\d{3})_birth0|21_seed(\d{3})|21b_seed(\d{3}))$")
SEEDS21 = {1, 2, 3, 5, 6, 9, 8, 10}
N = 5000
WINDOWS = [("1-1000", 1, 1000), ("1-5000", 1, 5000), ("1001-5000", 1001, 5000)]
BLOCKS = [(f"{a}-{a + 499}", a, a + 499) for a in range(1, N + 1, 500)]
ARMS = ("22c", "#21", "#21b")
KINDS = ("correct", "wrong", "silent", "selection_error", "distinction_loss", "absent",
         "selection_error_ledgerdef", "distinction_loss_ledgerdef", "absent_ledgerdef")


def verb_items():
    h32 = sum(1 / k for k in range(1, 33))
    h8 = sum(1 / k for k in range(1, 9))
    items = [(f"V{j:02d}", "regular", "REG", .30 / (h32 * j)) for j in range(1, 33)] + \
            [(f"V{k + 32:02d}", "irregular", f"IRR_{k}", .70 / (h8 * k)) for k in range(1, 9)]
    items.sort(key=lambda x: (-x[3], x[0]))
    return items


VERBS = verb_items()
RANK = {v[0]: i + 1 for i, v in enumerate(VERBS)}


def select_runs():
    runs = []
    for line in TSV.read_text().splitlines():
        f = line.split("\t")
        if len(f) < 5:
            continue
        mr, state, when, sha, nfiles = f[:5]
        machine, rc = mr.split(":", 1)
        root, case = rc.rsplit("/", 1)
        if FORBID.search(case) or FORBID.search(root):
            continue                      # #19 の本は名前を見るだけで外す（開かない）
        m = ALLOW.match(case)
        if not m or state != "completed":
            continue
        if m.group(2):
            arm, seed = "22c", int(m.group(2))
        elif m.group(3):
            arm, seed = "#21", int(m.group(3))
            if seed not in SEEDS21:
                continue
        else:
            arm, seed = "#21b", int(m.group(4))
        runs.append(dict(arm=arm, seed=seed, case=case, machine=machine, root=root, fetched=when,
                         sha256=sha, tsv_files=int(nfiles), path=str(ARCH / machine / root / f"{case}.tar.gz")))
    runs.sort(key=lambda r: (ARMS.index(r["arm"]), r["seed"]))
    return runs


def not_used():
    """表にある 22c・#21・#21b の行のうち使わなかったもの（状態つき）。#19 の行は書かない。"""
    used = {(r["machine"], r["root"], r["case"]) for r in select_runs()}
    rows = []
    for line in TSV.read_text().splitlines():
        f = line.split("\t")
        if len(f) < 5:
            continue
        machine, rc = f[0].split(":", 1)
        root, case = rc.rsplit("/", 1)
        if FORBID.search(case) or FORBID.search(root) or not ALLOW.match(case) or (machine, root, case) in used:
            continue
        rows.append(f"{machine}:{root}/{case}　{f[1]}")
    return rows


class HashReader:
    def __init__(self, f):
        self.f, self.h, self.n = f, hashlib.sha256(), 0

    def read(self, n=-1):
        b = self.f.read(n)
        self.h.update(b)
        self.n += len(b)
        return b

    def drain(self):
        while self.read(1 << 22):
            pass


def lines(fobj):
    with gzip.GzipFile(fileobj=fobj) as g:
        for raw in g:
            if raw.strip():
                yield json.loads(raw)


def read_ledger(fobj):
    header, rows = None, {}
    for r in lines(fobj):
        if r.get("record_type", "trial") == "run_header":
            header = r
            continue
        if r.get("record_type", "trial") != "trial":
            continue
        t = r["prediction_order"]
        if t in rows:
            raise RuntimeError(f"台帳の試行 {t} が重なる")
        pe = r.get("predicted_edge")
        outcome = "correct" if r["hit"] else "silent" if pe is None else "wrong"
        cap_led = bool(r["hit"]) or any(c.get("hit") for c in (r.get("counterfactual_predictions") or []))
        rows[t] = (outcome, cap_led, bool(r["held_out_is_past"]), r["verb_name"], r["verb_class"], r["correct_past"],
                   (pe or {}).get("predicate"))
    return header, rows


def read_attention(fobj):
    cap = {}
    for r in lines(fobj):
        t = r.get("trial")
        if t is None or t in cap:
            raise RuntimeError(f"注意の記録の試行の番号が無いか重なる（{t}）")
        cap[t] = any(c.get("gate_passed") and c.get("hit") for c in (r.get("candidates") or []))
    return cap


def one_run(run):
    t0 = time.time()
    out = dict(run)
    case = run["case"]
    seed = run["seed"]
    led_re = re.compile(rf"^{re.escape(case)}/output/ledgers/cells/[^/]+/seed{seed:03d}\.jsonl\.gz$")
    att_re = re.compile(rf"^{re.escape(case)}/output/attention/[^/]+/seed{seed:03d}\.jsonl\.gz$")
    small = {f"{case}/spec.json": "spec", f"{case}/status.json": "status", f"{case}/result.json": "result",
             f"{case}/output/flag.json": "flag"}
    meta, ledger, attn, members, led_names, att_names = {}, None, None, 0, [], []
    with open(run["path"], "rb", buffering=16 << 20) as raw:   # drvfs では小さい読みが遅いので大きく読む
        hr = HashReader(raw)
        with tarfile.open(fileobj=hr, mode="r|gz") as tar:
            for m in tar:
                if not (m.name == case or m.name.startswith(case + "/")):
                    raise RuntimeError(f"包みに別の本の名前がある：{m.name}")
                if m.isfile():
                    members += 1
                if m.name in small:
                    meta[small[m.name]] = json.loads(tar.extractfile(m).read())
                elif led_re.match(m.name):
                    led_names.append(m.name)
                    ledger = read_ledger(tar.extractfile(m))
                elif att_re.match(m.name):
                    att_names.append(m.name)
                    attn = read_attention(tar.extractfile(m))
        hr.drain()
    out["sha256_read"] = hr.h.hexdigest()
    out["bytes"] = hr.n
    out["files_in_archive"] = members
    out["ledger_member"] = led_names
    out["attention_member"] = att_names
    out["meta"] = meta
    out["seconds"] = round(time.time() - t0, 1)
    if out["sha256_read"] != run["sha256"]:
        out["status"] = "NA：sha256 が表と違う"
        return out
    if len(led_names) != 1:
        out["status"] = f"NA：台帳が {len(led_names)} 本"
        return out
    header, rows = ledger
    out["ledger_header"] = {k: header.get(k) for k in ("code_commit", "run_seed", "trial_count", "world_hash")} if header else None
    if sorted(rows) != list(range(N)):
        out["status"] = f"NA：台帳の試行が 0〜{N - 1} でない（{len(rows)} 行）"
        return out
    if run["arm"] != "22c":
        if attn is None or len(att_names) != 1:
            out["status"] = "NA：注意の記録が無い"
            return out
        if sorted(attn) != list(range(N)):
            out["status"] = f"NA：突き合わせの誤り（注意の記録 {len(attn)} 試行）"
            return out
    elif attn is not None:
        out["status"] = "NA：22c に注意の記録がある（想定と違う）"
        return out
    trials = []
    for t in range(N):
        outcome, cap_led, past, verb, cls, cpast, ans = rows[t]
        cap = attn[t] if attn is not None else cap_led
        trials.append((t + 1, outcome, cap, cap_led, past, verb, cls, cpast, ans))
    out["trials"] = trials
    out["capable_source"] = "attention" if attn is not None else "ledger_counterfactual"
    out["status"] = "ok"
    return out


def kinds_of(outcome, cap, cap_led):
    k = [outcome]
    if outcome == "wrong":
        k.append("selection_error" if cap else "distinction_loss")
        k.append("selection_error_ledgerdef" if cap_led else "distinction_loss_ledgerdef")
    if not cap:
        k.append("absent")
    if not cap_led:
        k.append("absent_ledgerdef")
    return k


def window_counts(trials, a, b):
    c = Counter()
    for tr in trials:
        t, outcome, cap, cap_led = tr[:4]
        if a <= t <= b:
            c["tasks"] += 1
            c["cap_agree"] += int(cap == cap_led)
            for k in kinds_of(outcome, cap, cap_led):
                c[k] += 1
    return c


def verb_counts(trials, a, b):
    c = defaultdict(Counter)
    for t, outcome, cap, cap_led, past, verb, cls, cpast, ans in trials:
        if not (a <= t <= b) or not past:
            continue
        x = c[verb]
        x["past_tasks"] += 1
        if ans is None:
            x["abstain"] += 1
        else:
            x["answered"] += 1
            if ans == "REG":
                x["REG"] += 1
            if outcome == "correct":
                x["correct"] += 1
            elif ans != "REG":
                x["other"] += 1
            if outcome == "wrong" and ans == "REG":
                x["REG_wrong"] += 1
    return c


def fmt(x, nd=6):
    return "" if x is None else f"{x:.{nd}f}"


def div(a, b):
    return a / b if b else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--workers", type=int, default=3)
    args = ap.parse_args()
    out = args.out
    out.mkdir(parents=True, exist_ok=True)
    runs = select_runs()
    for r in runs:
        assert not FORBID.search(r["case"]) and not FORBID.search(r["path"])
    print(f"{len(runs)} 本", flush=True)
    with Pool(args.workers) as pool:
        res = []
        for r in pool.imap(one_run, runs):
            print(r["arm"], r["case"], r["status"], r["seconds"], "s", flush=True)
            res.append(r)
    ok = [r for r in res if r["status"] == "ok"]

    # 1・3：本ごと、窓ごと／500 ごと
    cols = ["arm", "seed", "case", "window", "trial_from", "trial_to", "tasks", "capable_source"] + \
           [f"n_{k}" for k in KINDS] + [f"rate_{k}" for k in KINDS] + ["cap_agree_attention_vs_ledgerdef"]
    per = {}
    for name, rows_spec, fn in (("per_run_windows.csv", WINDOWS, None), ("per_run_blocks500.csv", BLOCKS, None)):
        with open(out / name, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(cols)
            for r in ok:
                for wn, a, b in rows_spec:
                    c = window_counts(r["trials"], a, b)
                    per[(r["case"], wn)] = c
                    w.writerow([r["arm"], r["seed"], r["case"], wn, a, b, c["tasks"], r["capable_source"]] +
                               [c[k] for k in KINDS] + [fmt(div(c[k], c["tasks"])) for k in KINDS] +
                               [c["cap_agree"] if r["capable_source"] == "attention" else ""])

    # 腕ごとの平均（種の平均）と、合わせた数
    def arm_rows(spec):
        rows = []
        for arm in ARMS:
            rs = [r for r in ok if r["arm"] == arm]
            for wn, a, b in spec:
                cs = [per[(r["case"], wn)] for r in rs]
                tot = sum(cs, Counter())
                row = dict(arm=arm, window=wn, trial_from=a, trial_to=b, runs=len(rs),
                           seeds=" ".join(str(r["seed"]) for r in rs), tasks=tot["tasks"])
                for k in KINDS:
                    row[f"n_{k}"] = tot[k]
                    row[f"mean_rate_{k}"] = fmt(sum(c[k] / c["tasks"] for c in cs) / len(cs)) if cs else ""
                rows.append(row)
        return rows

    arm_cols = ["arm", "window", "trial_from", "trial_to", "runs", "seeds", "tasks"] + \
               [f"n_{k}" for k in KINDS] + [f"mean_rate_{k}" for k in KINDS]
    arm_w = arm_rows(WINDOWS)
    for name, spec in (("arm_windows.csv", WINDOWS), ("arm_blocks500.csv", BLOCKS)):
        with open(out / name, "w", newline="") as f:
            w = csv.DictWriter(f, arm_cols)
            w.writeheader()
            w.writerows(arm_w if spec is WINDOWS else arm_rows(spec))

    # 2：動詞ごとの REG（頻度の順）
    vcols = ["arm", "seed", "case", "window", "trial_from", "trial_to", "freq_rank", "verb", "verb_class", "correct_past",
             "probability", "past_tasks", "answered", "abstain", "REG", "correct", "other",
             "share_REG_of_past_tasks", "share_REG_of_answered", "REG_over_correct_plus_REG"]

    def vrow(prefix, c, verb):
        x = c.get(verb, Counter())
        _, cls, cpast, p = next(v for v in VERBS if v[0] == verb)
        return prefix + [RANK[verb], verb, cls, cpast, f"{p:.6f}", x["past_tasks"], x["answered"], x["abstain"], x["REG"],
                         x["correct"], x["other"], fmt(div(x["REG"], x["past_tasks"]), 4),
                         fmt(div(x["REG"], x["answered"]), 4), fmt(div(x["REG"], x["correct"] + x["REG"]), 4)]

    for name, spec in (("per_verb_REG_windows.csv", WINDOWS), ("per_verb_REG_blocks500.csv", BLOCKS)):
        with open(out / name, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(vcols)
            for r in ok:
                for wn, a, b in spec:
                    c = verb_counts(r["trials"], a, b)
                    for v in VERBS:
                        w.writerow(vrow([r["arm"], r["seed"], r["case"], wn, a, b], c, v[0]))
    with open(out / "arm_verb_REG_windows.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["arm", "runs", "window", "trial_from", "trial_to"] + vcols[6:])
        for arm in ARMS:
            rs = [r for r in ok if r["arm"] == arm]
            for wn, a, b in WINDOWS:
                c = defaultdict(Counter)
                for r in rs:
                    for v, x in verb_counts(r["trials"], a, b).items():
                        c[v].update(x)
                for v in VERBS:
                    w.writerow(vrow([arm, len(rs), wn, a, b], c, v[0]))

    # (a) 向き：腕の平均の差（D＋注意 − 基準）の符号を、窓 1〜1000 と全長で比べる
    def sign(x):
        return 0 if abs(x) < 1e-15 else (1 if x > 0 else -1)

    am = {(r["arm"], r["window"]): r for r in arm_w}
    dcols = ["metric", "compare", "mean_base_1-1000", "mean_D_1-1000", "diff_1-1000", "mean_base_1-5000", "mean_D_1-5000",
             "diff_1-5000", "diff_1001-5000", "same_sign_1-1000_vs_1-5000", "same_sign_1-1000_vs_1001-5000",
             "paired_seeds", "paired_same_sign_1-1000_vs_1-5000"]
    direction = []
    for k in KINDS:
        for d in ("#21", "#21b"):
            g = {wn: (float(am[("22c", wn)][f"mean_rate_{k}"]), float(am[(d, wn)][f"mean_rate_{k}"])) for wn, _, _ in WINDOWS}
            diffs = {wn: g[wn][1] - g[wn][0] for wn in g}
            base = {r["seed"]: r for r in ok if r["arm"] == "22c"}
            pairs = [(base[r["seed"]], r) for r in ok if r["arm"] == d and r["seed"] in base]
            same = 0
            for b_, d_ in pairs:
                s1 = sign(per[(d_["case"], "1-1000")][k] / N * 5 - per[(b_["case"], "1-1000")][k] / N * 5)
                s5 = sign(per[(d_["case"], "1-5000")][k] / N - per[(b_["case"], "1-5000")][k] / N)
                same += int(s1 == s5)
            direction.append({"metric": k, "compare": f"{d} − 22c",
                              "mean_base_1-1000": fmt(g["1-1000"][0]), "mean_D_1-1000": fmt(g["1-1000"][1]),
                              "diff_1-1000": fmt(diffs["1-1000"]), "mean_base_1-5000": fmt(g["1-5000"][0]),
                              "mean_D_1-5000": fmt(g["1-5000"][1]), "diff_1-5000": fmt(diffs["1-5000"]),
                              "diff_1001-5000": fmt(diffs["1001-5000"]),
                              "same_sign_1-1000_vs_1-5000": int(sign(diffs["1-1000"]) == sign(diffs["1-5000"])),
                              "same_sign_1-1000_vs_1001-5000": int(sign(diffs["1-1000"]) == sign(diffs["1001-5000"])),
                              "paired_seeds": " ".join(str(d_["seed"]) for _, d_ in pairs),
                              "paired_same_sign_1-1000_vs_1-5000": f"{same}/{len(pairs)}"})
    with open(out / "direction_a.csv", "w", newline="") as f:
        w = csv.DictWriter(f, dcols)
        w.writeheader()
        w.writerows(direction)

    # (b) 誤りのうち試行 1〜1000 に入る割合
    ecols = ["arm", "seed", "case", "metric", "n_1-1000", "n_1-5000", "n_1001-5000", "share_in_1-1000"]
    EK = ("wrong", "silent", "wrong_or_silent", "selection_error", "absent", "selection_error_ledgerdef", "absent_ledgerdef")
    with open(out / "error_share_b.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(ecols)
        for arm in ARMS:
            tot = defaultdict(Counter)
            for r in [r for r in ok if r["arm"] == arm]:
                for k in EK:
                    n1, n5, n15 = (per[(r["case"], wn)][k] if k != "wrong_or_silent" else
                                   per[(r["case"], wn)]["wrong"] + per[(r["case"], wn)]["silent"] for wn in ("1-1000", "1-5000", "1001-5000"))
                    tot[k].update({"1": n1, "5": n5, "15": n15})
                    w.writerow([arm, r["seed"], r["case"], k, n1, n5, n15, fmt(div(n1, n5), 4)])
            for k in EK:
                w.writerow([arm, "all", "(合計)", k, tot[k]["1"], tot[k]["5"], tot[k]["15"], fmt(div(tot[k]["1"], tot[k]["5"]), 4)])

    # meta
    script = Path(__file__).resolve()
    meta = {
        "made_at": datetime.now().isoformat(timespec="seconds"),
        "kind": "探索（受け箱の指示 85、理解の場の決定 10/9 18:39 の動詞の予想の形。記録を読むだけ。判定はしない）",
        "rule": "#19（全部入り）の本・関門（19_・19_seed・prefix_gate・gate100_・production34）は名前で外し、包みを開いていない。窓 1〜1000 は #19 を見る前の約束（D-07επ）",
        "script": f"{script.name}（nice -n 15 python3 {script.name} --out . --workers {args.workers}）",
        "script_sha256": hashlib.sha256(script.read_bytes()).hexdigest(),
        "sources": {
            "index": str(TSV), "index_sha256": hashlib.sha256(TSV.read_bytes()).hexdigest(),
            "archives": "/mnt/d/sfn_runs/cloud/verb/<機械>/<根>/<本>.tar.gz を流しながら読み、同じ読みで sha256 を表と突き合わせた（展開の写しは作らない）",
            "members_read": ["<本>/spec.json", "<本>/status.json", "<本>/result.json", "<本>/output/flag.json",
                             "<本>/output/ledgers/cells/<セル>/seedNNN.jsonl.gz",
                             "<本>/output/attention/<セル>/seedNNN.jsonl.gz（#21・#21b だけ）"],
            "record_format": "台帳と注意の記録の欄は、包みの道具（~/v33prod/results/control/動詞_クラウドの包み_2026-10-09/instruction27/）と、"
                             "版の源（~/sfn/sfn-compression-abm を git archive で /mnt/d に写した 94dbebc（#21 の包みの版）・6e4bcba（22c の包みの版）。"
                             "台帳の code_commit は 4dc6a05）の abm/loop.py・tools/v39.py・tools/attnsme.py・tools/verbworld.py・tools/verb/analyze.py で確かめた",
        },
        "definitions": {
            "trial": "台帳の prediction_order＋1（試行 1〜5000）。窓：1-1000・1-5000・1001-5000、と 500 ごと",
            "tasks": "窓の中の全試行（全課題）。率の分母",
            "correct": "台帳の hit＝1",
            "silent": "台帳の predicted_edge が無い（棄権）",
            "wrong": "それ以外（predicted_edge があって hit＝0）",
            "capable": {
                "#21・#21b": "注意の記録の candidates に gate_passed（support ≥ need(tau_acc, n)、tools/attnsme.py）かつ hit の候補が一つ以上ある（~/surface/wave1.py と同じ）",
                "22c": "注意の記録が無い（--attn-sme なし）。台帳だけの定義 capable_ledgerdef を使う：台帳の hit＝1、または counterfactual_predictions"
                       "（tau_passed_defs のうち選ばれなかった定義ごとの答え直し、tools/v39.py の counterfactuals）のどれかの hit＝1。"
                       "再生（selcands・tools/verb/analyze.py の答え直し）は計算なのでしていない",
            },
            "selection_error（選び間違い）": "wrong かつ capable",
            "distinction_loss（区別の喪失）": "wrong かつ capable でない",
            "absent（定義の不在）": "capable でない（全課題）",
            "*_ledgerdef": "capable_ledgerdef で数えた同じ量。全部の本で同じ定義。#21・#21b では cap_agree_attention_vs_ledgerdef に、注意の記録の capable と一致した試行の数",
            "rate_*": "n_* ÷ tasks",
            "mean_rate_*": "腕の中の本ごとの率の単純平均（種の平均）",
            "past_task": "台帳の held_out_is_past が真（伏せた辺が過去形の hold の席）",
            "REG": "past_task のうち predicted_edge の predicate が REG（引数は問わない）",
            "share_REG_of_past_tasks": "REG ÷ past_tasks（棄権も分母に入る。tools/verb/analyze.py の REG_all_queries_rate と同じ形）",
            "share_REG_of_answered": "REG ÷ answered（答えた past_task だけ）",
            "REG_over_correct_plus_REG": "REG ÷ (correct＋REG)（analyze.py の marcus_rate と同じ形。規則動詞では REG が正解なので 1）",
            "freq_rank": "tools/verbworld.py training_items('default') の確率の降順（規則 Vj＝0.30/(H32·j)、不規則 V(32+k)＝0.70/(H8·k)）。flag.json の verb_variant＝default・verb_frequencies＝null を本ごとに確かめた",
            "direction_a": "腕の平均の差（#21 または #21b の mean_rate − 22c の mean_rate）の符号を、1-1000 と 1-5000（と 1001-5000）で比べた。"
                           "paired は同じ種の番号どうしの差の符号（1-1000 と 1-5000）が同じだった種の数",
            "error_share_b": "n_1-1000 ÷ n_1-5000（試行の 20% が 1-1000）",
        },
        "fields": {"per_run_windows.csv / per_run_blocks500.csv": cols, "arm_windows.csv / arm_blocks500.csv": arm_cols,
                   "per_verb_REG_windows.csv / per_verb_REG_blocks500.csv": vcols, "direction_a.csv": dcols, "error_share_b.csv": ecols},
        "verbs_frequency_order": [dict(rank=RANK[v[0]], verb=v[0], verb_class=v[1], correct_past=v[2], probability=round(v[3], 6)) for v in VERBS],
        "runs": [{k: r.get(k) for k in ("arm", "seed", "case", "machine", "root", "fetched", "sha256", "sha256_read", "bytes",
                                        "tsv_files", "files_in_archive", "status", "capable_source", "ledger_member",
                                        "attention_member", "ledger_header", "seconds")} |
                 {"spec_arm": (r.get("meta", {}).get("spec") or {}).get("arm"),
                  "spec_source_commit": (r.get("meta", {}).get("spec") or {}).get("source_commit"),
                  "status_json": r.get("meta", {}).get("status"),
                  "result_exit_code": (r.get("meta", {}).get("result") or {}).get("exit_code"),
                  "flag_commit": (r.get("meta", {}).get("flag") or {}).get("commit"),
                  "flag_verb_variant": (r.get("meta", {}).get("flag") or {}).get("verb_variant"),
                  "flag_verb_frequencies": (r.get("meta", {}).get("flag") or {}).get("verb_frequencies"),
                  "flag_attn_sme": (r.get("meta", {}).get("flag") or {}).get("attn_sme"),
                  "flag_use_forget": (r.get("meta", {}).get("flag") or {}).get("use_forget")}
                 for r in res],
        "runs_not_used": not_used(),
    }
    (out / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n")
    print("done", flush=True)


if __name__ == "__main__":
    main()

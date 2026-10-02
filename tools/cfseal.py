"""C の「6%」の中身（委任書「シールを戻す確かめ」2026-10-02 昼の 2）。★ 記録を読むだけ。
対象：世界 2 の C（λ＝0.0187・0.099）。種 1〜20。
(1) --cf-value の記録（side の cfvalue.jsonl。開示のあった試行で、選ばれた定義のシールの席を一段薄くした写しで答え直した利益）を、
    課題の種類（ドア／ドア以外）× その日（通常／例外）で分ける。課題の種類とその日は台帳の行（held_out_is_door・shop_cue）から。
    内訳ごとに：評価した回数、利益が正・0・負の回数、利益の合計（ビット）。一段の種類（FH・HU）でも分ける。
(2) --cf-learn の記録（cflearn.jsonl。席ごとに、F・H・U のそれぞれで最終的な答えの書き直し費用）のうち、シールの席
    （shop.jsonl の shop_seat で which＝sig の (定義名, 登録試行, 席) が、その試行に生きていたもの）を、同じ内訳で：評価した回数、「U − H」が正の回数と合計、「H − F」が正の回数と合計。
(3) シールの席の保持の判断：v39 の記録の conv（薄くした判断ごとの V と空くビット）のうち、同じ試行に shop.jsonl でシールの席の状態が
    移った (定義, 席) のもの。V＝num／空くビット（tools/v310be.py candidates。num は FH なら R̄H − R̄F、HU なら R̄U − R̄H）。薄くする条件は V＜λ。
    差＝(λ − V)×空くビット（ビット。正なら値段のほうが大きかった分）と、λ − V を、種類ごとに分布で出す。
    あわせて、--cf-value の記録にある、シールの席の評価の時点の V と λ の比べ（V＜λ の回数・V≧λ の回数）。
使い方  python3.12 tools/cfseal.py <出力の .json> <腕の根> …"""
import glob
import gzip
import json
import os
import sys
from collections import Counter, defaultdict
from statistics import quantiles


def q5(xs):
    if not xs:
        return None
    if len(xs) < 2:
        return [round(xs[0], 4)] * 5
    q = quantiles(xs, n=4, method="inclusive")
    return [round(v, 4) for v in (min(xs), q[0], q[1], q[2], max(xs))]


def task_of(root, cell, seed):
    out = {}
    with gzip.open(os.path.join(root, "ledgers", "cells", cell, f"seed{seed:03d}.jsonl.gz"), "rt", encoding="utf-8") as f:
        next(f)
        for t, line in enumerate(f):
            d = json.loads(line)
            if d.get("record_type", "trial") != "trial":
                continue
            out[t] = ("ドア" if d.get("held_out_is_door") else "ドア以外", "通常" if d.get("shop_cue") == "n" else "例外")
    return out


def main():
    out = sys.argv[1]
    res = {}
    for root in sys.argv[2:]:
        arm = os.path.basename(root.rstrip("/"))
        lam = json.load(open(os.path.join(root, "flag.json")))["v39_price"]
        cv = defaultdict(lambda: {"回数": 0, "正": 0, "0": 0, "負": 0, "合計": 0.0})
        cl = defaultdict(lambda: {"回数": 0, "U−H が正": 0, "U−H の合計": 0.0, "H−F が正": 0, "H−F の合計": 0.0, "F の席": 0})
        trans = defaultdict(lambda: {"margin": [], "lamV": [], "num": [], "dc": []})
        vcmp = Counter()
        allT = Counter()
        checkT = Counter()
        for p in sorted(glob.glob(os.path.join(root, "ledgers/cells/*/seed*.done"))):
            seed = int(os.path.basename(p)[4:7])
            if not 1 <= seed <= 20:
                continue
            cell = os.path.basename(os.path.dirname(p))
            side = os.path.join(root, "side", cell)
            tk = task_of(root, cell, seed)
            # ★ 確かめ：台帳の行の試行番号（行の並び）と、side の試行番号が同じ数え方か（行の数＝1,740）
            checkT[len(tk)] += 1
            span = {}
            sig_t = set()
            for line in open(os.path.join(side, f"seed{seed:03d}.shop.jsonl"), encoding="utf-8"):
                d = json.loads(line)
                if d.get("kind") != "shop_seat" or d.get("which") != "sig":
                    continue
                # ★ 定義の名前は、消えたあと別の定義に使われうる（登録試行 reg が違う）。(定義, 登録試行, 席) ごとに生きていた試行の範囲を控え、
                #   --cf-learn の記録（reg が無い）は、その試行に範囲が掛かる (定義, 席) のときだけシールの席とする
                key = (d["R"], d["reg"], d["slot"])
                lo, hi = span.get(key, (d["trial"], None))
                span[key] = (min(lo, d["trial"]), d["trial"] if d.get("to") == "定義ごと消えた" else hi)
                fr, to = d.get("from"), d.get("to")
                allT[f"{fr}→{to}"] += 1
                sig_t.add((d["R"], d["slot"], d["trial"]))
            # ★ 判断の時点の値は v39 の記録の conv（tools/v39.py:1145：[種類, 定義, 席, V, 空くビット, 理由, 同点の数]）から取る。
            #   shop.jsonl の shop_seat の cand は、薄くしたあとに同じ定義の候補を計算し直した値で上書きされている（tools/shopworld.py:202、
            #   tools/v39.py:958）ので使わない。シールの席は、同じ試行に shop.jsonl でシールの席の状態が移った (定義, 席)
            for line in open(os.path.join(side, f"seed{seed:03d}.jsonl"), encoding="utf-8"):
                d = json.loads(line)
                if d.get("kind") != "v39" or not d.get("conv"):
                    continue
                for kind, R, slot, V, dc, why, _tie in d["conv"]:
                    if (R, slot, d["trial"]) not in sig_t:
                        continue
                    k = "F→H" if kind == "FH" else "H→U"
                    trans[k]["margin"].append((lam - V) * dc)
                    trans[k]["lamV"].append(lam - V)
                    trans[k]["num"].append(V * dc)
                    trans[k]["dc"].append(dc)
                    trans[k].setdefault("why", Counter())[why] += 1
            for line in open(os.path.join(side, f"seed{seed:03d}.cfvalue.jsonl"), encoding="utf-8"):
                d = json.loads(line)
                if "シール" not in d.get("kinds", []):
                    continue
                k = tk[d["trial"]]
                b = d["benefit"]
                for key in (k, (k[0], k[1], d["step"])):
                    e = cv[" ".join(key)]
                    e["回数"] += 1
                    e["正" if b > 0 else "負" if b < 0 else "0"] += 1
                    e["合計"] += b
                if d.get("V") is not None:
                    vcmp["V＜λ" if d["V"] < lam else "V≧λ"] += 1
            by_rs = defaultdict(list)
            for (R, reg, slot), (lo, hi) in span.items():
                by_rs[(R, slot)].append((lo, hi))
            for line in open(os.path.join(side, f"seed{seed:03d}.cflearn.jsonl"), encoding="utf-8"):
                d = json.loads(line)
                if not any(lo <= d["trial"] and (hi is None or d["trial"] < hi) for lo, hi in by_rs.get((d["R"], d["slot"]), [])):
                    continue
                k = " ".join(tk[d["trial"]])
                e = cl[k]
                c = d["cf"]
                e["回数"] += 1
                if c.get("U") is not None and c.get("H") is not None:
                    du = c["U"] - c["H"]
                    e["U−H が正"] += du > 0
                    e["U−H の合計"] += du
                if c.get("F") is not None:
                    e["F の席"] += 1
                    dh = c["H"] - c["F"]
                    e["H−F が正"] += dh > 0
                    e["H−F の合計"] += dh
        res[arm] = {"λ": lam, "台帳の行の数（種ごと）": dict(checkT),
                    "(1) --cf-value のシールの席": {k: {**v, "合計": round(v["合計"], 2)} for k, v in sorted(cv.items())},
                    "(2) --cf-learn のシールの席": {k: {**v, "U−H の合計": round(v["U−H の合計"], 2), "H−F の合計": round(v["H−F の合計"], 2)} for k, v in sorted(cl.items())},
                    "(3) シールの席を薄くした判断（v39 の conv）": {k: {"回数": len(v["margin"]), "差（(λ − V) × 空くビット、ビット）": q5(v["margin"]),
                                                              "λ − V": q5(v["lamV"]), "num（＝V × 空くビット。FH は R̄H − R̄F、HU は R̄U − R̄H）": q5(v["num"]),
                                                              "空くビット": q5(v["dc"]), "理由": dict(v.get("why", {}))} for k, v in sorted(trans.items())},
                    "(3) シールの席の状態の移りの全部（回数）": dict(sorted(allT.items())),
                    "(3) --cf-value の評価の時点の V と λ": dict(vcmp)}
        print(arm, json.dumps(res[arm], ensure_ascii=False)[:1500], flush=True)
    json.dump(res, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()

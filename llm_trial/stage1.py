"""段 1 の確かめ（委任書「LLM の小さな試し・第一段」）。★ LLM は呼ばない。
  1 場面 1,000 個（世界 1・2 × 四つの場合をでたらめに、伏せ方は学習と同じく半分ドア）を作り、文字列を読み直して研究者の側と突き合わせる。
  2 番号や行の順と、ドア・答え・型・シールの間に関係が無いか：
    ・ドアの関係の番号（10〜99 を 9 つの幅に分ける）が一様か（カイ二乗、自由度 8）
    ・ドアの行の位置（ドアが見えている場面）が一様か（行の位置そのもの。場面の行の数はどれも同じ）
    ・「?」のある行の位置が一様か（同じ）
    ・ドアの番号の幅 × 型、× シール、× 答え（世界 2、X／Y）の分割表のカイ二乗
  3 組 1（世界 1・2）の学習の系列と試験の場面を書き出す（LLM に渡す文字列と、研究者の側の記録を別のファイルに）。
使い方  python3.12 llm_trial/stage1.py <出力の場所>"""
import json
import math
import os
import random
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import world as w  # noqa: E402


def chi2_sf(x, k):
    """カイ二乗分布の上側確率（正則化された不完全ガンマ関数 Q(k/2, x/2)）。"""
    a, z = k / 2.0, x / 2.0
    if z <= 0:
        return 1.0
    if z < a + 1:
        s, term, n = 0.0, 1.0 / a, 0
        while abs(term) > 1e-15 and n < 10000:
            s += term
            n += 1
            term *= z / (a + n)
        p = s * math.exp(-z + a * math.log(z) - math.lgamma(a))
        return 1 - p
    b, c, d = z + 1 - a, 1e300, 1 / (z + 1 - a)
    h = d
    for i in range(1, 10000):
        an = -i * (i - a)
        b += 2
        d = an * d + b
        d = 1e-300 if abs(d) < 1e-300 else d
        c = b + an / c
        c = 1e-300 if abs(c) < 1e-300 else c
        d = 1 / d
        h *= d * c
        if abs(d * c - 1) < 1e-15:
            break
    return h * math.exp(-z + a * math.log(z) - math.lgamma(a))


def gof(counts, k):
    n = sum(counts.get(i, 0) for i in range(k))
    e = n / k
    x = sum((counts.get(i, 0) - e) ** 2 / e for i in range(k))
    return {"n": n, "カイ二乗": round(x, 2), "自由度": k - 1, "p": round(chi2_sf(x, k - 1), 3), "度数": [counts.get(i, 0) for i in range(k)]}


def table(pairs, rows, k):
    n = len(pairs)
    tot_r = Counter(r for r, _c in pairs)
    tot_c = Counter(c for _r, c in pairs)
    cnt = Counter(pairs)
    x = 0.0
    for r in rows:
        for c in range(k):
            e = tot_r[r] * tot_c[c] / n
            if e > 0:
                x += (cnt[(r, c)] - e) ** 2 / e
    df = (len(rows) - 1) * (k - 1)
    return {"n": n, "カイ二乗": round(x, 2), "自由度": df, "p": round(chi2_sf(x, df), 3)}


def main():
    out = sys.argv[1]
    os.makedirs(out, exist_ok=True)
    rng = random.Random("stage1-1000")
    bad = []
    door_bin, door_line, q_line = Counter(), Counter(), Counter()
    by_type, by_cue, by_ans = [], [], []
    NL = set()
    N = int(os.environ.get("STAGE1_N", "1000"))
    for i in range(N):
        world = 1 + i % 2
        typ, cue = rng.choice(w.CASES)
        rels = w.relations(typ, cue, world)
        hidden = w.DOOR_PATH if rng.random() < 0.5 else rng.choice(sorted(n for n in w.hideable(rels) if n != w.DOOR_PATH))
        voc = w.vocab(1000 + i)
        text, rec = w.render(rels, hidden, random.Random(f"s1|{i}"), voc)
        research = {"type": typ, "cue": cue, "world": world, **rec}
        v = w.verify(text, research, voc)
        if v:
            bad.append({"i": i, "食い違い": v})
        dnum = int(rec["rid"][w.DOOR_PATH][1:])
        b = (dnum - 10) * 9 // 90
        door_bin[b] += 1
        lines = text.split("\n")
        nl = len(lines)
        if hidden != w.DOOR_PATH:
            pos = next(k for k, ln in enumerate(lines) if ln.startswith(rec["rid"][w.DOOR_PATH] + ":"))
            door_line[pos] += 1
            NL.add(nl)
        qpos = next(k for k, ln in enumerate(lines) if "?" in ln)
        q_line[qpos] += 1
        NL.add(nl)
        by_type.append((typ, b))
        by_cue.append((cue, b))
        if world == 2:
            by_ans.append((w.door_pred(2, typ, cue), b))
    res = {"1 読み直しの突き合わせ": {"場面": N, "食い違いのある場面": len(bad), "例": bad[:5]},
           "2 ドアの番号（9 幅）の一様さ": gof(door_bin, 9),
           "2 ドアの行の位置（見えている場面、行の位置そのもの）の一様さ": gof(door_line, max(NL)),
           "2 「?」の行の位置（行の位置そのもの）の一様さ": gof(q_line, max(NL)),
           "場面の行の数": sorted(NL),
           "2 ドアの番号の幅 × 型": table(by_type, ["甲", "乙"], 9),
           "2 ドアの番号の幅 × シール": table(by_cue, ["n", "e"], 9),
           "2 ドアの番号の幅 × 答え（世界 2）": table(by_ans, [w.X, w.Y], 9)}
    # 3 組 1 の系列と試験
    sets = {}
    for world in (1, 2):
        st = w.make_set(1, world)
        bad_s = [s["i"] for s in st["series"] if w.verify(s["text"], s["research"], st["vocab"])]
        bad_t = [k for k, t in enumerate(st["tests"]) if w.verify(t["text"], t["research"], st["vocab"])]
        base = w.save_set(st, out)
        cnt = Counter((s["research"]["type"], s["research"]["cue"]) for s in st["series"])
        sets[f"組 1・世界 {world}"] = {"ファイル": base, "系列の場合の数": {f"{t}・{c}": v for (t, c), v in cnt.items()},
                                     "ドアを伏せた場面": sum(1 for s in st["series"] if s["research"]["door_hidden"]),
                                     "読み直しの食い違い（系列・試験）": [bad_s, bad_t], "共有部分の試験の経路": st["shared_paths"]}
    w1 = json.load(open(os.path.join(out, "set1_w1_研究者.json")))
    w2 = json.load(open(os.path.join(out, "set1_w2_研究者.json")))
    same = all(a["rid"] == b["rid"] and a["hidden"] == b["hidden"] and a["type"] == b["type"] and a["cue"] == b["cue"]
               for a, b in zip(w1["series"], w2["series"]))
    sets["世界 1・2 で順番・伏せ方・番号が同じ"] = same
    res["3 組 1"] = sets
    json.dump(res, open(os.path.join(out, "段1の確かめ.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps(res, ensure_ascii=False, indent=1)[:3000])


if __name__ == "__main__":
    main()

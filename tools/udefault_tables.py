"""既定の答えとの食い違いの表（委任書 2026-10-03）。★ tools/udefault.py の出力を読むだけ。数を並べるだけで、解釈はしない。
2 記憶を固定して、選びに使った場合（ドアが問われて答えた試行の候補）：
  今の規則の順（今の規則の順位）で、同じ支持の割合の候補の組の中だけ、期待一致率の高い方を前にする（門は変えない）。
  仮の決定：期待なし・未定義（None）の候補は、その組の中の今の位置のまま動かさない。期待一致率が決まる候補どうしが、その候補たちの占める位置の中で
  期待一致率の高い順（同じなら今の規則の順）に並び替わる。シールの一致での選びも同じ作り（一致＞一部＞不一致、「なし」は動かさない）。
  選び直した一位の「その定義での答え」と、元の一位の答えを比べて、誤答→正解・誤答→棄権・正解→誤答・正解→棄権を数える。
  範囲：世界 2 の例外の日のドア・通常の日のドア、世界 1 のドア（日で分けた数も）。
3 開示だけで学べるか（control/2026-10-03_開示だけで学べるか_走行の係.md と同じ手順）：種ごとに試行の順で、試行 t の答えの「外れる確率」を、
  t より前の答えて開示を受けた試行だけから、印の区間ごとの外れの率で推定する（区間に開示が無ければそれまでの開示全部の率、開示がまだ無ければ 0）。
  全部の種の全部の答えた試行で、その確率が実際の外れを分ける AUC（同点は 0.5）。比べに、全部の記録で区間ごとの外れの率を使った AUC も出す。
  印：(a) 選ばれた定義の期待一致率（区間 1.0、0.9〜1.0 未満、…、0.1 未満、未定義）、(b) シールの一致・不一致（なし・一致・一部・不一致）。
使い方  python3.12 tools/udefault_tables.py <udefault の出力の場所>"""
import glob
import gzip
import json
import math
import os
import sys
from collections import Counter

ARMS = {2: ["cw2_A_lam0187", "cw2_C_lam0187", "cw2_A_lam0990", "cw2_C_lam0990"],
        1: ["cw1_A_lam0187", "cw1_C_lam0187", "cw1_A_lam0990", "cw1_C_lam0990"]}
SEAL_ORDER = {"一致": 2, "一部": 1, "不一致": 0}


def outcome(a):
    return "棄権" if a["黙り"] else ("正解" if a["当たり"] else "誤答")


def reorder(v, key):
    """v は今の規則の順。同じ割合の組の中で、key が None でない候補だけを、その位置の中で key の大きい順に並べ替える。"""
    out = []
    i = 0
    while i < len(v):
        j = i
        while j < len(v) and abs(v[j]["割合"] - v[i]["割合"]) < 1e-12:
            j += 1
        grp = v[i:j]
        pos = [k for k, c in enumerate(grp) if key(c) is not None]
        mov = sorted((grp[k] for k in pos), key=lambda c: (-key(c), c["今の規則の順位"]))
        grp = list(grp)
        for k, c in zip(pos, mov):
            grp[k] = c
        out += grp
        i = j
    return out


def step2(base, arm, key):
    by = {}
    for p in sorted(glob.glob(os.path.join(base, arm, "seed0*.cands.jsonl.gz"))):
        for line in gzip.open(p, "rt", encoding="utf-8"):
            c = json.loads(line)
            by.setdefault((c["seed"], c["trial"]), []).append(c)
    res = {}
    for v in by.values():
        v = sorted(v, key=lambda c: c["今の規則の順位"])
        new = reorder(v, key)[0]
        o, n = outcome(v[0]["その定義での答え"]), outcome(new["その定義での答え"])
        k = res.setdefault(v[0]["日"], Counter())
        k["試行"] += 1
        k["元：" + o] += 1
        k["選ぶ定義が変わった"] += int(new["R"] != v[0]["R"])
        if o != n:
            k[f"{o}→{n}"] += 1
    return res


def bin_rate(x):
    if x is None:
        return "未定義"
    if x >= 1.0:
        return "1.0"
    return f"{math.floor(x * 10) / 10:.1f}"


def auc(scores, ys):
    pos = [s for s, y in zip(scores, ys) if y]
    neg = [s for s, y in zip(scores, ys) if not y]
    if not pos or not neg:
        return None
    # 順位で数える（同点は 0.5）
    allv = sorted(set(scores))
    cn = Counter(neg)
    below = {}
    acc = 0
    for s in allv:
        below[s] = acc
        acc += cn.get(s, 0)
    tot = sum(below[s] + 0.5 * cn.get(s, 0) for s in pos)
    return tot / (len(pos) * len(neg))


def step3(base, arm, mark):
    scores, ys, allrows = [], [], []
    fill_all = no_disc = 0
    for p in sorted(glob.glob(os.path.join(base, arm, "seed0*.trials.jsonl"))):
        rows = sorted((json.loads(l) for l in open(p, encoding="utf-8")), key=lambda r: r["trial"])
        seen = Counter()
        seen_miss = Counter()
        for r in rows:
            m = mark(r)
            if seen[m]:
                s = seen_miss[m] / seen[m]
            elif sum(seen.values()):
                s = sum(seen_miss.values()) / sum(seen.values())
                fill_all += 1
            else:
                s = 0.0
                no_disc += 1
            scores.append(s)
            ys.append(1 - r["当たり"])
            allrows.append((m, 1 - r["当たり"]))
            if r["開示"]:
                seen[m] += 1
                seen_miss[m] += 1 - r["当たり"]
    tot, mis = Counter(m for m, _ in allrows), Counter(m for m, y in allrows if y)
    ins = [mis[m] / tot[m] for m, _ in allrows]
    return {"答え": len(ys), "外れ": sum(ys), "AUC（開示だけ・その時点まで）": auc(scores, ys), "AUC（全部の記録）": auc(ins, [y for _, y in allrows]),
            "区間に開示が無く全体の率で代えた答え": fill_all, "開示がまだ無かった答え": no_disc,
            "印ごとの答え・外れ": {m: [tot[m], mis[m]] for m in sorted(tot)}}


def main():
    base = sys.argv[1]
    res = {"2": {}, "3": {}}
    md = ["## 2. 記憶を固定して、選びに使った場合（ドアが問われて答えた試行。同じ支持の割合の候補の中だけで並べ替え。門は変えない）", ""]
    cols = ["誤答→正解", "誤答→棄権", "正解→誤答", "正解→棄権"]
    for name, key in (("期待一致率", lambda c: c["期待一致率"]), ("シールの一致", lambda c: SEAL_ORDER.get(c["シール"]))):
        md += [f"### 印：{name}", "", "| 世界 | 腕 | 日 | 試行 | 元：正解 | 元：誤答 | 元：棄権 | 選ぶ定義が変わった | " + " | ".join(cols) + " |",
               "|---:|---|---|---:|---:|---:|---:|---:|" + "---:|" * len(cols)]
        for w, arms in ARMS.items():
            for arm in arms:
                r = step2(base, arm, key)
                res["2"].setdefault(name, {})[arm] = {k: dict(v) for k, v in r.items()}
                for day in ("e", "n"):
                    k = r.get(day, Counter())
                    md.append(f"| {w} | {arm} | {'例外' if day == 'e' else '通常'} | {k['試行']} | {k['元：正解']} | {k['元：誤答']} | {k['元：棄権']} | {k['選ぶ定義が変わった']} | "
                              + " | ".join(str(k[c]) for c in cols) + " |")
        md.append("")
    md += ["- 世界 1 は、ドアの答えがシールの日によらない（tools/shopworld.py door_pred）。日の欄は場面のシールの印で分けただけ。", "",
           "## 3. 開示だけで学べるか（印ごとの外れの予測の AUC。答えた試行すべて）", "",
           "| 世界 | 腕 | 印 | 答え | 外れ | AUC（開示だけ・その時点まで） | AUC（全部の記録） | 区間に開示が無く全体の率で代えた答え | 開示がまだ無かった答え |",
           "|---:|---|---|---:|---:|---:|---:|---:|---:|"]
    for w, arms in ARMS.items():
        for arm in arms:
            for name, mark in (("期待一致率", lambda r: bin_rate(r.get("期待一致率"))), ("シールの一致", lambda r: r.get("シール") or "未定義")):
                v = step3(base, arm, mark)
                res["3"].setdefault(name, {})[arm] = v
                f = lambda x: "—" if x is None else f"{x:.3f}"
                md.append(f"| {w} | {arm} | {name} | {v['答え']} | {v['外れ']} | {f(v['AUC（開示だけ・その時点まで）'])} | {f(v['AUC（全部の記録）'])} | "
                          f"{v['区間に開示が無く全体の率で代えた答え']} | {v['開示がまだ無かった答え']} |")
    md += ["", "### 3 の補足：印ごとの答えた試行の数と外れの数（全部の種の和）", "", "| 世界 | 腕 | 印 | 印の値ごとの［答え, 外れ］ |", "|---:|---|---|---|"]
    for name, arms in res["3"].items():
        for arm, v in arms.items():
            md.append(f"| {arm[2]} | {arm} | {name} | {v['印ごとの答え・外れ']} |")
    json.dump(res, open(os.path.join(base, "表.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    open(os.path.join(base, "表.md"), "w", encoding="utf-8").write("\n".join(md) + "\n")
    print("\n".join(md))


if __name__ == "__main__":
    main()

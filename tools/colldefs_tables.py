"""集団化で届いた定義の表（委任書 2026-10-03）。★ tools/colldefs.py の出力を読むだけ。数を並べるだけで、解釈はしない。
表 1（通信あり）：腕ごとに、例外の日のドアの外れ・届いた定義（例外の日の場面から来た束を取り込んだ定義）が記憶にあって選ばれなかった件・
  そのうち、届いた定義のどれかを使えば門を通って正しく答えられた件・どれを使っても正しく答えられなかった件（内訳：使った答えの種類）。
表 2（比べ）：通信あり／なしの例外の日のドアの外れの、選び間違い（候補の中に門を通って正しく答える定義がある）と区別の喪失（無い）の件数と割合。
  定め方は tools/selcands_tables.py の 2 と同じ。
使い方  python3.12 tools/colldefs_tables.py <colldefs の出力の場所>"""
import glob
import json
import os
import sys
from collections import Counter


def load(base, arm, mode):
    rows, chk = [], Counter()
    for p in sorted(glob.glob(os.path.join(base, arm, f"pilot_w2_{mode}_g0*.json"))):
        d = json.load(open(p, encoding="utf-8"))
        chk["集団"] += 1
        chk["対象"] += d["対象"]
        chk["作った"] += d["作った"]
        rows += d["外れ"]
    chk["確かめの食い違い"] = sum(1 for r in rows if not all(r["確かめ"].values()))
    return rows, chk


def pct(a, b):
    return f"{a}（{100 * a / b:.1f}%）" if b else f"{a}（—）"


def main():
    base = sys.argv[1]
    md, res = [], {}
    md += ["## 1. 通信あり：届いた定義を使った場合の答え（世界 2、例外の日にドアが問われて外れた試行、集団の種 1〜20、二体の和）", "",
           "| 腕 | 外れ | 届いた定義が記憶にあり選ばれなかった件 | そのうち正しく答えられた | 正しく答えられなかった | （内訳：届いた定義の答えが、門を通らない・黙り・外れ。件ごとに一番よいもの） |",
           "|---|---:|---:|---:|---:|---|"]
    for arm in ("A", "C"):
        rows, chk = load(base, arm, "recvA")
        have = [r for r in rows if r["届いた定義"]]
        ok = [r for r in have if r["届いた定義で正しく答えられる"]]
        why = Counter()
        for r in have:
            if r["届いた定義で正しく答えられる"]:
                continue
            kinds = set()
            for g in r["届いた定義"]:
                if not g["候補にある"]:
                    kinds.add("候補に無い")
                    continue
                a = g["その定義での答え"]
                kinds.add("門を通らない" if not a["門を通る"] else ("黙り" if a["黙り"] else "外れ"))
            why[next(k for k in ("外れ", "黙り", "門を通らない", "候補に無い") if k in kinds)] += 1
        res[arm] = {"確かめ": dict(chk), "外れ": len(rows), "届いた定義が記憶にあり選ばれなかった": len(have), "正しく答えられた": len(ok),
                    "正しく答えられなかった": len(have) - len(ok), "内訳": dict(why)}
        md.append(f"| {arm} | {len(rows)} | {len(have)} | {pct(len(ok), len(have))} | {len(have) - len(ok)} | {dict(why)} |")
    md += ["", "- 内訳は、正しく答えられなかった件ごとに、届いた定義の答えのうち「外れ（門を通って答えた）」→「黙り」→「門を通らない」→「候補に無い」の順で最初にあるもの。", "",
           "## 2. 比べ：例外の日のドアの外れの、選び間違いと区別の喪失", "",
           "| 腕 | 通信 | 外れ | 選び間違い（門を通って正しく答える候補がある） | 区別の喪失（無い） | 選び間違いのうち、届いた定義で正しく答えられる |",
           "|---|---|---:|---:|---:|---:|"]
    for arm in ("A", "C"):
        for mode, lab in (("no_comm", "なし"), ("recvA", "あり")):
            rows, chk = load(base, arm, mode)
            se = [r for r in rows if r["候補の中に正しく答える定義がある"]]
            via = sum(1 for r in se if r["届いた定義で正しく答えられる"])
            res.setdefault("比べ", {})[f"{arm}・{lab}"] = {"確かめ": dict(chk), "外れ": len(rows), "選び間違い": len(se), "区別の喪失": len(rows) - len(se),
                                                        "選び間違いのうち届いた定義で": via}
            md.append(f"| {arm} | {lab} | {len(rows)} | {pct(len(se), len(rows))} | {pct(len(rows) - len(se), len(rows))} | {via if mode == 'recvA' else '—'} |")
    md += ["", "| 腕 | 通信 | 集団 | 対象の外れ | 作り直した | 確かめの食い違い（予測・一位の選び・一位でやり直した答え） |", "|---|---|---:|---:|---:|---:|"]
    for k, v in res["比べ"].items():
        c = v["確かめ"]
        md.append(f"| {k.split('・')[0]} | {k.split('・')[1]} | {c.get('集団', 0)} | {c.get('対象', 0)} | {c.get('作った', 0)} | {c['確かめの食い違い']} |")
    json.dump(res, open(os.path.join(base, "表.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    open(os.path.join(base, "表.md"), "w", encoding="utf-8").write("\n".join(md) + "\n")
    print("\n".join(md))


if __name__ == "__main__":
    main()

"""手がかりを知っていた場合の上限：「シール優先」で選び直した答えの数え上げ（委任書 2026-10-02 夜）。★ tools/selcands.py の出力を読むだけ。
★ この選び方は、研究者が答えを分ける手がかり（シール）を知っている前提の「ずる」で、模型に入れる案ではない。比べの上限として数えるだけ。
シール優先：門を通る候補（その定義での答えの「門を通る」）のうち、シールの席が F・H で、場面のシールに名前で写った定義を優先し、
  その中は今の規則の順（今の規則の順位）。該当が無ければ今の規則のまま（順位 1 の定義）。
「場面のシールに名前で写った」の判定：
  ・記録に「場面のシールに写る」の欄があればそれ（通常の日の書き出しで足した欄）。
  ・無ければ（例外の日の記録）、シールの席が F・H で「写り先は見えている」。見えている関係への写りは名前が同じか履歴の名に入るときだけで
    （tools/v39.py:308）、場面で述語 sig_n・sig_e を持つのはシールの関係だけ（tools/shopworld.py:70）なので、同じことになる。
元の答え・選び直した答え：どちらも候補ごとのやり直しの答え（その定義での答え）。順位 1 のやり直しが本物と同じことは selcands の確かめで見ている。
使い方  python3.12 tools/sealprio.py <selcands の出力の場所> <表の題>"""
import glob
import gzip
import json
import os
import sys
from collections import Counter

ARMS = ["cw2_A_lam0187", "cw2_C_lam0187", "cw2_A_lam0990", "cw2_C_lam0990"]


def outcome(a):
    return "黙り" if a["黙り"] else ("当たり" if a["当たり"] else "外れ")


def seal_named(c):
    for s in c["ドア・シール・link の席"]:
        if s["種類"] != "シール" or s["状態"] not in ("F", "H"):
            continue
        if "場面のシールに写る" in s:
            if s["場面のシールに写る"]:
                return True
        elif s["写り先は見えている"]:
            return True
    return False


def main():
    base, title = sys.argv[1], sys.argv[2]
    res = {}
    md = [f"## {title}", "",
          "| 腕 | 試行 | 元：当たり | 元：外れ | 元：黙り | 該当の定義があった | 選ぶ定義が変わった | 外れ→当たり | 正解→外れ | 正解→黙り | 外れ→黙り | 黙り→当たり | 黙り→外れ | 選び直し後：当たり |",
          "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for arm in ARMS:
        by = {}
        for p in sorted(glob.glob(os.path.join(base, arm, "seed*.cands.jsonl.gz"))):
            if int(os.path.basename(p)[4:7]) > 20:
                continue
            for line in gzip.open(p, "rt", encoding="utf-8"):
                c = json.loads(line)
                by.setdefault((c["seed"], c["trial"]), []).append(c)
        k = Counter()
        for v in by.values():
            v = sorted(v, key=lambda c: c["今の規則の順位"])
            top = v[0]
            pref = [c for c in v if c["その定義での答え"]["門を通る"] and seal_named(c)]
            ch = pref[0] if pref else top
            o, n = outcome(top["その定義での答え"]), outcome(ch["その定義での答え"])
            k["試行"] += 1
            k["元：" + o] += 1
            k["選び直し後：" + n] += 1
            k["該当の定義があった"] += int(bool(pref))
            k["選ぶ定義が変わった"] += int(ch["R"] != top["R"])
            if o != n:
                k[f"{'正解' if o == '当たり' else o}→{n}"] += 1
        res[arm] = dict(k)
        md.append(f"| {arm} | {k['試行']} | {k['元：当たり']} | {k['元：外れ']} | {k['元：黙り']} | {k['該当の定義があった']} | {k['選ぶ定義が変わった']} | "
                  f"{k['外れ→当たり']} | {k['正解→外れ']} | {k['正解→黙り']} | {k['外れ→黙り']} | {k['黙り→当たり']} | {k['黙り→外れ']} | {k['選び直し後：当たり']} |")
    json.dump(res, open(os.path.join(base, "シール優先.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    open(os.path.join(base, "シール優先.md"), "w", encoding="utf-8").write("\n".join(md) + "\n")
    print("\n".join(md))


if __name__ == "__main__":
    main()

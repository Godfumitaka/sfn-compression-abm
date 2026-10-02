"""選び間違いの表（委任書 2026-10-02 夕方の 1・2）。★ tools/selcands.py の出力を読むだけ。数を並べるだけで、解釈はしない。
2 の分け方（委任書のとおり）：外れの件で、候補の中に「それを使えば門を通り、正しく答える定義」があれば選び間違い、無ければ区別の喪失。
選び間違いの件では、正しく答える候補のうち今の規則で一番上のもの（「正しい定義」）を比べる：
  ・割合が選ばれた定義と同じ（同点）か、低いか。同点のうち、両方 1.0 か。
  ・正しい定義のシールの席の状態。
  ・割合で負けた（低い）件で、正しい定義の写らなかった F・H の席の種類（席の数の和）。
使い方  python3.12 tools/selcands_tables.py <selcands の出力の場所> [種:試行 腕]（1 の表の試行。既定 1:113 cw2_A_lam0187）"""
import glob
import gzip
import json
import os
import sys
from collections import Counter

ARMS = ["cw2_A_lam0187", "cw2_C_lam0187", "cw2_A_lam0990", "cw2_C_lam0990"]


def load(base, arm):
    by = {}
    for p in sorted(glob.glob(os.path.join(base, arm, "seed*.cands.jsonl.gz"))):
        for l in gzip.open(p, "rt", encoding="utf-8"):
            c = json.loads(l)
            by.setdefault((c["seed"], c["trial"]), []).append(c)
    return by


def main():
    base = sys.argv[1]
    s1, t1 = (int(x) for x in (sys.argv[2] if len(sys.argv) > 2 else "1:113").split(":"))
    arm1 = sys.argv[3] if len(sys.argv) > 3 else "cw2_A_lam0187"
    md = []
    # 1 の表
    rows = sorted(load(base, arm1).get((s1, t1), []), key=lambda c: c["今の規則の順位"])
    md += [f"## 1. 試行 {t1} の候補の表（{arm1}・種 {s1}・試行 {t1}。0 から数える）", ""]
    if rows:
        md += [f"- 店：{rows[0]['店']}。本物の答えは{'当たり' if rows[0]['本物の当たり'] else '外れ'}。候補（F・H の席がある定義）：{len(rows)}。", ""]
    md += ["| 順位 | 定義 | 生まれた試行 | F/H/U | 分子／分母（割合） | (i) 見えている関係 | (ii) 見えていない位置 | (iii) U の席の写り | SME の点数 | 選択用の点数（名前・引数・つながり） | 場面の側の割合 | r（ビット） | 選ばれた | 答え | 門 | 当たり | ドアの位置 |",
           "|---:|---|---:|---|---|---:|---:|---:|---:|---|---:|---:|---|---|---|---|---|"]
    for c in rows:
        a = c["その定義での答え"]
        sel = c["選択用の内訳"]
        md.append(f"| {c['今の規則の順位']} | {c['R']} | {c['生まれた試行']} | {c['F']}/{c['H']}/{c['U']} | {c['分子']}／{c['分母']}（{c['割合']:.3f}） | "
                  f"{c['(i) 見えている関係に写った']} | {c['(ii) 見えていない位置に写った']} | {c['(iii) U の席の写り']} | {c['SME の点数']:.2f} | "
                  f"{c['選択用の点数']}（{sel['名前の一致']}・{sel['引数の対応']}・{sel['一段のつながり']}） | {c['場面の側の割合']:.3f} | {c['r']} | "
                  f"{'○' if c['選ばれた'] else ''} | {a['答え'] or '黙り（' + str(a['理由']) + '）'} | {'通る' if a['門を通る'] else '通らない'} | "
                  f"{'○' if a['当たり'] else '×'} | {'○' if a['ドアの位置に答えた'] else '×'} |")
    md += ["", "### 1 の補足：ドア・シール・link の席と、SME の点数の各項、r の内訳", "",
           "| 順位 | 定義 | ドア・シール・link の席（種類・状態・履歴・写り先が見えているか・ドアに写るか） | SME の各項 | r の内訳 | 写らなかった F・H の席 |",
           "|---:|---|---|---|---|---|"]
    for c in rows:
        seats = "；".join(f"{s['種類']}（席 {s['席']}）{s['状態']}・{s['履歴'] if s['履歴'] is not None else (s['述語'] or '—')}・見え{'○' if s['写り先は見えている'] else '×'}・ドア{'○' if s['ドアに写る'] else '×'}"
                         for s in c["ドア・シール・link の席"])
        b = c["SME の内訳"]
        sme = f"述語 {b.get('predicate_match')}・引数 {b.get('argument_consistency')}・体系性 {b.get('systematicity')}・写らない減点 {b.get('unmatched_penalty')}"
        rp = c["r の内訳"]
        rr = "；".join(f"{k} {round(v, 2) if isinstance(v, float) else v}" for k, v in rp.items())
        md.append(f"| {c['今の規則の順位']} | {c['R']} | {seats} | {sme} | {rr} | {c['写らなかった F・H の席（種類別）'] or '—'} |")
    # 2 の表
    md += ["", "## 2. 選び間違いの数え上げ（世界 2、例外の日にドアが問われて答えた試行、種 1〜20）", "",
           "| 腕 | 外れの件数 | 選び間違い | 区別の喪失 | 選び間違いのうち同点（割合が同じ） | うち両方 1.0 | 選び間違いのうち割合で負けた | 正解の件数（比べ） | 正解のうち、ほかにも正しく答える候補があった |",
           "|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    detail = {}
    for arm in ARMS:
        by = load(base, arm)
        miss = [v for v in by.values() if not v[0]["本物の当たり"]]
        hitc = [v for v in by.values() if v[0]["本物の当たり"]]
        sel_err, lost, tie, tie1, worse = 0, 0, 0, 0, 0
        seal_st = Counter()
        unm = Counter()
        tie_break = Counter()
        for v in miss:
            v = sorted(v, key=lambda c: c["今の規則の順位"])
            good = [c for c in v if c["その定義での答え"]["当たり"] and c["その定義での答え"]["門を通る"]]
            if not good:
                lost += 1
                continue
            sel_err += 1
            g, ch = good[0], v[0]
            seals = [s["状態"] for s in g["ドア・シール・link の席"] if s["種類"] == "シール"]
            seal_st["・".join(seals) if seals else "シールの席なし"] += 1
            if abs(g["割合"] - ch["割合"]) < 1e-12:
                tie += 1
                tie1 += int(ch["割合"] == 1.0)
                tie_break["席の数で負けた" if g["分母"] < ch["分母"] else "登録の新しさ・名前で負けた"] += 1
            else:
                worse += 1
                for k, n in g["写らなかった F・H の席（種類別）"].items():
                    unm[k] += n
        other = sum(1 for v in hitc if sum(1 for c in v if c["その定義での答え"]["当たり"] and c["その定義での答え"]["門を通る"]) > 1)
        md.append(f"| {arm} | {len(miss)} | {sel_err} | {lost} | {tie} | {tie1} | {worse} | {len(hitc)} | {other} |")
        detail[arm] = {"正しい定義のシールの席": dict(seal_st), "同点の決まり方": dict(tie_break), "割合で負けた件の写らなかった席（種類別の和）": dict(unm)}
    md += ["", "| 腕 | 正しい定義のシールの席の状態（件数） | 同点の決まり方 | 割合で負けた件で、正しい定義の写らなかった F・H の席（種類別の和） |", "|---|---|---|---|"]
    for arm, d in detail.items():
        md.append(f"| {arm} | {d['正しい定義のシールの席']} | {d['同点の決まり方']} | {d['割合で負けた件の写らなかった席（種類別の和）']} |")
    open(os.path.join(base, "表.md"), "w", encoding="utf-8").write("\n".join(md) + "\n")
    json.dump(detail, open(os.path.join(base, "表.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("\n".join(md))


if __name__ == "__main__":
    main()

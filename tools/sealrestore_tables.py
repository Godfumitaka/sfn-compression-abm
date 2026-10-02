"""シールを戻す確かめの表（委任書 2026-10-02 昼の 1）。★ tools/sealrestore.py の出力を読むだけ。
腕ごとに、戻した席（シール／シール以外の U の席）ごとの：件数、答えが正解に変わった、黙りに変わった、外れのまま、選ばれる定義が変わった、
支持が 1 未満になった。取り出せなかった件の理由別の数、比べの席が無かった件の数。確かめ（予測の食い違い・指紋の食い違い）の和。
「外れのまま」＝答えて、当たらなかった（答えが元と同じかどうかは別の欄に数える）。
使い方  python3.12 tools/sealrestore_tables.py <sealrestore の出力の場所>"""
import glob
import json
import os
import sys
from collections import Counter

ARMS = ["cw2_A_lam0187", "cw2_C_lam0187", "cw2_A_lam0990", "cw2_C_lam0990"]


def tally(items, base):
    c = Counter()
    for o, b in zip(items, base):
        c["件数"] += 1
        if o["当たり"]:
            c["正解に変わった"] += 1
        elif o["黙り"]:
            c["黙りに変わった"] += 1
        else:
            c["外れのまま"] += 1
            if o["答え"] == b["答え"] and o["引数"] == b["引数"]:
                c["外れのまま（答えも元と同じ）"] += 1
        if o["R"] != b["R"]:
            c["選ばれる定義が変わった"] += 1
        if o["支持の割合"] is not None and o["支持の割合"] < 1:
            c["支持が 1 未満になった"] += 1
    return dict(c)


def main():
    base_dir = sys.argv[1]
    res, md = {}, ["# シールを戻して答え直す（世界 2、種 1〜20）", ""]
    md += ["| 腕 | 戻した席 | 件数 | 答えが正解に変わった | 黙りに変わった | 外れのまま | （うち答えも元と同じ） | 選ばれる定義が変わった | 支持が 1 未満になった |",
           "|---|---|---:|---:|---:|---:|---:|---:|---:|"]
    for arm in ARMS:
        rows = [json.loads(l) for p in sorted(glob.glob(os.path.join(base_dir, arm, "seed*.restore.jsonl"))) for l in open(p, encoding="utf-8")]
        chk = [json.load(open(p, encoding="utf-8")) for p in sorted(glob.glob(os.path.join(base_dir, arm, "seed*.check.json")))]
        excl = Counter(r["除いた理由"] for r in rows if "除いた理由" in r)
        ok = [r for r in rows if "除いた理由" not in r]
        sig_ok = [r for r in ok if "R" in r.get("シール", {})]
        sig_no = Counter(r["シール"]["取り出せない"] for r in ok if "取り出せない" in r.get("シール", {}))
        ctl_ok = [r for r in ok if "R" in (r.get("比べ") or {})]
        ctl_none = sum(1 for r in ok if "比べ" not in r)
        ctl_none_any = sum(1 for r in ok if r.get("シール以外の U の席の数", 0) == 0)
        t_sig = tally([r["シール"] for r in sig_ok], [r["本物の答え（やり直し）"] for r in sig_ok])
        t_ctl = tally([r["比べ"] for r in ctl_ok], [r["本物の答え（やり直し）"] for r in ctl_ok])
        both = [r for r in sig_ok if "R" in (r.get("比べ") or {})]
        t_sig_b = tally([r["シール"] for r in both], [r["本物の答え（やり直し）"] for r in both])
        t_ctl_b = tally([r["比べ"] for r in both], [r["本物の答え（やり直し）"] for r in both])
        res[arm] = {"対象の件": len(rows), "除いた件（理由別）": dict(excl), "シール：取り出せない（理由別）": dict(sig_no),
                    "シール": t_sig, "シール以外の U の席": t_ctl, "比べの席が無い件": ctl_none,
                    "うちシール以外の U の席がそもそも無い件": ctl_none_any,
                    "両方そろった件だけ：シール": t_sig_b, "両方そろった件だけ：シール以外の U の席": t_ctl_b,
                    "確かめ": {"走行": len(chk), "全試行で確かめた走行": sum(1 for c in chk if c.get("全試行の確かめ")),
                             "予測を比べた試行": sum(c["pred_compared"] for c in chk), "予測の食い違い": sum(c["pred_mismatch"] for c in chk),
                             "指紋の食い違い（v39_seats の init・post を除く）": sum(c["hash_mismatch"] for c in chk)},
                    "戻した状態の種類（シール）": dict(Counter(r["シール"]["戻した状態"]["st"] for r in sig_ok)),
                    "戻した状態の種類（比べ）": dict(Counter(r["比べ"]["戻した状態"]["st"] for r in ctl_ok))}
        for name, t in (("シール", t_sig), ("シール以外の U の席", t_ctl), ("シール（両方そろった件）", t_sig_b), ("シール以外（両方そろった件）", t_ctl_b)):
            md.append(f"| {arm} | {name} | {t.get('件数', 0)} | {t.get('正解に変わった', 0)} | {t.get('黙りに変わった', 0)} | {t.get('外れのまま', 0)} | "
                      f"{t.get('外れのまま（答えも元と同じ）', 0)} | {t.get('選ばれる定義が変わった', 0)} | {t.get('支持が 1 未満になった', 0)} |")
    md += ["", "| 腕 | 対象の件 | 除いた件 | シールの最後の状態を取り出せない | 比べの席が無い（うちシール以外の U の席が無い） | 戻した状態（シール） | 戻した状態（比べ） | 予測の確かめ |",
           "|---|---:|---|---|---|---|---|---|"]
    for arm, v in res.items():
        c = v["確かめ"]
        md.append(f"| {arm} | {v['対象の件']} | {v['除いた件（理由別）']} | {v['シール：取り出せない（理由別）']} | {v['比べの席が無い件']}（{v['うちシール以外の U の席がそもそも無い件']}） | "
                  f"{v['戻した状態の種類（シール）']} | {v['戻した状態の種類（比べ）']} | {c['走行']} 走行（全試行 {c['全試行で確かめた走行']}）、{c['予測を比べた試行']} 試行で食い違い {c['予測の食い違い']}、指紋の食い違い {c['指紋の食い違い（v39_seats の init・post を除く）']} |")
    json.dump(res, open(os.path.join(base_dir, "戻して答え直す.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    open(os.path.join(base_dir, "戻して答え直す.md"), "w", encoding="utf-8").write("\n".join(md) + "\n")
    print("\n".join(md))


if __name__ == "__main__":
    main()

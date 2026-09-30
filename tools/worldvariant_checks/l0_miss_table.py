"""世界 v4（型の変種）の λ＝0 の外れの中身（2026-09-30 朝の委任書の 3）。★ 数えるだけ。判断しない。
切り替わる関係が伏せられた課題（held_out_switch あり）で、実際に答えたもの（答えごとの記録、tools/answerlog.py）を、外れと当たりに分けて並べる。
使い方  python3.12 tools/worldvariant_checks/l0_miss_table.py <出力 md> <answers.csv> [<answers.csv> …]"""
import collections
import csv
import json
import statistics
import sys

A_PRED = {"T1": "hold", "T2": "break", "T3": "pull", "T4": "wrap"}
B_PRED = {"T1": "hold_b", "T2": "break_b", "T3": "pull_b", "T4": "wrap_b"}


def pred_kind(r):
    T = r["held_out_switch"]
    if r["pred"] == A_PRED[T]:
        return "その関係の変種 A の述語"
    if r["pred"] == B_PRED[T]:
        return "その関係の変種 B の述語"
    if r["pred"] in A_PRED.values() or r["pred"] in B_PRED.values():
        return "ほかの切り替わる関係の述語"
    return "それ以外"


def main():
    out, files = sys.argv[1], sys.argv[2:]
    rows = []
    for f in files:
        rows += [r for r in csv.DictReader(open(f, encoding="utf-8")) if r.get("held_out_switch")]
    for r in rows:
        r["結果"] = "当たり" if r["hit"] == "1" else "外れ"
        r["答えた述語の種類"] = pred_kind(r)
        r["二つとも入っている"] = "はい" if r["def_switch_seats"] == "2" else f"いいえ（{r['def_switch_seats'] or '？'}）"
    L = ["| 結果 | 場面の変種 | 答え |", "|---|---|---:|"]
    c = collections.Counter((r["結果"], r["scene_variant"]) for r in rows)
    L += [f"| {k[0]} | {k[1]} | {v:,} |" for k, v in sorted(c.items())]
    keys = ("scene_variant", "born_variant", "base_variant", "二つとも入っている", "答えた述語の種類", "other_switch_visible", "source")
    head = ("場面の変種", "定義が生まれた場面の変種", "生まれたときの土台の場面の変種", "定義に切り替わる関係の席が二つとも入っているか",
            "答えた述語", "もう一方の切り替わる関係が場面で見えていたか", "答えの出どころ")
    L += ["", "外れと当たりを、同じ項目で並べる（数は答えの数）", "", "| " + " | ".join(head) + " | 外れ | 当たり |", "|" + "---|" * len(head) + "---:|---:|"]
    t = collections.Counter((tuple(r[k] for k in keys), r["結果"]) for r in rows)
    for k in sorted({k for k, _ in t}):
        L.append("| " + " | ".join(x or "—" for x in k) + f" | {t[(k, '外れ')]:,} | {t[(k, '当たり')]:,} |")
    L += ["", "選ばれなかった候補の定義の支持の割合（答えるときの照合で、選ばれた定義以外の候補のうち最大のもの）", "",
          "| 結果 | 答え | 候補の数（平均） | 選ばれた定義の支持の割合（平均） | 選ばれなかった候補の最大（平均） | 同（中央値） | 選ばれた定義と同じ割合の候補があった答え |", "|---|---:|---:|---:|---:|---:|---:|"]
    for res in ("外れ", "当たり"):
        rs = [r for r in rows if r["結果"] == res]
        mx = [float(r["cand_other_max_ratio"]) for r in rs if r["cand_other_max_ratio"] != ""]
        sel = [float(r["support_ratio"]) for r in rs if r["support_ratio"] != ""]
        cn = [int(r["cand_n"]) for r in rs if r["cand_n"] != ""]
        tie = sum(1 for r in rs if r["cand_other_max_ratio"] != "" and abs(float(r["cand_other_max_ratio"]) - float(r["support_ratio"])) < 1e-12)
        f = lambda v: f"{v:.3f}" if v is not None else "—"  # noqa: E731
        L.append(f"| {res} | {len(rs):,} | {f(statistics.mean(cn) if cn else None)} | {f(statistics.mean(sel) if sel else None)} | "
                 f"{f(statistics.mean(mx) if mx else None)} | {f(statistics.median(mx) if mx else None)} | {tie:,} |")
    L += ["", "答えた定義ごと（外れの多い順）", "",
          "| 種 | 答えた定義 | 定義が生まれた場面の変種 | 土台の変種 | 二つとも入っている | 外れ | 当たり | 答えた述語（外れ） | 答えた述語（当たり） |",
          "|---:|---|---|---|---|---:|---:|---|---|"]
    by = collections.defaultdict(list)
    for r in rows:
        by[(r["seed"], r["def_id"])].append(r)
    for (s, d), rs in sorted(by.items(), key=lambda kv: (-sum(r["結果"] == "外れ" for r in kv[1]), kv[0])):
        r0 = rs[0]
        pm = collections.Counter(r["pred"] for r in rs if r["結果"] == "外れ")
        ph = collections.Counter(r["pred"] for r in rs if r["結果"] == "当たり")
        L.append(f"| {s} | {d} | {r0['born_variant']} | {r0['base_variant']} | {r0['二つとも入っている']} | {sum(pm.values())} | {sum(ph.values())} | "
                 f"{', '.join(f'{k} {v}' for k, v in pm.most_common()) or '—'} | {', '.join(f'{k} {v}' for k, v in ph.most_common()) or '—'} |")
    open(out, "w", encoding="utf-8").write("\n".join(L) + "\n")
    with open(out.replace(".md", ".csv"), "w", encoding="utf-8", newline="") as fo:
        w = csv.DictWriter(fo, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(json.dumps({"答え": len(rows), "外れ": sum(r["結果"] == "外れ" for r in rows)}, ensure_ascii=False))


if __name__ == "__main__":
    main()

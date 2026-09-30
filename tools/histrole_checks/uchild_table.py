"""tools/histrole_checks/uchild.py の記録を表にする。★ 数えるだけ。判断しない。
使い方  python3.12 tools/histrole_checks/uchild_table.py <出力 md> <名前=jsonl> ..."""
import json
import statistics
import sys


def main():
    out = sys.argv[1]
    runs = [(a.split("=", 1)[0], json.loads(open(a.split("=", 1)[1], encoding="utf-8").readline())) for a in sys.argv[2:]]
    L = ["### 1 U の子を持つ F・H の親の席の数（定義ごと）", "",
         "予測の前の状態（100 試行ごと、試行 100〜1,700 の 17 回）と走行の終わり。親の席は、U の子を一つ以上持つ F・H の行（一つの行は一回だけ数える）。", "",
         "| 腕・種 | 途中：定義の数（平均） | 途中：U の子を持つ親がいる定義（平均） | 途中：U の子を持つ親の席（和の平均） | 途中：一つの定義の最大（最大） | 終わり：定義の数 | 終わり：親がいる定義 | 終わり：親の席（和） | 終わり：定義ごと（多い順） |",
         "|---|---:|---:|---:|---:|---:|---:|---:|---|"]
    for name, d in runs:
        mid = [c for c in d["census"] if c["tag"] != "走行の終わり"]
        end = [c for c in d["census"] if c["tag"] == "走行の終わり"][-1]
        m = lambda k: statistics.mean(c[k] for c in mid) if mid else 0  # noqa: E731
        L.append(f"| {name} | {m('defs'):.1f} | {m('defs_with'):.1f} | {m('parents'):.1f} | {max((c['max'] for c in mid), default=0)} | "
                 f"{end['defs']} | {end['defs_with']} | {end['parents']} | {', '.join(str(x) for x in end['per_def'] if x) or '—'} |")
    L += ["", "### 2 選ばれた定義で、U の子のせいで照合から外れた親（予測ごと、延べ）", "",
          "「外れた親」＝本当の照合で写らず、U の子の引数だけを緩めた仮の照合では場面の関係 Q に写り、Q のその子の位置の関係が見えている F・H の親。", "",
          "| 腕・種 | 予測で定義を選んだ試行 | 選んだ定義に U の子を持つ親がいた | 外れた親がいた試行 | 外れた親（延べ） | 支持の割合の下がり（外れた親がいた試行の平均） | 同（最大） | 門を通れなかった試行 | そのうち、外れた親を当てはまったと数えたら通っていた |",
          "|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for name, d in runs:
        S = d["select"]
        ex = [r for r in S if r["excluded"]]
        drops = [r["excluded"] / r["n"] for r in ex if r["n"]]
        L.append(f"| {name} | {len(S):,} | {sum(1 for r in S if r['u_parents']):,} | {len(ex):,} | {sum(r['excluded'] for r in S):,} | "
                 f"{(statistics.mean(drops) if drops else 0):.3f} | {(max(drops) if drops else 0):.3f} | {sum(1 for r in S if r['support'] < r['need']):,} | "
                 f"{sum(1 for r in S if r['support'] < r['need'] <= r['support'] + r['excluded']):,} |")
    L += ["", "### 3 U の席が、役割に見えている関係があるのに観察を受けなかった回数（m1 の同化ごと、延べ）", "",
          "m1（実際の鎖）で同化した定義の、その試行の前に U だった席。「役割に見えている関係がある」＝仮の照合で、その席の親が場面の関係 Q に写り、Q のその席の位置の関係が見えている。「観察を受けた」＝この m1 のあと、その席に履歴の鍵がある（U→H の覚え直し）。", "",
          "| 腕・種 | 階 | U の席（延べ） | 役割に見えている関係がある | そのうち観察を受けなかった | 役割に見えている関係が無い | そのうち観察を受けた |", "|---|---|---:|---:|---:|---:|---:|"]
    for name, d in runs:
        for lab, hi in (("一階", False), ("高階", True)):
            M = [r for r in d["m1"] if r["higher"] == hi]
            rv = [r for r in M if r["role_visible"]]
            nv = [r for r in M if not r["role_visible"]]
            L.append(f"| {name} | {lab} | {len(M):,} | {len(rv):,} | {sum(1 for r in rv if not r['observed']):,} | {len(nv):,} | {sum(1 for r in nv if r['observed']):,} |")
    open(out, "w", encoding="utf-8").write("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()

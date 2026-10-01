"""照合の直し：親子の並行連結（2026-10-01 朝の委任書「照合の直し（親子の並行連結）と照合器の検査」の 1）。旗 --strict-pc（既定オフ）。
★ abm/ は変えない。sme._alignment_candidates（照合の候補の一覧。fix2・v39・ustruct の差し替えを含む）をいちばん外側で包む。旗を切れば何もしない。

決まり（アストラさんの決定：本来の SME に忠実に、子が合わない親は対にしない）
  親の候補の対（基の行 l, 相手の行 r）は、その relation_pairs のすべての子の対 (l_c, r_c) が次のどちらかのときだけ、採れる候補とする。
    (a) r_c が相手の場面に見えていない（相手の場面の関係の ID に無い。伏せた関係など。F-1 の第三分岐。今どおり写してよい）。
    (b) (l_c, r_c) 自体が、同じ照合の直接の対の候補の一覧にあり（F・H・U の名前の条件は今の候補の作り方のまま）、
        かつその子の対もこの決まりで採れる候補である（下へ再帰。一度決めた答えは控える）。
  採れる候補だけを、元の並びのまま照合の手順（tools/fixorder2.py の map_graphs）に渡す。採る段で子の対が今の写像と食い違えば親を採らない
  決まりは、今の sme._candidate_fits のまま（写像器の側は変えない）。
数え（STATS）：落とした親の候補の数と、その理由（最初に引っかかった子の、基の述語 ≠ 相手の述語／子の対が無い／子の対が採れない（孫で落ちた））。
  使い道ごと（呼び出しの元の関数で分ける：予測の定義の照合・予測の場面の照合・誕生と同化・E の書き直しの費用・同定・試験・記録の道具・その他）に、
  候補の一覧を作った回数・落とした親の候補の数を数える。
"""
from __future__ import annotations

import sys
from collections import Counter

STATS: dict = {}
USES = (  # （呼び出しの元の関数名, 使い道）。スタックを内から外へ見て、最初に当たったもの
    ("_probe", "試験"),
    ("_sources", "記録の道具（routelog）"),
    ("hypo_m1", "E の書き直しの費用（仮の適用）"),
    ("rewrite", "E の書き直しの費用"),
    ("choose_and_register", "E の書き直しの費用"),
    ("counterfactuals", "反実仮想の予測"),
    ("select_definition", "予測の定義の照合"),
    ("map_v39", "予測の定義の照合"),
    ("_identify_definition", "同定"),
    ("identify", "同定"),
    ("m1", "誕生と同化"),
    ("predict", "予測の場面の照合（逐語の記憶と提示）"),
)


def _use() -> str:
    f = sys._getframe(2)
    names = []
    while f is not None and len(names) < 40:
        names.append(f.f_code.co_name)
        f = f.f_back
    for fn, label in USES:
        if fn in names:
            return label
    return "その他"


def filter_candidates(cands, base_graph, partial_graph):
    """採れる候補だけを、元の並びのまま返す。あわせて (落とした数, 理由の Counter) を返す。"""
    partial_ids = frozenset(r.relation_id for r in partial_graph.relations)
    direct = {(c.base_relation_id, c.partial_relation_id): c for c in cands}
    bpred = {r.relation_id: r.predicate for r in base_graph.relations}
    tpred = {r.relation_id: r.predicate for r in partial_graph.relations}
    memo: dict = {}
    why: dict = {}

    def ok(c) -> bool:
        key = (c.base_relation_id, c.partial_relation_id)
        if key in memo:
            return memo[key]
        memo[key] = True   # 循環は無い（子は親の引数）が、念のため
        res = True
        for lc, rc in c.relation_pairs:
            if rc not in partial_ids:
                continue
            child = direct.get((lc, rc))
            if child is None:
                res = False
                why[key] = f"子の対が無い：{bpred.get(lc, '?')}≠{tpred.get(rc, '?')}" if bpred.get(lc) != tpred.get(rc) \
                    else "子の対が無い（名は同じ）"
                break
            if not ok(child):
                res = False
                why[key] = "子の対が採れない（その下で落ちた）"
                break
        memo[key] = res
        return res

    out = [c for c in cands if ok(c)]
    reasons = Counter(why[(c.base_relation_id, c.partial_relation_id)] for c in cands if not memo[(c.base_relation_id, c.partial_relation_id)])
    return tuple(out), len(cands) - len(out), reasons


def install() -> None:
    """ほかの候補の差し替え（fix2・v39・ustruct）のあと、照合を使う前に入れる。"""
    import abm.sme as sme
    STATS.clear()
    STATS.update(calls=0, dropped=0, reasons=Counter(), use_calls=Counter(), use_dropped=Counter())
    prev = sme._alignment_candidates

    def _alignment_candidates(base_graph, partial_graph):
        cands = prev(base_graph, partial_graph)
        out, n, reasons = filter_candidates(cands, base_graph, partial_graph)
        u = _use()
        STATS["calls"] += 1
        STATS["dropped"] += n
        STATS["reasons"].update(reasons)
        STATS["use_calls"][u] += 1
        STATS["use_dropped"][u] += n
        return out

    sme._alignment_candidates = _alignment_candidates


def stats() -> dict:
    return {"calls": STATS.get("calls", 0), "dropped": STATS.get("dropped", 0), "reasons": dict(STATS.get("reasons", {})),
            "use_calls": dict(STATS.get("use_calls", {})), "use_dropped": dict(STATS.get("use_dropped", {}))}

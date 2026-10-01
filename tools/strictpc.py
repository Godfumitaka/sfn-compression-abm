"""照合の直し：親子の並行連結（2026-10-01 朝の委任書「照合の直し（親子の並行連結）と照合器の検査」の 1）。旗 --strict-pc（既定オフ）。
★ abm/ は変えない。sme._alignment_candidates（照合の候補の一覧。fix2・v39・ustruct の差し替えを含む）をいちばん外側で包む。旗を切れば何もしない。

決まり（アストラさんの決定：本来の SME に忠実に、子が合わない親は対にしない）
  親の候補の対（基の行 l, 相手の行 r）は、その relation_pairs のすべての子の対 (l_c, r_c) が次のどちらかのときだけ、採れる候補とする。
    (a) r_c が相手の場面に見えていない（相手の場面の関係の ID に無い。伏せた関係など。F-1 の第三分岐。今どおり写してよい）。
    (b) (l_c, r_c) 自体が、同じ照合の直接の対の候補の一覧にあり（F・H・U の名前の条件は今の候補の作り方のまま）、
        かつその子の対もこの決まりで採れる候補である（下へ再帰。一度決めた答えは控える）。
  採れる候補だけを、元の並びのまま照合の手順（tools/fixorder2.py の map_graphs）に渡す。採る段で子の対が今の写像と食い違えば親を採らない
  決まりは、今の sme._candidate_fits のまま（写像器の側は変えない）。
穴の直し（2026-10-01 午前・改訂の段 1。この旗の中だけ）
  1 基の側の見えていない関係：照合のグラフが定義のグラフでない（v39・fix2 の差し替えの対象でない）とき、候補の作り方を cands_ext に替える。
    abm/sme.py の作り方の写しに、「基の引数が基の場面の関係でも物でもない ID で、相手の引数が見えている関係なら、関係の子の対にする」を足したもの。
    並行連結の確かめでは、基の子が基の関係でも物でも U の席でもなければ (a) と同じく許す。
  2 物の伝播（tools/fixorder2.py:189-215）で、U の席の表（tools/ustruct.py UREG）にある関係の ID を物として伝えない（fixorder2.PROP_EXCLUDE に入れる）。
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


def _registered(base_graph) -> bool:
    """照合のグラフが v39・fix2 の差し替えの対象（定義のグラフ）か。対象でなければ、候補は元の abm/sme.py の作り方。"""
    for name in ("v39", "fix2"):
        m = sys.modules.get(name)
        if m is not None:
            e = getattr(m, "REG", {}).get(id(base_graph))
            if e is not None and e[0] is base_graph:
                return True
    return False


def cands_ext(base_graph, partial_graph):
    """abm/sme.py:280-323 の候補の作り方の写し。★ の所だけ違う（2026-10-01 午前・改訂の段 1 の 1）：
    基の引数が基の場面の関係でも物でもない ID（基の場面で伏せられていた関係）で、相手の引数が見えている関係なら、関係の子の対にする。"""
    import abm.sme as sme
    from abm.sme import AlignmentCandidate
    base_relation_ids = sme._relation_ids(base_graph)
    base_entity_ids = frozenset(e.entity_id for e in base_graph.entities)
    partial_relation_ids = sme._relation_ids(partial_graph)
    partial_entity_ids = frozenset(e.entity_id for e in partial_graph.entities)
    candidates = []
    n_ext = 0
    for left in sorted(base_graph.relations, key=sme._relation_key):
        for right in sorted(partial_graph.relations, key=sme._relation_key):
            if left.predicate != right.predicate or len(left.arguments) != len(right.arguments):
                continue
            entity_pairs, relation_pairs = [], []
            compatible = True
            ext = False
            for left_arg, right_arg in zip(left.arguments, right.arguments, strict=True):
                left_is_relation = left_arg in base_relation_ids
                right_is_relation = right_arg in partial_relation_ids
                right_is_unobserved = (not right_is_relation) and (right_arg not in partial_entity_ids)
                if left_is_relation and right_is_unobserved:
                    relation_pairs.append((left_arg, right_arg))
                    continue
                # ★ 基の側の見えていない関係 ↔ 相手の見えている関係
                left_is_unobserved = (not left_is_relation) and (left_arg not in base_entity_ids)
                if left_is_unobserved and right_is_relation:
                    relation_pairs.append((left_arg, right_arg))
                    ext = True
                    continue
                if left_is_relation != right_is_relation:
                    compatible = False
                    break
                if left_is_relation:
                    relation_pairs.append((left_arg, right_arg))
                else:
                    entity_pairs.append((left_arg, right_arg))
            if compatible:
                n_ext += ext
                candidates.append(AlignmentCandidate(base_relation_id=left.relation_id, partial_relation_id=right.relation_id,
                                                     predicate=left.predicate, arity=len(left.arguments),
                                                     entity_pairs=tuple(sorted(entity_pairs)), relation_pairs=tuple(sorted(relation_pairs))))
    return tuple(sorted(candidates, key=sme._candidate_order_key)), n_ext


def filter_candidates(cands, base_graph, partial_graph):
    """採れる候補だけを、元の並びのまま返す。あわせて (落とした数, 理由の Counter, (c) で許した U の子の数) を返す。"""
    partial_ids = frozenset(r.relation_id for r in partial_graph.relations)
    partial_by_id = {r.relation_id: r for r in partial_graph.relations}
    partial_ents = frozenset(e.entity_id for e in partial_graph.entities)
    base_ids = frozenset(r.relation_id for r in base_graph.relations)
    urows = {}
    if "ustruct" in sys.modules:
        urows = sys.modules["ustruct"].UREG.get(id(base_graph), {}) or {}
    def_ids = base_ids | frozenset(urows) | RELPOS.get(id(base_graph), frozenset())
    base_ents = frozenset(e.entity_id for e in base_graph.entities) - RELPOS.get(id(base_graph), frozenset())
    if MODE[0] == "ii":
        base_ents = base_ents - NONROW.get(id(base_graph), frozenset())
    direct = {(c.base_relation_id, c.partial_relation_id): c for c in cands}
    bpred = {r.relation_id: r.predicate for r in base_graph.relations}
    tpred = {r.relation_id: r.predicate for r in partial_graph.relations}
    memo: dict = {}
    why: dict = {}
    allowed_u = Counter()

    def child_ok(lc, rc):
        """子の対 (lc, rc) が (a)(b)(c) のどれかを満たすか。満たさなければ理由を返す（満たせば None）。"""
        if rc not in partial_ids:
            return None                                          # (a)
        if lc not in base_ids and lc not in urows and lc not in base_ents:
            allowed_u["基の側の見えていない子"] += 1                  # (a) と同じ扱い（段 1 の 1）
            return None
        if lc in base_ids:                                       # (b)
            c = direct.get((lc, rc))
            if c is None:
                return f"子の対が無い：{bpred.get(lc, '?')}≠{tpred.get(rc, '?')}" if bpred.get(lc) != tpred.get(rc) else "子の対が無い（名は同じ）"
            return None if ok(c) else "子の対が採れない（その下で落ちた）"
        u = urows.get(lc)                                        # (c) U の席
        if u is None:
            return "基の子が照合のグラフに無く、U の席でもない"
        C = partial_by_id[rc]
        if len(u.arguments) != len(C.arguments):
            return "U の子：引数の数が合わない"
        for ua, ca in zip(u.arguments, C.arguments):
            ua_rel = ua in def_ids
            ca_rel = ca in partial_ids
            ca_unobs = (not ca_rel) and (ca not in partial_ents)
            if ua_rel and (ca_rel or ca_unobs):
                r = child_ok(ua, ca)
                if r is not None:
                    return f"U の子の下で：{r}"
            elif ua_rel or ca_rel or ca_unobs:
                return "U の子：引数の種類が合わない"
        allowed_u["(c) で許した U の子"] += 1
        return None

    def ok(c) -> bool:
        key = (c.base_relation_id, c.partial_relation_id)
        if key in memo:
            return memo[key]
        memo[key] = True   # 循環は無い（子は親の引数）が、念のため
        res = True
        for lc, rc in c.relation_pairs:
            r = child_ok(lc, rc)
            if r is not None:
                res = False
                why[key] = r
                break
        memo[key] = res
        return res

    out = [c for c in cands if ok(c)]
    if SAMPLE:
        for c in cands:
            key = (c.base_relation_id, c.partial_relation_id)
            if not memo[key] and why.get(key) == "子の対が無い（名は同じ）":
                _sample(c, base_graph, partial_graph, base_ids, partial_ids, partial_ents, urows, direct)
    reasons = Counter(why[(c.base_relation_id, c.partial_relation_id)] for c in cands if not memo[(c.base_relation_id, c.partial_relation_id)])
    return tuple(out), len(cands) - len(out), reasons, allowed_u


SAMPLE: list = []    # 環境変数 STRICTPC_SAMPLE（記録だけ）：開いたファイル
PAIRDUMP: list = []  # 環境変数 STRICTPC_PAIRDUMP（記録だけ）：開いたファイルと残りの数


def _kind(x, rel_ids, ent_ids, uids=frozenset()):
    return "U の席" if x in uids else "関係" if x in rel_ids else "物" if x in ent_ids else "見えていない ID"


def _sample(c, base_graph, partial_graph, base_ids, partial_ids, partial_ents, urows, direct):
    """段 2：名は同じだが子の対の候補が無いために落ちた親の候補の、最初に引っかかった子の中身（記録だけ）。"""
    import json
    bby = {r.relation_id: r for r in base_graph.relations}
    tby = {r.relation_id: r for r in partial_graph.relations}
    bents = frozenset(e.entity_id for e in base_graph.entities)
    for lc, rc in c.relation_pairs:
        if rc in partial_ids and lc in base_ids and (lc, rc) not in direct and bby[lc].predicate == tby[rc].predicate:
            L, R = bby[lc], tby[rc]
            rec = {"大きさ": len(base_graph.relations) + len(partial_graph.relations), "使い道": _use(),
                   "基は定義のグラフか": any(n.startswith("definition:") for n in (base_graph.graph_id,)), "親": [c.base_relation_id, c.partial_relation_id, c.predicate],
                   "基の子": [L.relation_id, L.predicate, list(L.arguments), [_kind(a, base_ids, bents, frozenset(urows)) for a in L.arguments]],
                   "相手の子": [R.relation_id, R.predicate, list(R.arguments), [_kind(a, partial_ids, partial_ents) for a in R.arguments]],
                   "基の子の引数の関係": {a: [bby[a].predicate, list(bby[a].arguments)] for a in L.arguments if a in bby},
                   "相手の子の引数の関係": {a: [tby[a].predicate, list(tby[a].arguments)] for a in R.arguments if a in tby},
                   "基の子の引数の U の席": {a: [urows[a].predicate, list(urows[a].arguments)] for a in L.arguments if a in urows},
                   "基のグラフ": [[r.relation_id, r.predicate, list(r.arguments)] for r in base_graph.relations],
                   "基の物": [e.entity_id for e in base_graph.entities],
                   "相手のグラフ": [[r.relation_id, r.predicate, list(r.arguments)] for r in partial_graph.relations],
                   "相手の物": [e.entity_id for e in partial_graph.entities]}
            SAMPLE[0].write(json.dumps(rec, ensure_ascii=False) + "\n")
            return


def _pairdump(real_select):
    """段 3：予測で選ばれた定義と提示の場面の組を、照合の前の候補の一覧（直しの前）と照合器の写像と一緒に書く（記録だけ）。"""
    import json
    import v39

    def select_definition(state, scene, config):
        res = real_select(state, scene, config)
        if res is not None and PAIRDUMP and PAIRDUMP[1] > 0:
            _r, _s, d, _g, al, _n, _tie, _passed = res
            g = v39.v39_graph(d, state.slot_history)
            try:
                raw = PREV[0](g, scene)
                ur = dict(sys.modules["ustruct"].UREG.get(id(g), {})) if "ustruct" in sys.modules else {}
            finally:
                v39.unregister(g)
            rec = {"基": [[r.relation_id, r.predicate, list(r.arguments)] for r in g.relations],
                   "基の物": sorted({a for r in g.relations for a in r.arguments if a not in {x.relation_id for x in g.relations} and a not in ur}),
                   "U の席": [[r.relation_id, r.predicate, list(r.arguments)] for r in ur.values()],
                   "相手": [[r.relation_id, r.predicate, list(r.arguments)] for r in scene.relations],
                   "相手の物": [e.entity_id for e in scene.entities],
                   "候補（直しの前）": [[c.base_relation_id, c.partial_relation_id, [list(x) for x in c.entity_pairs], [list(x) for x in c.relation_pairs]] for c in raw],
                   "照合器の関係": dict(al.relation_mapping), "照合器の物": dict(al.entity_mapping), "照合器の点": al.total_score}
            PAIRDUMP[0].write(json.dumps(rec, ensure_ascii=False) + "\n")
            PAIRDUMP[1] -= 1
        return res
    return select_definition


PREV: list = []

# ---------------------------------------------------------------- 定義の行の引数の種類の控え（2026-10-01 11 時台の返事、段 3.5 の (iii)）
# 控え方：本人が見た場面（本物の試行の会計の段の入口の提示。試験の場面は入れない）の関係ごとに、引数の種類を決めて控える。
#   場面の関係の ID なら「関係」、場面の物の一覧にあれば「物」、どちらでもない（伏せられていた関係を指す ID）なら「関係」。研究者の側の情報は使わない。
#   定義の行は、本人が前に見た場面（逐語の記憶の場面）の関係なので、行の関係 ID ごとの控え（KINDS）で、誕生・同化・仮の誕生のどれでも同じ種類になる。
# 使い方：定義のグラフ（tools/v39.py v39_graph）を作るとき、行でない引数のうち控えた種類が関係のもの（RELPOS）を物の一覧から外す。
#   照合の候補（v39・ustruct の LEFT_REL）では、それを「まだ分からない関係の位置」とし、相手の見えている関係・見えていない ID と関係の子の対にする。
#   並行連結の確かめでは、見えていない子と同じく許す（基の側の見えていない子）。
# 費用：tools/v39.py structure_bits の引数の符号を、控えた種類で数える（関係なら clog2(行の数)、物の数からは外す）。差を STATS に残す。
KINDS: dict = {}       # 関係 ID → 引数ごとの種類（"関係"／"物"）の組
RELPOS: dict = {}      # id(定義のグラフ) → 行でない引数のうち、控えた種類が関係のもの
NONROW: dict = {}      # id(定義のグラフ) → 行でない引数（(ii) の記録用）
MODE: list = ["iii"]   # "iii"（本番）／"ii"（記録だけ：種類を相手の側で決める）


def record_kinds(scene, extra=()):
    """extra：開示で本人に届いた関係（会計の段の入口で、開示があればその関係も同じ見分けで控える）。"""
    rel = {r.relation_id for r in scene.relations} | {r.relation_id for r in extra}
    ent = {e.entity_id for e in scene.entities}
    for r in tuple(scene.relations) + tuple(extra):
        if r.relation_id not in KINDS:
            KINDS[r.relation_id] = tuple("関係" if a in rel else "物" if a in ent else "関係" for a in r.arguments)


def _relpos_of(d):
    rel_ids = {row.relation.relation_id for row in d.constituents}
    out, nonrow, missing = set(), set(), 0
    for row in d.constituents:
        k = KINDS.get(row.relation.relation_id)
        if k is None:
            missing += 1
        for i, a in enumerate(row.relation.arguments):
            if a in rel_ids:
                continue
            nonrow.add(a)
            if k is not None and i < len(k) and k[i] == "関係":
                out.add(a)
    return frozenset(out), frozenset(nonrow), missing


def _left_rel(g, a, right_is_relation):
    if MODE[0] == "off":
        return False
    if MODE[0] == "ii":
        return a in NONROW.get(id(g), ()) and right_is_relation
    return a in RELPOS.get(id(g), ())


def _install_kinds():
    import abm.loop as loop
    import v39
    from abm.domains import Entity, RelationGraph
    real_acc = loop._update_accounting

    def update_accounting(state, output, scene, config, horizon_, score, coin, revealed_edge):
        record_kinds(scene, (revealed_edge,) if (coin.f_fired and revealed_edge is not None) else ())
        return real_acc(state, output, scene, config, horizon_, score, coin, revealed_edge)

    loop._update_accounting = update_accounting
    real_graph, real_unreg = v39.v39_graph, v39.unregister

    def v39_graph(d, slot_history):
        g = real_graph(d, slot_history)
        relpos, nonrow, missing = _relpos_of(d)
        STATS["kinds_missing_rows"] += missing
        if MODE[0] == "off":
            SHADOW[id(g)] = relpos
            return g
        if MODE[0] == "ii" or not relpos:
            NONROW[id(g)] = nonrow
            return g
        g2 = RelationGraph(graph_id=g.graph_id, entities=tuple(e for e in g.entities if e.entity_id not in relpos), relations=g.relations)
        entry = v39.REG.pop(id(g))
        v39.REG[id(g2)] = (g2, entry[1], entry[2])
        us = sys.modules.get("ustruct")
        if us is not None and id(g) in us.UREG:
            us.UREG[id(g2)] = us.UREG.pop(id(g))
        RELPOS[id(g2)] = relpos
        NONROW[id(g2)] = nonrow
        if KINDLOG:
            import json
            for row in d.constituents:
                k = KINDS.get(row.relation.relation_id)
                if k is not None:
                    KINDLOG[0].write(json.dumps([row.relation.relation_id, list(row.relation.arguments), list(k)]) + "\n")
        return g2

    def unregister(g):
        SHADOW.pop(id(g), None)
        RELPOS.pop(id(g), None)
        NONROW.pop(id(g), None)
        real_unreg(g)

    v39.v39_graph = v39_graph
    v39.unregister = unregister
    v39.LEFT_REL.clear()
    v39.LEFT_REL.append(_left_rel)
    real_sb = v39.structure_bits

    def structure_bits(d):
        old = real_sb(d)
        relpos, _nonrow, _m = _relpos_of(d)
        if not relpos or MODE[0] == "off":
            return old
        rel_ids = {row.relation.relation_id for row in d.constituents}
        ents = {a for row in d.constituents for a in row.relation.arguments if a not in rel_ids and a not in relpos}
        m = len({row.slot_index for row in d.constituents})
        e = len(ents)
        bits = v39.clog2(v39.CFG["T"]) + v39.I(m) + v39.I(e)
        for row in d.constituents:
            bits += v39.I(len(row.relation.arguments))
            for a in row.relation.arguments:
                bits += 1 + (v39.clog2(m) if (a in rel_ids or a in relpos) else v39.clog2(e))
        STATS["struct_calls_changed"] += 1
        STATS["struct_bits_diff"] += bits - old
        return bits

    v39.structure_bits = structure_bits
    real_map = v39.map_v39

    def map_v39(d, slot_history, scene):
        g, al = real_map(d, slot_history, scene)
        if ALT_II:
            # 記録だけ：(ii)（種類を相手の側で決める）なら写像が変わったか。本番の写像には何も返さない
            MODE[0] = "ii"
            try:
                _g2, al2 = real_map(d, slot_history, scene)
            finally:
                MODE[0] = "iii"
            STATS["alt_ii_calls"] += 1
            if dict(al.relation_mapping) != dict(al2.relation_mapping) or dict(al.entity_mapping) != dict(al2.entity_mapping):
                STATS["alt_ii_changed"] += 1
                for row in d.constituents:
                    rid = row.relation.relation_id
                    if al.relation_mapping.get(rid) != al2.relation_mapping.get(rid):
                        STATS["alt_ii_seat_" + v39.seat_state(d, row, slot_history)] += 1
        return g, al

    v39.map_v39 = map_v39


KINDLOG: list = []
ALT_II: list = []
SHADOW: dict = {}     # "off" のとき：id(定義のグラフ) → 控えから見た RELPOS（使わない。5 例の確かめ用）
PROBE: list = []      # 環境変数 STRICTPC_PROBE（5 例の確かめ）：[{親の対, 基の子, 相手の子}] と結果のファイル


def _probe5(prev, cands, out, g, T):
    import json
    keep = {(c.base_relation_id, c.partial_relation_id) for c in out}
    have = {(c.base_relation_id, c.partial_relation_id) for c in cands}
    for ex in PROBE[0]:
        par = tuple(ex["親"][:2])
        if par in have and par not in keep and ex["基の子"][0] in {r.relation_id for r in g.relations}:
            MODE[0] = "iii"
            RELPOS[id(g)] = SHADOW[id(g)]
            try:
                c2 = prev(g, T)
                o2, n2, r2, _u = filter_candidates(c2, g, T)
            finally:
                RELPOS.pop(id(g), None)
                MODE[0] = "off"
            PROBE[1].write(json.dumps({"親": list(par), "控えを使わない：親が残る": False, "控えを使う：親が残る": par in {(c.base_relation_id, c.partial_relation_id) for c in o2},
                                       "控えを使わない：落とした親の候補": len(cands) - len(out), "控えを使う：落とした親の候補": n2,
                                       "控えから見た関係の位置": sorted(SHADOW[id(g)])}, ensure_ascii=False) + "\n")
            PROBE[1].flush()


def install() -> None:
    """ほかの候補の差し替え（fix2・v39・ustruct）のあと、照合を使う前に入れる。"""
    import abm.sme as sme
    STATS.clear()
    STATS.update(calls=0, dropped=0, u_allowed=0, ext_cands=0, unobs_base_allowed=0, kinds_missing_rows=0, struct_calls_changed=0,
                 struct_bits_diff=0, alt_ii_calls=0, alt_ii_changed=0, alt_ii_seat_F=0, alt_ii_seat_H=0, alt_ii_seat_U=0, reasons=Counter(), use_calls=Counter(), use_dropped=Counter())
    prev = sme._alignment_candidates
    PREV.clear()
    PREV.append(prev)
    import os
    SAMPLE.clear()
    PAIRDUMP.clear()
    if os.environ.get("STRICTPC_SAMPLE"):
        SAMPLE.append(open(os.environ["STRICTPC_SAMPLE"], "w", encoding="utf-8"))
    KINDS.clear()
    RELPOS.clear()
    NONROW.clear()
    KINDLOG.clear()
    ALT_II.clear()
    MODE[0] = "off" if os.environ.get("STRICTPC_KINDS_OFF") else "iii"
    SHADOW.clear()
    PROBE.clear()
    if os.environ.get("STRICTPC_PROBE"):
        import json as _j
        PROBE.extend([_j.load(open(os.environ["STRICTPC_PROBE"], encoding="utf-8")), open(os.environ["STRICTPC_PROBE"] + ".out", "w", encoding="utf-8")])
    if os.environ.get("STRICTPC_KINDLOG"):
        KINDLOG.append(open(os.environ["STRICTPC_KINDLOG"], "w", encoding="utf-8"))
    if os.environ.get("STRICTPC_ALT_II"):
        ALT_II.append(True)
    if "v39" in sys.modules:
        _install_kinds()
    if os.environ.get("STRICTPC_PAIRDUMP"):
        import v39
        PAIRDUMP.extend([open(os.environ["STRICTPC_PAIRDUMP"], "w", encoding="utf-8"), int(os.environ.get("STRICTPC_PAIRDUMP_N", "3000"))])
        v39.select_definition = _pairdump(v39.select_definition)

    def _alignment_candidates(base_graph, partial_graph):
        if _registered(base_graph):
            cands = prev(base_graph, partial_graph)
        else:
            cands, n_ext = cands_ext(base_graph, partial_graph)
            STATS["ext_cands"] += n_ext
        out, n, reasons, allowed_u = filter_candidates(cands, base_graph, partial_graph)
        if PROBE and id(base_graph) in SHADOW:
            _probe5(prev, cands, out, base_graph, partial_graph)
        STATS["u_allowed"] += allowed_u["(c) で許した U の子"]
        STATS["unobs_base_allowed"] += allowed_u["基の側の見えていない子"]
        u = _use()
        STATS["calls"] += 1
        STATS["dropped"] += n
        STATS["reasons"].update(reasons)
        STATS["use_calls"][u] += 1
        STATS["use_dropped"][u] += n
        return out

    sme._alignment_candidates = _alignment_candidates
    # ★ 段 1 の 2：物の伝播で、U の席の表（tools/ustruct.py UREG）にある関係の ID を物として伝えない
    if "fixorder2" in sys.modules:
        fo2 = sys.modules["fixorder2"]
        fo2.PROP_EXCLUDE.clear()
        fo2.PROP_EXCLUDE.append(lambda g: frozenset(sys.modules["ustruct"].UREG.get(id(g), {}) or {}) if "ustruct" in sys.modules else frozenset())


def stats() -> dict:
    for f in (SAMPLE[:1] + PAIRDUMP[:1] + KINDLOG[:1]):
        f.flush()
    return {"calls": STATS.get("calls", 0), "dropped": STATS.get("dropped", 0), "u_allowed": STATS.get("u_allowed", 0), "ext_cands": STATS.get("ext_cands", 0),
            "unobs_base_allowed": STATS.get("unobs_base_allowed", 0),
            **{k: STATS.get(k, 0) for k in ("kinds_missing_rows", "struct_calls_changed", "struct_bits_diff", "alt_ii_calls", "alt_ii_changed",
                                            "alt_ii_seat_F", "alt_ii_seat_H", "alt_ii_seat_U")}, "reasons": dict(STATS.get("reasons", {})),
            "use_calls": dict(STATS.get("use_calls", {})), "use_dropped": dict(STATS.get("use_dropped", {}))}

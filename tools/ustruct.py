"""U の照合（旗 --u-struct）。2026-09-30 の委任書「U の照合の直し・覚え直しの初期の評価・支持の三分類」の 1。
★ abm/ は変えない。旗を切れば何もしない（v3.10hsa-main と一字一句同じ）。

1 --u-struct（--v39 と --hist-role と一緒に使う）
  今：U の席は照合のグラフに置かない。U の子を持つ親の引数は、見えている関係・物には当てはまらず、見えていない ID にだけ当てはまる（tools/v39.py _install_candidates）。
  直し：U の席を、名前の条件を持たない関係の位置として、構造の照合に参加させる。
    U の席そのものは照合の候補にならない（グラフに置かないのは今のまま。支持の分子にも分母にも入らない）。
    U の子を持つ親の候補を作るとき、U の子の引数は次のとおり当てはめる。
      見えている物：当てはまらない（関係と物の区別）。
      見えている関係 C：U の席の行と C の引数の数が同じなら当てはまる。このとき U の席の行の引数も C の引数と対にする
        （行の引数が定義の関係なら関係と、物なら見えている物と。種類が違えば当てはまらない）。
        対は親の候補に入るので、既存の物・関係の対応と食い違えば、その親の候補は採られない（map_graphs の _candidate_fits）。
      見えていない ID：今のまま当てはまる。
    一つの候補の中で、同じ左が二つの右に、又は二つの左が同じ右に当たるなら、その候補は作らない（同じ席を複数の位置へ当てはめない）。
    親自身の名前の条件は今のまま（F は名前の一致、H は履歴の名）。忘れた名前（U の席の名）は照合に使わない（U の席の行の述語は見ない）。
  U の席の観察（m1 の席の履歴）：親が照合で写れば、その親の同じ引数の位置の子を U の席の対応先にし、子が見えていればその述語を観察として足す
    （tools/histrole.py の親の子の規則を、U の席については階を問わず使う。親が無い・写らない・子が見えないときは足さない）。
（2 の覚え直しの初期の評価は tools/relearninit.py、旗 --relearn-init）
"""
from __future__ import annotations

CFG: dict = {}
STATS: dict = {}
UREG: dict = {}      # id(g) → {U の席の関係 ID: Relation}


def u_candidates(prev):
    def _alignment_candidates(base_graph, partial_graph):
        import abm.sme as sme
        import v39
        from abm.sme import AlignmentCandidate
        entry = v39.REG.get(id(base_graph))
        if entry is None or entry[0] is not base_graph:
            return prev(base_graph, partial_graph)
        _, hallow, ushield = entry
        urows = UREG.get(id(base_graph), {})
        base_relation_ids = sme._relation_ids(base_graph)
        def_rel_ids = base_relation_ids | ushield
        partial_by_id = {r.relation_id: r for r in partial_graph.relations}
        partial_relation_ids = frozenset(partial_by_id)
        partial_entity_ids = frozenset(e.entity_id for e in partial_graph.entities)
        candidates = []
        for left in sorted(base_graph.relations, key=sme._relation_key):
            allowed = hallow.get(left.relation_id)
            for right in sorted(partial_graph.relations, key=sme._relation_key):
                if len(left.arguments) != len(right.arguments):
                    continue
                if right.predicate != left.predicate and (allowed is None or right.predicate not in allowed):
                    continue
                entity_pairs = []
                relation_pairs = []
                compatible = True
                upair = False
                for left_arg, right_arg in zip(left.arguments, right.arguments, strict=True):
                    if left_arg in ushield:
                        if right_arg in partial_entity_ids:
                            compatible = False
                            break
                        if right_arg in partial_relation_ids:
                            # ★ --u-struct：U の子が見えている関係に当てはまる（引数の数・種類・物の対応を守る）
                            u = urows.get(left_arg)
                            C = partial_by_id[right_arg]
                            if u is None or len(u.arguments) != len(C.arguments):
                                compatible = False
                                break
                            upair = True
                            relation_pairs.append((left_arg, right_arg))
                            for ua, ca in zip(u.arguments, C.arguments):
                                if ua in def_rel_ids or (v39.LEFT_REL[0](base_graph, ua, ca in partial_relation_ids) if v39.LEFT_REL else False):
                                    if ca in partial_entity_ids:
                                        compatible = False
                                        break
                                    relation_pairs.append((ua, ca))
                                elif ca in partial_entity_ids:
                                    entity_pairs.append((ua, ca))
                                else:
                                    compatible = False
                                    break
                            if not compatible:
                                break
                            continue
                        relation_pairs.append((left_arg, right_arg))
                        continue
                    left_is_relation = left_arg in base_relation_ids or (v39.LEFT_REL[0](base_graph, left_arg, right_arg in partial_relation_ids)
                                                                         if v39.LEFT_REL else False)
                    right_is_relation = right_arg in partial_relation_ids
                    right_is_unobserved = (not right_is_relation) and (right_arg not in partial_entity_ids)
                    if left_is_relation and right_is_unobserved:
                        relation_pairs.append((left_arg, right_arg))
                        continue
                    if left_is_relation != right_is_relation:
                        compatible = False
                        break
                    if left_is_relation:
                        relation_pairs.append((left_arg, right_arg))
                    else:
                        entity_pairs.append((left_arg, right_arg))
                if compatible and upair:
                    # ★ U の子を見えている関係に当てはめた候補だけ：候補の中の食い違いを確かめ、重複を除く（ほかの候補は今と同じ形）
                    if not _consistent(entity_pairs, relation_pairs, left.relation_id, right.relation_id):
                        STATS["cand_inconsistent"] = STATS.get("cand_inconsistent", 0) + 1
                        compatible = False
                    else:
                        entity_pairs, relation_pairs = sorted(set(entity_pairs)), sorted(set(relation_pairs))
                        STATS["cand_u_visible"] = STATS.get("cand_u_visible", 0) + 1
                if compatible:
                    candidates.append(AlignmentCandidate(
                        base_relation_id=left.relation_id, partial_relation_id=right.relation_id,
                        predicate=left.predicate, arity=len(left.arguments),
                        entity_pairs=tuple(sorted(entity_pairs)), relation_pairs=tuple(sorted(relation_pairs))))
        return tuple(sorted(candidates, key=sme._candidate_order_key))
    return _alignment_candidates


def _consistent(entity_pairs, relation_pairs, left_id, right_id) -> bool:
    """一つの候補の中で、同じ左が二つの右に、又は二つの左が同じ右に当たらないか（親自身の対も含める）。"""
    for pairs in (entity_pairs, list(relation_pairs) + [(left_id, right_id)]):
        fw, bw = {}, {}
        for a, b in pairs:
            if fw.setdefault(a, b) != b or bw.setdefault(b, a) != a:
                return False
    return True


def install_matching():
    """照合の差し替えだけを入れる（v39_graph に U の席の行を控えさせ、候補の規則を包む）。元に戻す関数を返す。"""
    import abm.sme as sme
    import v39
    real_graph, real_unreg, real_cands = v39.v39_graph, v39.unregister, sme._alignment_candidates

    def v39_graph(d, slot_history):
        g = real_graph(d, slot_history)
        _, _hallow, ushield = v39.REG[id(g)]
        UREG[id(g)] = {row.relation.relation_id: row.relation for row in d.constituents if row.relation.relation_id in ushield}
        return g

    def unregister(g):
        UREG.pop(id(g), None)
        real_unreg(g)

    v39.v39_graph = v39_graph
    v39.unregister = unregister
    sme._alignment_candidates = u_candidates(real_cands)

    def undo():
        v39.v39_graph, v39.unregister, sme._alignment_candidates = real_graph, real_unreg, real_cands
    return undo


def install(fo) -> None:
    """tools/v3_run.py の worker で、v39・v310be のあとに入れる。"""
    import histrole
    CFG.clear()
    STATS.clear()
    UREG.clear()
    install_matching()
    histrole.CFG["u_all_orders"] = True

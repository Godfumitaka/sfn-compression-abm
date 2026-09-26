"""直し②（2026-09-26 夕、アストラさんの指示）：墓石を子に持つ高階の行の照らし方。旗 --fix2（既定オフ）。★ abm/ は変えない。

今の動き（旗オフ）
  同定（identification_graph="live"）と話すときの支持（agent_runtime._definition_graph）の定義のグラフは、関係に生きている行だけを置く。
  墓石の子の関係 ID は、グラフの関係にも実体にも入らない（abstraction.py:316-331、agent_runtime.py:246-260）。
  そのため写し（sme._alignment_candidates、sme.py:280-323）では、墓石の子の引数は「関係でない」側として扱われ、
    場面でその位置の関係が見えていれば、親の行は対にならない（関係 対 関係でない、sme.py:305-307）。
    伏せられていれば、実体どうしの対として対になる（sme.py:310-311）。
直し②（旗オン）
  墓石の子の引数を、墓石の席（定義 R・その行の slot_index）の slot_history で照らす。
    場面でその位置の関係が見えているとき：その述語が、墓石の席の slot_history に回数 1 以上で入っていれば当てはまる
      （関係どうしの対にする）。入っていなければ当てはまらない（親の行は対にならない）。
    伏せられているとき（相手の側で関係でも実体でもない）：ほかの伏せられた位置と同じく「見えていない枠」として扱う
      （sme.py:298-304 の F-1 と同じく、関係どうしの対にする）。
    相手の側で実体のとき：当てはまらない（生きている子の関係と同じ扱い）。
  入れる所は二つだけ（アストラさんの指示）
    1 同化の照らし（同定）：tools/v32.py の同定の中で、定義のグラフに墓石の子の情報を付ける（自己の点にも同じ規則が効く）。
    2 話すときの支持：agent_runtime._select_definition を差し替え、支持（と支持比による定義の選び方・τ の門）だけを直し②の写しで数える。
      ★ --fix2 では、選んだ定義の投影・穴埋め・会計に渡す写しは、今と同じ写し（直し②なし）のまま。
    3 予測と会計（--fix2-full、2026-09-26 夜、アストラさんの決定）：選んだ定義の写しとして、直し②の写しをそのまま渡す。
      投影（agent_runtime.py:125-130）・穴埋め（:135-146）・会計（loop.py:205 の definition_alignment。classify_row・②・①）が同じ写しを使う。
      → 墓石を子に持つ親の行は、子が見えていて席の履歴にあれば、選ぶときも会計でも「当てはまる」（充足）。
      → その墓石の子の行は、見えている関係に写るので、穴埋め（filling.py:175-196「写った先が見えている行は埋めない」）の対象から外れる。
  墓石の子の無い定義のグラフは、今と同じ（同じ写しを使う）。
仕組み：墓石の子の情報は、グラフの物そのもの（id と参照の一致）に結びつけて REG に控え、差し替えた _alignment_candidates が読む。
  控えは使い終わったらすぐ消す。REG に無いグラフの写しは、元の _alignment_candidates をそのまま呼ぶ。
"""
from __future__ import annotations

from collections.abc import Mapping

STATS: dict = {}
REG: dict[int, tuple[object, dict[str, frozenset[str]]]] = {}


def tomb_allowed(graph, definition, slot_history) -> dict[str, frozenset[str]]:
    """グラフの生きている行の引数に現れる墓石の子の関係 ID → 墓石の席の slot_history で回数 1 以上の述語。"""
    tomb_slot = {c.relation.relation_id: c.slot_index for c in definition.constituents if not c.alive}
    if not tomb_slot:
        return {}
    out: dict[str, frozenset[str]] = {}
    for r in graph.relations:
        for a in r.arguments:
            if a in tomb_slot and a not in out:
                h = slot_history.get((definition.name, tomb_slot[a]))
                if isinstance(h, Mapping):
                    ok = frozenset(p for p, n in h.items() if n >= 1)
                elif h is None:
                    ok = frozenset()
                else:
                    ok = frozenset(h)
                out[a] = ok
    return out


def register(graph, definition, slot_history) -> bool:
    allowed = tomb_allowed(graph, definition, slot_history)
    if not allowed:
        return False
    REG[id(graph)] = (graph, allowed)
    STATS["registered"] = STATS.get("registered", 0) + 1
    STATS["tomb_child_links"] = STATS.get("tomb_child_links", 0) + len(allowed)
    return True


def unregister(graph) -> None:
    REG.pop(id(graph), None)


def install(full: bool = False) -> None:
    import abm.agent_runtime as ar
    import abm.sme as sme
    from abm.sme import AlignmentCandidate

    STATS.clear()
    STATS.update(registered=0, tomb_child_links=0, visible_ok=0, visible_ng=0, hidden=0, entity_ng=0,
                 select_calls=0, select_changed_support=0, full=full)
    original = sme._alignment_candidates

    def _alignment_candidates(base_graph, partial_graph):
        entry = REG.get(id(base_graph))
        if entry is None or entry[0] is not base_graph:
            return original(base_graph, partial_graph)
        tomb = entry[1]
        # ★ ここから sme.py:284-323 と同じ。墓石の子の引数だけ、直し②の規則で見る。
        base_relation_ids = sme._relation_ids(base_graph)
        partial_relation_ids = sme._relation_ids(partial_graph)
        partial_entity_ids = frozenset(e.entity_id for e in partial_graph.entities)
        partial_pred = {r.relation_id: r.predicate for r in partial_graph.relations}
        candidates = []
        for left in sorted(base_graph.relations, key=sme._relation_key):
            for right in sorted(partial_graph.relations, key=sme._relation_key):
                if left.predicate != right.predicate or len(left.arguments) != len(right.arguments):
                    continue
                entity_pairs: list[tuple[str, str]] = []
                relation_pairs: list[tuple[str, str]] = []
                compatible = True
                for left_arg, right_arg in zip(left.arguments, right.arguments, strict=True):
                    if left_arg in tomb:
                        # ★ 直し②
                        if right_arg in partial_relation_ids:
                            if partial_pred[right_arg] in tomb[left_arg]:
                                STATS["visible_ok"] += 1
                                relation_pairs.append((left_arg, right_arg))
                                continue
                            STATS["visible_ng"] += 1
                            compatible = False
                            break
                        if right_arg not in partial_entity_ids:
                            STATS["hidden"] += 1
                            relation_pairs.append((left_arg, right_arg))
                            continue
                        STATS["entity_ng"] += 1
                        compatible = False
                        break
                    left_is_relation = left_arg in base_relation_ids
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
                if compatible:
                    candidates.append(AlignmentCandidate(
                        base_relation_id=left.relation_id,
                        partial_relation_id=right.relation_id,
                        predicate=left.predicate,
                        arity=len(left.arguments),
                        entity_pairs=tuple(sorted(entity_pairs)),
                        relation_pairs=tuple(sorted(relation_pairs)),
                    ))
        return tuple(sorted(candidates, key=sme._candidate_order_key))

    sme._alignment_candidates = _alignment_candidates

    def _select_definition(state, scene, config):
        # ★ agent_runtime.py:204-243 と同じ。支持だけを直し②の写しで数え、返す写しは今と同じ写し。
        STATS["select_calls"] += 1
        ranked = []
        for definition in state.definitions.values():
            if definition.m_live == 0:
                continue
            graph = ar._definition_graph(definition)
            alignment = sme.map_graphs(graph, scene).alignment
            if alignment is None:
                continue
            support_alignment = alignment
            if register(graph, definition, state.slot_history):
                try:
                    support_alignment = sme.map_graphs(graph, scene).alignment
                finally:
                    unregister(graph)
            support = sum(
                1 for constituent in definition.constituents
                if constituent.alive
                and constituent.relation.relation_id in support_alignment.relation_mapping
            )
            if support_alignment is not alignment:
                old = sum(1 for c in definition.constituents
                          if c.alive and c.relation.relation_id in alignment.relation_mapping)
                STATS["select_changed_support"] += int(old != support)
            # ★ --fix2-full：予測と会計にも直し②の写しを渡す。--fix2：今と同じ写しを渡す
            ranked.append((support / definition.m_live, support, definition, graph, support_alignment if full else alignment))
        if not ranked:
            return None
        ranked.sort(
            key=lambda item: (-item[0], -item[2].m_live, -item[2].registered_at, item[2].name)
        )
        best = ranked[0]
        tie_event = sum(
            item[0] == best[0]
            and item[2].m_live == best[2].m_live
            and item[2].registered_at == best[2].registered_at
            for item in ranked
        ) > 1
        best_name = best[2].name
        passed = [{"R": definition.name, "support": support, "m_live": definition.m_live,
                   "ratio": ratio, "selected": definition.name == best_name}
                  for ratio, support, definition, _graph, _alignment in ranked
                  if support >= ar._need(config.tau_acc, definition.m_live)]
        return (*best, tie_event, passed)

    ar._select_definition = _select_definition

"""名前・番号に依らない写し（2026-09-26 夜、アストラさんの指示・案 1）。旗 --fix-order2（既定オフ）。★ abm/ は変えない。

★ --fix-order（tools/fixorder.py）の代わりに使う（両方は付けない）。fixorder.py の「親の中身として写った子も、自分の番で
  述語一致の点を数える」規則はそのまま含み、そのうえで、写しの結果が述語の名前・行や物の ID・並び順に依らないようにする。

今の動き（--fix-order、tools/fixorder.py）で名前・番号に依る所
  1 候補の順番：引数の数 → 述語の名前 → 行 ID の順（sme.py:323・:326-327）。先に採った対が勝つ（sme.py:125-138）。
    → 子の番で、先に採った対と食い違って採れない／親子でない候補が同じ物を取り合い、名前の順で先の方が勝つ。
  2 伝播（sme.py:140-155）：写像の対を基の行 ID の順に回し、同じ物に二通りの相手があれば先の方を採る（sme.py:146）。
直し（旗オン）
  1 候補の順番を構造だけで決める。鍵 ＝（高さの合計の小さい順, その対を中身に持つ親の候補の数の多い順, 引数の数の多い順）。
    ・高さ：その行の引数に、同じグラフの行が入っていなければ 0、入っていれば 1 ＋ 子の高さの最大（基・相手の両側で数えて足す）。
      子が先に来るので、親の対は、すでに採った子の対と食い違わないかを sme._candidate_fits で確かめてから採る。
    ・親の候補の数：その（基の行, 相手の行）の対を relation_pairs に含む候補の数。構造に埋まった対（核）が、埋まっていない対（飾り）より先。
    ・同じ鍵の候補は一つの組として扱う。組の中で、今の写像と矛盾しない候補どうしが互いに食い違わなければ、全部採る。
      食い違うものがあれば、食い違いの図の連結ごとに、互いに食い違わない最大の組を全部出し、そのすべてに共通する候補だけを採る
      （どれを採るかを名前や番号で決めない。決まらない所は採らない）。連結が 16 候補を超えるときは、食い違いの無い候補だけを採る。
    ・採らなかった候補は、後の組でも採らない（今と同じく、一度通り過ぎた候補には戻らない）。
  2 伝播は、一通りにしか決まらない対応だけを採る：基の物に相手の候補が一つだけ、かつその相手に基の候補が一つだけのとき。
    それを繰り返す（採ると、ほかの候補が一通りになることがある）。
  ★ 体系性・対にならなかった行の罰・投影の候補の作り方・点の式は sme.py:157-205 と同じ。
★ 採った対の並び（MappingResult.candidates）は、組の順・組の中は候補の元の並び。点の合計には並びは効かない。
入れる所：fixorder.py と同じ（読み込み済みのモジュールで map_graphs が元の関数を指していれば、すべて張り替える）。
  候補は呼ぶときに sme._alignment_candidates を読むので、直し②（tools/fix2.py）の差し替えもそのまま効く。
"""
from __future__ import annotations

import sys
from collections import Counter, defaultdict

STATS: dict = {}
MAX_COMPONENT = 16


def _heights(graph) -> dict[str, int]:
    rels = {r.relation_id: r for r in graph.relations}
    memo: dict[str, int] = {}

    def h(rid: str, seen: frozenset) -> int:
        if rid in memo:
            return memo[rid]
        if rid in seen:
            return 0
        kids = [a for a in rels[rid].arguments if a in rels and a != rid]
        v = 0 if not kids else 1 + max(h(k, seen | {rid}) for k in kids)
        memo[rid] = v
        return v

    return {rid: h(rid, frozenset()) for rid in rels}


def _assignments(pair):
    ents = tuple(pair.entity_pairs)
    rels = ((pair.base_relation_id, pair.partial_relation_id),) + tuple(pair.relation_pairs)
    return ents, rels


def _clash(a, b) -> bool:
    """二つの候補を両方採れないか（一対一の写像として矛盾するか）。"""
    for xs, ys in ((a[0], b[0]), (a[1], b[1])):
        left = {}; right = {}
        for l, r in xs:
            left[l] = r; right[r] = l
        for l, r in ys:
            if (l in left and left[l] != r) or (r in right and right[r] != l):
                return True
    return False


def _max_independent_sets(nodes: list[int], adj: dict[int, set[int]]) -> list[frozenset]:
    best: list[frozenset] = []
    best_n = -1

    def rec(i: int, chosen: frozenset, banned: frozenset) -> None:
        nonlocal best, best_n
        if len(chosen) + (len(nodes) - i) < best_n:
            return
        if i == len(nodes):
            if len(chosen) > best_n:
                best, best_n = [chosen], len(chosen)
            elif len(chosen) == best_n:
                best.append(chosen)
            return
        v = nodes[i]
        if v not in banned:
            rec(i + 1, chosen | {v}, banned | adj[v])
        rec(i + 1, chosen, banned)

    rec(0, frozenset(), frozenset())
    return best


def install() -> None:
    import abm.sme as sme

    original = sme.map_graphs
    STATS.clear()
    STATS.update(calls=0, child_accepted=0, tie_groups_with_clash=0, tie_dropped=0, big_component=0,
                 prop_ambiguous=0)

    def map_graphs(base_graph, target_graph_partial, params=None, *, prototype=None, prototype_prior_weight=0.0):
        """sme.py:105-205（と tools/fixorder.py）の写し。★ の所だけが違う。"""
        STATS["calls"] += 1
        weights = params or sme.SMEParams()
        base_relation_ids = sme._relation_ids(base_graph)
        partial_relation_ids = sme._relation_ids(target_graph_partial)
        pairs = sme._alignment_candidates(base_graph, target_graph_partial)
        entity_mapping: dict[str, str] = {}
        used_entities: dict[str, str] = {}
        relation_mapping: dict[str, str] = {}
        used_relations: dict[str, str] = {}
        accepted = []
        accepted_ids: set[str] = set()

        # ★ 1 構造だけで決める鍵
        hb = _heights(base_graph); ht = _heights(target_graph_partial)
        parents = Counter(rp for p in pairs for rp in p.relation_pairs)

        def key(p):
            return (hb.get(p.base_relation_id, 0) + ht.get(p.partial_relation_id, 0),
                    -parents[(p.base_relation_id, p.partial_relation_id)], -p.arity)

        groups: dict[tuple, list] = defaultdict(list)
        for p in pairs:
            groups[key(p)].append(p)

        def eligible(pair) -> bool:
            if pair.base_relation_id in relation_mapping or pair.partial_relation_id in used_relations:
                # fixorder.py と同じ：親の中身として同じ相手に写った子で、まだ対として採っていないものだけ
                if not (relation_mapping.get(pair.base_relation_id) == pair.partial_relation_id
                        and used_relations.get(pair.partial_relation_id) == pair.base_relation_id
                        and pair.base_relation_id not in accepted_ids):
                    return False
            return sme._candidate_fits(pair, entity_mapping, used_entities, relation_mapping, used_relations)

        def accept(pair) -> None:
            if pair.base_relation_id in relation_mapping:
                STATS["child_accepted"] += 1
            for left, right in pair.entity_pairs:
                entity_mapping[left] = right
                used_entities[right] = left
            for left, right in pair.relation_pairs:
                relation_mapping[left] = right
                used_relations[right] = left
            relation_mapping[pair.base_relation_id] = pair.partial_relation_id
            used_relations[pair.partial_relation_id] = pair.base_relation_id
            accepted.append(pair)
            accepted_ids.add(pair.base_relation_id)

        for k in sorted(groups):
            ok = [p for p in groups[k] if eligible(p)]
            if len(ok) <= 1:
                for p in ok:
                    accept(p)
                continue
            asg = [_assignments(p) for p in ok]
            adj: dict[int, set[int]] = {i: set() for i in range(len(ok))}
            for i in range(len(ok)):
                for j in range(i + 1, len(ok)):
                    if _clash(asg[i], asg[j]):
                        adj[i].add(j); adj[j].add(i)
            take: set[int] = {i for i in adj if not adj[i]}
            if len(take) < len(ok):
                STATS["tie_groups_with_clash"] += 1
                seen: set[int] = set(take)
                for s in range(len(ok)):
                    if s in seen:
                        continue
                    comp, stack = [], [s]
                    seen.add(s)
                    while stack:
                        v = stack.pop(); comp.append(v)
                        for w in adj[v]:
                            if w not in seen:
                                seen.add(w); stack.append(w)
                    comp.sort()
                    if len(comp) > MAX_COMPONENT:
                        STATS["big_component"] += 1
                        STATS["tie_dropped"] += len(comp)
                        continue
                    sets = _max_independent_sets(comp, adj)
                    common = frozenset.intersection(*sets) if sets else frozenset()
                    take |= common
                    STATS["tie_dropped"] += len(comp) - len(common)
            for i in range(len(ok)):   # ★ 採る候補は互いに食い違わないので、採る順は結果に効かない
                if i in take:
                    accept(ok[i])

        # ★ 2 伝播：一通りにしか決まらない対応だけ
        _bid = {r.relation_id: r for r in base_graph.relations}
        _tid = {r.relation_id: r for r in target_graph_partial.relations}
        changed = True
        while changed:
            changed = False
            prop_l: dict[str, set] = defaultdict(set)
            prop_r: dict[str, set] = defaultdict(set)
            for lrel, rrel in relation_mapping.items():
                lb, rb = _bid.get(lrel), _tid.get(rrel)
                if lb is None or rb is None or len(lb.arguments) != len(rb.arguments):
                    continue
                for la, ra in zip(lb.arguments, rb.arguments):
                    if la in base_relation_ids or ra in partial_relation_ids:
                        continue
                    if la in entity_mapping or ra in used_entities:
                        continue
                    prop_l[la].add(ra); prop_r[ra].add(la)
            for la, ras in prop_l.items():
                if len(ras) == 1:
                    ra = next(iter(ras))
                    if len(prop_r[ra]) == 1:
                        entity_mapping[la] = ra; used_entities[ra] = la; changed = True
                    else:
                        STATS["prop_ambiguous"] += 1
                else:
                    STATS["prop_ambiguous"] += 1

        # ★ ここから下は sme.py:157-205 と同じ
        systematicity = sme._systematicity_score(base_graph, target_graph_partial, relation_mapping)
        matched = len(accepted)
        unmatched = sme._unmatched_count(base_graph, relation_mapping)
        argument_score = sum(len(pair.entity_pairs) + len(pair.relation_pairs) for pair in accepted)
        structural_score = (
            weights.predicate_match_weight * matched
            + weights.argument_consistency_weight * argument_score
            + weights.higher_order_weight * systematicity
            - weights.unmatched_penalty * unmatched
        )
        candidate_projections = sme._projectable_base_relation_ids(
            base_graph, target_graph_partial, entity_mapping, relation_mapping,
            base_relation_ids, partial_relation_ids,
        )
        prior = sme.prototype_prior_score(
            entity_mapping=entity_mapping,
            candidate_projections=candidate_projections,
            prototype=prototype,
            base_graph=base_graph,
            target_graph_partial=target_graph_partial,
            enabled=prototype_prior_weight != 0.0,
        )
        total = structural_score + prototype_prior_weight * prior.total
        alignment = sme.Alignment(
            entity_mapping=entity_mapping,
            relation_mapping=relation_mapping,
            total_score=total,
            score_breakdown={
                "predicate_match": weights.predicate_match_weight * matched,
                "argument_consistency": weights.argument_consistency_weight * argument_score,
                "systematicity": weights.higher_order_weight * systematicity,
                "unmatched_penalty": weights.unmatched_penalty * unmatched,
                "structural_score": structural_score,
                "prototype_prior_score": prior.total,
                "prototype_prior_weight": prototype_prior_weight,
                "prototype_prior_contribution": prototype_prior_weight * prior.total,
                "total_score": total,
            },
            systematicity_contribution=systematicity,
            matched_predicates_count=matched,
            unmatched_count=unmatched,
            candidate_projections=candidate_projections,
            prototype_prior_terms=prior.per_candidate,
        )
        return sme.MappingResult(alignment=alignment, candidates=tuple(accepted))

    n = 0
    for mod in list(sys.modules.values()):
        if mod is not None and getattr(mod, "map_graphs", None) is original:
            setattr(mod, "map_graphs", map_graphs)
            n += 1
    STATS["rebound_modules"] = n

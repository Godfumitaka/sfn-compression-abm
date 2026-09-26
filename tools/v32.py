"""二つ目の実験（2026-09-26、アストラさんの指示）：同化先の決め方を変える旗。★ abm/ は変えない。
abm/loop.py:11 が取り込んだ名前 loop._identify_definition を、外側から差し替える（m1 の包み方 tools/v3_run.py:276 と同じ）。
元の関数は abm/abstraction.py:14-55。候補の絞り（m_live>0・自己の点>0）、並べ方、自己の点の求め方（キャッシュの扱いも）はそのまま写した。

旗A（--ident-rho ρ）両側で測る
    比 ＝ 点(定義, 相手) ÷（点(定義, 定義) ＋ ρ × 相手の側だけにある分の点）
    相手の側だけにある分の点（案）：点(相手, 相手) を相手の行ごとに割り振り（self_row_points。合計は 点(相手, 相手) に一致）、
        点(定義, 相手) の写しで定義のどの行からも写されなかった相手の行（写像の値に無い行）の分を足したもの。
        行の分 ＝ 対として採られた行は 4 ＋ 1 × 引数の対応の数 ＋ 2 × 体系性、親の引数として写っただけの行は 2 × 体系性だけ
        （sme.py:157-166 の項。重みは SMEParams sme.py:19-25）。定義の側の罰が「写像の鍵に無い行」を数える（sme.py:415-416）のと向きをそろえた。
    ρ＝0 のときは、比の計算が元と一字一句同じ（点 ÷ 自己の点）。
旗B（--ident-argmax）一番高い定義を選ぶ
    候補すべての比を出し、一番高い定義が基準に届けば同化（その名前を返す）、届かなければ None（誕生）。
    同点は今の走査順（assimilation_count の多い順 → registered_at の新しい順）で先のもの（厳密に大きいときだけ入れ替える）。
旗C（--ident-commons）照らす相手を共通構造にする（2026-09-26 午後、アストラさんの決定：案 C1）
    共通構造 ＝ m1 と同じ手順の対（abstraction.py:74-85。ドライバの写し v3_run.py:47-55）：土台（output.trace["selected_scene"]）と
    今の場面の整列（output.trace["alignment"]）の対のうち、土台の側が構造の行（abstraction.py:289-303）で、述語が一致するもの。
    C1：対の今の場面の側の行で作る（ID は今の場面のまま。並びは今の場面の並び）。実体は、その行の引数のうち今の場面の実体であるもの。
      子が共通構造の外にある親の行は、そのまま残す（写しでは、その引数は「見えていない枠」sme.py:298-304 になる）。伏せ辺は入らない。
      共通構造が 2 行未満なら同定しない（None）。m1 はそのとき何もしない（abstraction.py:86-87）。
    output は loop.predict を包んで控える（同定を呼ぶ loop.py:97 の時点で、その試行の output はもうある loop.py:80）。
    旗A と重ねると、相手の側だけの点は 点(共通構造, 共通構造) を行に割り振った分から取る。
--ident-shadow：元の関数も毎回呼んで結果を比べる。旗A・B・C がどれも切れていれば、違った時点で止める（写しの確かめ）。
    shadow のときは loop.predict の包みも入れる（包みが振る舞いを変えないことも一緒に確かめる）。
    旗が入っていれば、元と違った回を数えるだけ（STATS["differ"]）。
"""
from __future__ import annotations

STATS: dict = {}
LAST: dict = {}


def self_row_points(scene, params) -> tuple[dict, float]:
    """点(相手, 相手) を相手の行ごとに割り振る（sme.py:157-166 の項をそのまま行に付ける）。★ 合計は 点(相手, 相手) と同じ。
    対として採られた行（sme.py:136）：述語一致 1 ＋ 引数の対応の数 ＋ 体系性。
    親の行の引数として先に写り、対としては採られなかった行（sme.py:126-127・:133-135）：体系性だけ（sme.py:403-411 は写像のすべての組を見る）。
    どこにも写らなかった行：− 罰（sme.py:159・:165）。"""
    from abm.sme import map_graphs
    res = map_graphs(scene, scene)
    rm = res.alignment.relation_mapping
    by_id = {r.relation_id: r for r in scene.relations}
    accepted = {c.base_relation_id: c for c in res.candidates}
    pts = {}
    for r in scene.relations:
        v = 0.0
        if r.relation_id in accepted:
            c = accepted[r.relation_id]
            v += params.predicate_match_weight + params.argument_consistency_weight * (len(c.entity_pairs) + len(c.relation_pairs))
        if r.relation_id in rm:
            right = by_id.get(rm[r.relation_id])
            if right is not None:
                v += params.higher_order_weight * sum(1 for la, ra in zip(r.arguments, right.arguments) if rm.get(la) == ra)
        else:
            v -= params.unmatched_penalty
        pts[r.relation_id] = v
    return pts, res.alignment.total_score


def target_only_points(row_points, covered) -> float:
    """相手の側だけにある分の点：点(定義, 相手) の写しで、どの定義の行からも写されなかった相手の行（写像の値に無い行）の点の合計。
    ★ 定義の側の罰（sme.py:415-416）が「写像の鍵に無い行」を数えるのと、向きをそろえた。"""
    return sum(v for rid, v in row_points.items() if rid not in covered)


def commons_graph(scene, output):
    """旗C（案 C1）の共通構造のグラフ。2 行未満なら None。"""
    from abm.abstraction import _structural_relation_ids
    from abm.domains import RelationGraph
    base = output.trace["selected_scene"]
    alignment = output.trace["alignment"]
    base_by_id = {r.relation_id: r for r in base.relations}
    target_by_id = {r.relation_id: r for r in scene.relations}
    # ★ ここは abstraction.py:76-85 と同じ手順（整列の対 → 土台の側が構造の行 → 述語が一致）
    raw = [(base_by_id[l], target_by_id[r]) for l, r in sorted(alignment.relation_mapping.items())
           if l in base_by_id and r in target_by_id]
    sids = _structural_relation_ids(base)
    pairs = [p for p in raw if p[0].relation_id in sids and p[0].predicate == p[1].predicate]
    if len(pairs) < 2:
        return None
    keep = {t.relation_id for _, t in pairs}
    rels = tuple(r for r in scene.relations if r.relation_id in keep)
    args = {a for r in rels for a in r.arguments}
    ents = tuple(e for e in scene.entities if e.entity_id in args)
    return RelationGraph(graph_id=f"commons:{scene.graph_id}", entities=ents, relations=rels)


def install(rho: float | None, argmax: bool, shadow: bool, commons: bool = False) -> None:
    import abm.loop as loop
    from abm.abstraction import _definition_graph, _identify_definition as original
    from abm.sme import SMEParams, map_graphs

    params = SMEParams()
    STATS.clear()
    STATS.update(rho=rho, argmax=argmax, shadow=shadow, commons=commons, calls=0, scored=0, reached_calls=0, chosen=0,
                 tie_at_max=0, differ=0, argmax_not_first=0, commons_lt2=0, commons_rows=0)
    LAST.clear()
    if commons or shadow:
        real_predict = loop.predict

        def predict_wrapped(*a, **k):
            out = real_predict(*a, **k)
            LAST["output"] = out[0]              # ★ 控えるだけ。返すものは同じ
            return out

        loop.predict = predict_wrapped

    def identify(state, scene, threshold, self_score_cache=None, *,
                 identification_graph="all", self_score_cache_mode="legacy"):
        # ★ ここまで abstraction.py:25-33 と同じ
        if identification_graph not in {"all", "live"}:
            raise ValueError(f"未知の identification_graph: {identification_graph}")
        if self_score_cache_mode not in {"legacy", "off"}:
            raise ValueError(f"未知の self_score_cache: {self_score_cache_mode}")
        cache = self_score_cache if self_score_cache is not None else {}
        target = scene
        if commons:
            target = commons_graph(scene, LAST["output"])
            LAST["commons_ids"] = frozenset(r.relation_id for r in target.relations) if target is not None else frozenset()
            if target is None:
                STATS["commons_lt2"] += 1
                return None                          # ★ m1 もこのとき何もしない（abstraction.py:86-87）
            STATS["commons_rows"] += len(target.relations)
        definitions = sorted(
            (definition for definition in state.definitions.values() if definition.m_live > 0),
            key=lambda definition: (-definition.assimilation_count, -definition.registered_at),
        )
        STATS["calls"] += 1
        first = None
        best = None
        best_ratio = None
        n_reach = 0
        ratios = []
        row_points = None
        for definition in definitions:
            graph = _definition_graph(definition, mode=identification_graph)
            # ★ 自己の点：abstraction.py:36-49 と同じ
            if self_score_cache_mode == "off":
                self_score = map_graphs(graph, graph).alignment.total_score
            else:
                live_signature = tuple((row.slot_index, row.registered_at)
                                       for row in definition.constituents if row.alive)
                cache_key = repr((definition.name, live_signature))
                self_score = cache.get(cache_key)
                if self_score is None:
                    self_score = map_graphs(graph, graph).alignment.total_score
                    cache[cache_key] = self_score
            if self_score <= 0:
                continue
            result = map_graphs(graph, target)
            score = result.alignment.total_score
            if rho:
                if row_points is None:
                    row_points, _ = self_row_points(target, params)
                covered = set(result.alignment.relation_mapping.values())
                ratio = score / (self_score + rho * target_only_points(row_points, covered))
            else:
                ratio = score / self_score          # ★ abstraction.py:53 と同じ式
            STATS["scored"] += 1
            if ratio >= threshold:
                n_reach += 1
                if first is None:
                    first = definition.name
                if not argmax:
                    break                            # ★ 最初に届いたところで止める（abstraction.py:53-54）
            if argmax:
                ratios.append(ratio)
                if best_ratio is None or ratio > best_ratio:
                    best, best_ratio = definition.name, ratio
        if argmax:
            chosen = best if (best_ratio is not None and best_ratio >= threshold) else None
            if chosen is not None and sum(1 for r in ratios if r == best_ratio) > 1:
                STATS["tie_at_max"] += 1             # ★ 一番高い比に並んだ定義が二つ以上（走査順で先のものを採った）
            if chosen is not None and chosen != first:
                STATS["argmax_not_first"] += 1
        else:
            chosen = first
        STATS["reached_calls"] += n_reach > 0
        STATS["chosen"] += chosen is not None
        if shadow:
            ref = original(state, scene, threshold, self_score_cache, identification_graph=identification_graph,
                           self_score_cache_mode=self_score_cache_mode)
            if ref != chosen:
                STATS["differ"] += 1
                if not rho and not argmax and not commons:
                    raise RuntimeError(f"写しが元の同定と食い違う {chosen} != {ref}")
        return chosen

    loop._identify_definition = identify

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
直し②（--fix2、tools/fix2.py）：同定の中で、定義のグラフに墓石の子の情報を付ける（自己の点と、相手との写しの両方に効く）。
    旗A・B・C が切れていても、--fix2 のときはこの同定（今の同定の写し）を差し込んで使う。
--ident-shadow：元の関数も毎回呼んで結果を比べる。旗A・B・C・直し② がどれも切れていれば、違った時点で止める（写しの確かめ）。
--rename-check：確かめ用。毎回、述語の名前を付け替えて（二通り）同じ規則で判断をやり直し、元の判断と違った回を数える（記録だけ）。
map_graphs は呼ぶときに abm.sme.map_graphs を読む（名前の順番の直し tools/fixorder.py が入っていれば、それを使う）。
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
    import abm.sme as sme
    res = sme.map_graphs(scene, scene)   # ★ 名前の順番の直し（tools/fixorder.py）が入っていれば、それを使う
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


def install(rho: float | None, argmax: bool, shadow: bool, commons: bool = False, fix2: bool = False,
            rename_check: bool = False) -> None:
    import abm.loop as loop
    import abm.sme as sme
    from abm.abstraction import _definition_graph, _identify_definition as original
    from abm.sme import SMEParams

    def map_graphs(*a, **k):   # ★ 呼ぶときに abm.sme.map_graphs を読む（名前の順番の直しの差し替えを使うため）
        return sme.map_graphs(*a, **k)

    params = SMEParams()
    STATS.clear()
    if fix2:
        import fix2 as fix2mod
    STATS.update(rename_check=rename_check, rn_calls=0, rn_same_ident=0, rn_differ_ident=0,
                 rn_differ_rev=0, rn_differ_hash=0, rn_ratio_differ_rev=0, rn_ratio_differ_hash=0,
                 rn_commons_differ_rev=0, rn_commons_differ_hash=0, rn_examples=[])
    STATS.update(rho=rho, argmax=argmax, shadow=shadow, commons=commons, fix2=fix2, calls=0, scored=0, reached_calls=0, chosen=0,
                 tie_at_max=0, differ=0, argmax_not_first=0, commons_lt2=0, commons_rows=0)
    LAST.clear()
    if commons or shadow:
        real_predict = loop.predict

        def predict_wrapped(*a, **k):
            out = real_predict(*a, **k)
            LAST["output"] = out[0]              # ★ 控えるだけ。返すものは同じ
            return out

        loop.predict = predict_wrapped

    def _rename_check(state, scene, threshold, identification_graph, definitions, chosen, first, target):
        """★ 確かめ（--rename-check）：述語の名前を付け替えて、同じ規則で同化の判断をやり直し、元の判断と比べる。記録だけ。
        付け替え：rev ＝ 名前を逆さに読んだもの、hash ＝ sha1 の頭 8 桁を前に付けたもの（どちらも一対一）。
        ident ＝ 付け替えなし（この確かめの作り直しが、元の判断を再現するかの確かめ。初めの 300 回だけ）。
        共通構造（旗C）は、同じ土台と今の場面を付け替えてから写し直して作る（土台の選び直しはしない）。"""
        import hashlib
        from abm.domains import Relation, RelationGraph
        STATS["rn_calls"] += 1
        out = LAST.get("output")
        variants = [("rev", lambda p: "r:" + p[::-1]), ("hash", lambda p: hashlib.sha1(p.encode()).hexdigest()[:8] + ":" + p)]
        if STATS["rn_calls"] <= 300:
            variants.insert(0, ("ident", lambda p: p))
        for tag, rn in variants:
            def ren(g):
                return RelationGraph(graph_id=g.graph_id, entities=g.entities,
                                     relations=tuple(Relation(r.relation_id, rn(r.predicate), r.arguments, r.attributes)
                                                     for r in g.relations))
            if commons:
                from types import SimpleNamespace
                base2 = ren(out.trace["selected_scene"]); scene2 = ren(scene)
                al2 = map_graphs(base2, scene2).alignment
                tgt = commons_graph(scene2, SimpleNamespace(trace={"selected_scene": base2, "alignment": al2}))
                cm_ids = frozenset(r.relation_id for r in tgt.relations) if tgt is not None else frozenset()
                if tag != "ident" and cm_ids != LAST.get("commons_ids"):
                    STATS["rn_commons_differ_" + tag] += 1
                if tgt is None:
                    ch2 = None; rat2 = {}
                    _rn_record(tag, chosen, ch2, first, None, {}, rat2)
                    continue
            else:
                tgt = ren(scene)
            rp = self_row_points(tgt, params)[0] if rho else None
            f2 = None; b2 = None; br2 = None; rat2 = {}
            for d in definitions:
                g = ren(_definition_graph(d, mode=identification_graph))
                reg = False
                if fix2:
                    allowed = fix2mod.tomb_allowed(_definition_graph(d, mode=identification_graph), d, state.slot_history)
                    if allowed:
                        fix2mod.REG[id(g)] = (g, {k: frozenset(rn(x) for x in v) for k, v in allowed.items()}); reg = True
                try:
                    ss = map_graphs(g, g).alignment.total_score
                    if ss <= 0:
                        continue
                    res = map_graphs(g, tgt)
                    sc = res.alignment.total_score
                    if rho:
                        ratio = sc / (ss + rho * target_only_points(rp, set(res.alignment.relation_mapping.values())))
                    else:
                        ratio = sc / ss
                finally:
                    if reg:
                        fix2mod.REG.pop(id(g), None)
                rat2[d.name] = ratio
                if ratio >= threshold and f2 is None:
                    f2 = d.name
                    if not argmax:
                        break
                if argmax and (br2 is None or ratio > br2):
                    b2, br2 = d.name, ratio
            ch2 = (b2 if (br2 is not None and br2 >= threshold) else None) if argmax else f2
            _rn_record(tag, chosen, ch2, first, target, LAST.get("rn_ratios"), rat2)

    def _rn_record(tag, chosen, ch2, first, target, ratios0, rat2):
        if tag == "ident":
            STATS["rn_same_ident" if ch2 == chosen else "rn_differ_ident"] += 1
            LAST["rn_ratios"] = rat2
            return
        base = LAST.get("rn_ratios_main") or {}
        if any(abs(rat2.get(k, -1) - v) > 1e-12 for k, v in base.items()) or set(rat2) != set(base):
            STATS["rn_ratio_differ_" + tag] += 1
        if ch2 != chosen:
            STATS["rn_differ_" + tag] += 1
            if len(STATS["rn_examples"]) < 30:
                top = sorted(base.items(), key=lambda kv: -kv[1])[:3]
                top2 = sorted(rat2.items(), key=lambda kv: -kv[1])[:3]
                STATS["rn_examples"].append({"call": STATS["calls"], "tag": tag, "chosen": chosen, "renamed": ch2,
                                             "top": [[k, round(v, 6)] for k, v in top],
                                             "top_renamed": [[k, round(v, 6)] for k, v in top2]})

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
                if rename_check:
                    LAST["rn_ratios_main"] = {}
                    defs0 = sorted((d for d in state.definitions.values() if d.m_live > 0),
                                   key=lambda d: (-d.assimilation_count, -d.registered_at))
                    _rename_check(state, scene, threshold, identification_graph, defs0, None, None, None)
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
        ratios_main = {}
        for definition in definitions:
            graph = _definition_graph(definition, mode=identification_graph)
            registered = fix2mod.register(graph, definition, state.slot_history) if fix2 else False
            try:
                # ★ 自己の点：abstraction.py:36-49 と同じ（直し② で墓石の子の情報を付けたグラフは、キャッシュの鍵を分ける）
                if self_score_cache_mode == "off":
                    self_score = map_graphs(graph, graph).alignment.total_score
                else:
                    live_signature = tuple((row.slot_index, row.registered_at)
                                           for row in definition.constituents if row.alive)
                    cache_key = repr((definition.name, live_signature) + (("fix2",) if registered else ()))
                    self_score = cache.get(cache_key)
                    if self_score is None:
                        self_score = map_graphs(graph, graph).alignment.total_score
                        cache[cache_key] = self_score
                if self_score <= 0:
                    continue
                result = map_graphs(graph, target)
            finally:
                if registered:
                    fix2mod.unregister(graph)
            score = result.alignment.total_score
            if rho:
                if row_points is None:
                    row_points, _ = self_row_points(target, params)
                covered = set(result.alignment.relation_mapping.values())
                ratio = score / (self_score + rho * target_only_points(row_points, covered))
            else:
                ratio = score / self_score          # ★ abstraction.py:53 と同じ式
            STATS["scored"] += 1
            if rename_check:
                ratios_main[definition.name] = ratio
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
        if rename_check:
            LAST["rn_ratios_main"] = ratios_main
            _rename_check(state, scene, threshold, identification_graph, definitions, chosen, first, target)
        if shadow:
            ref = original(state, scene, threshold, self_score_cache, identification_graph=identification_graph,
                           self_score_cache_mode=self_score_cache_mode)
            if ref != chosen:
                STATS["differ"] += 1
                if not rho and not argmax and not commons and not fix2:
                    raise RuntimeError(f"写しが元の同定と食い違う {chosen} != {ref}")
        return chosen

    loop._identify_definition = identify

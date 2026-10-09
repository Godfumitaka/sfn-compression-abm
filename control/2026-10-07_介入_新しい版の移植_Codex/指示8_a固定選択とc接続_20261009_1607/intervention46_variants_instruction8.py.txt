"""指示8の別診断入口：(iii-a)の固定選択と(iii-c)の同じ誕生。

旧いa/b候補と停止資料は変更しない。bの実行入口は持たない。
完全場面のaは上限の参考だけで、(i)や本番へ戻さない。
"""
from dataclasses import dataclass, replace
from functools import partial

from abm.domains import RelationGraph


@dataclass(frozen=True)
class Experience:
    agent: str
    trial: int
    shop: str
    scene: RelationGraph
    source: str


class ExperienceLog:
    """全試行の実経験を順に受け、店ごとの最新二場面を読む。

sceneはその試行で実際に見た可視部分と実開示だけ。例外ではない
試行もNoneで受け取るので、記録の穴を古い二場面で埋めない。
    """
    def __init__(self):
        self.last = {}
        self.by_shop = {}

    def append(self, agent, trial, shop, *, exception_scene, source):
        if trial != self.last.get(agent, -1) + 1 or not source:
            raise ValueError("実経験の連続した記録と出所が無いので補わない")
        if exception_scene is not None and not isinstance(exception_scene, RelationGraph):
            raise TypeError("本人が実際に見た関係グラフだけを材料にする")
        self.last[agent] = trial
        if exception_scene is not None:
            pair = self.by_shop.setdefault((agent, shop), [])
            pair.append(Experience(agent, trial, shop, exception_scene, source))
            self.by_shop[agent, shop] = pair[-2:]

    def latest(self, frame, shop):
        if self.last.get(frame.agent, -1) != frame.trial - 1:
            raise ValueError("試行前までの全経験記録が無いので補わない")
        return tuple(self.by_shop.get((frame.agent, shop), ()))


def add_content(frame, full_scene, name, *, state=None):
    """当該完全場面の全F一本。誕生の初期成績や頻度は作らない。"""
    from abm.definition import Constituent, NamedDefinition
    from abm.domains import Relation
    if not isinstance(full_scene, RelationGraph):
        raise TypeError("a/bの当該完全場面が必要")
    state = frame.state if state is None else state
    if name in state.definitions:
        raise ValueError("診断用の定義名が重複")
    before = frame.digest()
    ids = {row.relation_id: f"{name}:r{i}" for i, row in enumerate(full_scene.relations)}
    if len(ids) != len(full_scene.relations):
        raise ValueError("完全場面の関係IDが重複")
    rows = tuple(Constituent(i, frame.trial,
        Relation(ids[row.relation_id], row.predicate,
                 tuple(ids.get(argument, argument) for argument in row.arguments), row.attributes),
        frozen_price=None, alive=True) for i, row in enumerate(full_scene.relations))
    definition = NamedDefinition(name, rows, len(rows), frame.trial)
    result = replace(state, definitions={**state.definitions, name: definition})
    if frame.digest() != before:
        raise RuntimeError("全F一本の追加が元の実記録を変えた")
    return result, definition


def fixed_prediction(frame, flags, definition_name, *, state=None):
    """指示8の研究者固定選択。同じSession.answerの門と予測を使う。

注意の候補生成や選択は呼ばない。出所や領域で模型の読み手を
切り替えず、研究者が指定した定義の対応だけを固定する。
    """
    import attncstar
    import attnsme
    import cstar_runtime as C
    import smeshared as S
    import v39
    from random import Random
    if (not flags["attn_allin"] or flags["stage2"] != "on"
            or flags["stage2_reuse"] != "off" or not C.CFG
            or attnsme.ST.get("active")):
        raise ValueError("同じ全部入り・第二段・使い回しoffの診断文脈が必要")
    state = frame.state if state is None else state
    if definition_name not in state.definitions:
        raise ValueError("研究者指定の定義が記憶に無い")
    with frame.isolated(), attncstar.prediction_context(frame.agent_input, state, frame.config):
        ranked = []
        original_choice = S._definition_choice
        def capture(rows, scene):
            ranked.extend(rows)
            return original_choice(rows, scene)
        # Session.rankと同じ照合を保存する。注意のpublic_candidatesは通さない。
        S._definition_choice = capture
        try:
            S.select_definition(state, frame.agent_input.target_graph_partial, frame.config)
        finally:
            S._definition_choice = original_choice
        row = next((r for r in ranked if r[2].name == definition_name), None)
        if row is None:
            raise ValueError("研究者指定の一本の同じ照合を読めない")
        _, support, definition, graph, alignment, n, _ = row
        fids = {r.relation.relation_id for r in definition.constituents if r.alive}
        alignment = replace(alignment, candidate_projections=tuple(
            rid for rid in alignment.candidate_projections if rid in fids))
        forced = (support/n, support, definition, graph, alignment, n, False, ())
        original_select = v39.select_definition
        v39.select_definition = lambda *args, **kwargs: forced
        clone = Random()
        clone.setstate(frame.rng_state)
        try:
            output, _ = v39.predict(frame.agent_input, state, frame.config, clone)
        finally:
            v39.select_definition = original_select
        return dict(prediction=attnsme.prediction_data(output), selected=definition_name,
                    selection="researcher_fixed", support=support, m_live=n,
                    attention_candidates_called=False)


def content_prediction(frame, full_scene, flags, name, *, state=None):
    """(iii-a)だけ。同じ全F一本を研究者が選び、元の門から答える。"""
    augmented, definition = add_content(frame, full_scene, name, state=state)
    result = fixed_prediction(frame, flags, definition.name, state=augmented)
    return dict(added_definition=definition.name, iii_a=result,
                upper_reference_uses_current_complete_scene=True,
                evidence_scope="iii_a_upper_reference_only")

def add_past(frame, log, shop, flags, *, horizon, name_suffix, state=None):
    """構成は同じhypo_m1、初期値は同じVirtualInitialで一本だけ。

構成用の空の定義箱は、出生初期値の評価には渡さない。評価は
元の競合する記憶・背景・観測・注意・問いの控えを持つ写しで行う。
    """
    import attncstar
    import cstar_runtime as C
    import v310be as B
    import v39
    from abm.sme import map_graphs
    from attnstage2_distribution import Readout
    from attnstage2_initial import VirtualInitial
    if not isinstance(log, ExperienceLog):
        raise TypeError("試行前までの連続した実経験の記録が必要")
    experiences = log.latest(frame, shop)
    if len(experiences) < 2:
        return frame.state if state is None else state, None, dict(status="材料なし")
    if len(experiences) != 2 or not all(isinstance(x, Experience) for x in experiences):
        raise ValueError("実経験の最新二場面だけを受け取る")
    first, second = experiences
    if (first.agent != frame.agent or second.agent != frame.agent or first.shop != second.shop
            or not 0 <= first.trial < second.trial < frame.trial
            or not first.source or not second.source):
        raise ValueError("同じ個体・店の試行前の二場面と出所が必要")
    if (flags["stage2"] != "on" or flags["stage2_init"] != "virtual"
            or flags["stage2_reuse"] != "off" or not flags["attn_allin"]
            or type(flags["stage2_birth_hu"]) is not bool):
        raise ValueError("確認済みの全部入り・virtual・使い回しoffの同じ旗が必要")
    if not C.CFG or C.CFG["match_cstar_e"] != flags["match_cstar_e"]:
        raise ValueError("同じ版と旗の誕生の照合が導入されていない")
    state = frame.state if state is None else state
    before = frame.digest()
    with frame.isolated():
        # 形の構成だけを空の定義箱で行い、元の定義を同化させない。
        scratch = replace(state, definitions={}, slot_history={}, merit={}, embed={},
                          exceptions={}, v39_seats={})
        with C.phase(state, frame.config, second.scene, flags["match_cstar_e"]):
            alignment = map_graphs(first.scene, second.scene).alignment
            if alignment is None:
                return state, None, dict(status="誕生なし", material_trials=[first.trial, second.trial])
            born = B.hypo_m1(scratch, first.scene, second.scene, alignment, frame.trial, None,
                dict(base_written_at=first.trial, horizon=horizon,
                     pricing_rule=frame.config.pricing_rule, refill_rule=frame.config.refill_rule,
                     local_lambda=frame.config.local_lambda))
        if born is None:
            return state, None, dict(status="誕生なし", material_trials=[first.trial, second.trial])
        shape, old_name = born
        definition = shape.definitions[old_name]
        if len(shape.definitions) != 1 or definition.registered_at != frame.trial:
            raise RuntimeError("同じ誕生関数が新しい一本を返していない")
        if definition.name in state.definitions:
            definition = replace(definition, name=f"{definition.name}_DIAG_{name_suffix}")
        if definition.name in state.definitions:
            raise ValueError("診断用の誕生名が重複")
        new_name = definition.name
        pre = (frame.agent_input, state, frame.config, frame.rng_state,
               frame.observations, frame.prediction_attention, frame.door_task, (), None)
        policy = VirtualInitial(loss_mode=flags["stage2_loss"], mode=flags["attn_sme"],
            position=flags["attn_position"], epsilon=flags["logp_eps"], readout_policy=Readout(),
            feature_policy=attncstar.Features(flags["logp_eps"]),
            session_class=partial(attncstar.Session, reuse_structure=False),
            measure_birth_hu=flags["stage2_birth_hu"])
        records = dict(state.v39_seats)
        for row in definition.constituents:
            context = dict(definition=definition, row=row, state=shape,
                first_material=first.scene, second_visible=second.scene,
                trial=frame.trial, base_age=frame.trial-first.trial,
                config=frame.config, pre=pre, questions=frame.questions)
            rec = v39.SeatRec(0, v39.seat_state(definition, row, shape.slot_history),
                             frame.trial, frame.trial, v39.ZERO4, v39.ZERO4)
            records[new_name, row.slot_index] = policy(rec, "birth", context)
        # 新しい一本の登録値だけを足す。元の容器の既存の項目は変えない。
        additions = {}
        for field in ("slot_history", "merit", "embed", "exceptions"):
            values = dict(getattr(state, field))
            for key, value in getattr(shape, field).items():
                if key[0] != old_name:
                    raise RuntimeError("構成用の写しに別の定義の更新がある")
                values[(new_name, *key[1:])] = value
            additions[field] = values
        result = replace(state, definitions={**state.definitions, new_name:definition},
                         v39_seats=records, **additions)
        proof = dict(status="追加", material_trials=[first.trial, second.trial],
            sources=[first.source, second.source], added_definition=new_name,
            competing_definitions=list(state.definitions),
            initial_records=policy.drain_records(),
            initialization="native_VirtualInitial", birth="native_hypo_m1")
    if frame.digest() != before:
        raise RuntimeError("過去二場面の誕生が元の実記録を変えた")
    return result, definition, proof


def past_prediction(frame, log, shop, flags, *, horizon, name_suffix, state=None):
    """実経験の二場面から作った同じ一本を加え、本人が選ぶ。"""
    augmented, definition, proof = add_past(frame, log, shop, flags,
        horizon=horizon, name_suffix=name_suffix, state=state)
    if definition is not None:
        proof["prediction"] = frame.prediction(flags, state=augmented)
    return proof

"""注意による選択の初版。段①の部品だけ。既存の走行器にはまだ接続しない。

prepare は公開入力と予測前記憶だけで、実際の答えと全候補の答えを確定する。
finish は実台帳の f_realized / f_fired / feedback_content だけを受け取る。
保持・照合・誕生・同化・門を変えず、abm/ の型に注意を足さない。
旗 --attn-select は tools/attnsel_checks.py の手例で使う。段②・③は未実装。
"""
from __future__ import annotations

from collections import Counter
from contextlib import contextmanager
from dataclasses import dataclass, replace
from fractions import Fraction
import json
import math
from random import Random
import sys


def _weight(weights, name):
    value = weights.get(name, 1.0)
    if not math.isfinite(value) or value < 0:
        raise ValueError("注意の重みは有限・非負でなければならない")
    return Fraction(str(value))


@dataclass(frozen=True)
class Terms:
    """照合を固定した点の会計。重みを持たず、自己の点も毎回計算する。"""
    cross: tuple
    fixed: tuple
    histories: tuple
    cross_structure: int
    definition_structure: int
    scene_names: tuple
    scene_structure: int
    empty_histories: int = 0
    fixed_names: tuple = ()  # 診断だけ。全三点でこの名前の重みを 1 に固定する。

    def scores(self, weights):
        if self.fixed_names:
            weights = {**weights, **dict.fromkeys(self.fixed_names, 1.0)}
        name = sum((n * _weight(weights, p) for p, n in self.cross), Fraction())
        dd_name = sum((n * _weight(weights, p) for p, n in self.fixed), Fraction())
        dd_name += sum((max(_weight(weights, p) for p in h) for h in self.histories), Fraction())
        # 空の H は既存 N3 が自己の名前点 1 とする。未定義の max(空) の補完。
        dd_name += self.empty_histories
        xx_name = sum((n * _weight(weights, p) for p, n in self.scene_names), Fraction())
        return (name + self.cross_structure, dd_name + self.definition_structure,
                xx_name + self.scene_structure)

    def value(self, weights):
        s, dd, xx = self.scores(weights)
        return None if dd + xx == 0 else 2 * s / (dd + xx)

    def gradient(self, weights):
        """Q の解析勾配。H の最大値が同点なら全最大名に等分する劣勾配。"""
        if self.fixed_names:
            weights = {**weights, **dict.fromkeys(self.fixed_names, 1.0)}
        s, dd, xx = self.scores(weights)
        den = dd + xx
        if den == 0:
            raise ValueError("分母 0 の候補は学習に使わない")
        ds, dden = Counter(dict(self.cross)), Counter(dict(self.fixed))
        dden.update(dict(self.scene_names))
        for hist in self.histories:
            top = max(_weight(weights, p) for p in hist)
            tied = [p for p in hist if _weight(weights, p) == top]
            for p in tied:
                dden[p] += Fraction(1, len(tied))
        return {p: (0.0 if p in self.fixed_names else float(2 * (ds[p] * den - s * dden[p]) / den**2))
                for p in weights}


def terms(d, history, alignment, scene):
    """旧 N3 の構造点を保持し、名前点だけを関係名ごとの係数に展開する。"""
    import selectn3
    import v39
    old = selectn3.n3_terms(d, history, alignment, scene)
    visible = {r.relation_id: r for r in scene.relations}
    cross, fixed, histories = Counter(), Counter(), []
    empty = 0
    for row in d.constituents:
        st = v39.seat_state(d, row, history)
        if st == "U":
            continue  # 忘れた行の predicate と履歴は読まない。
        target = visible.get(alignment.relation_mapping.get(row.relation.relation_id))
        if target is not None:
            cross[target.predicate] += 1  # F/H は照合が実際に合わせた名前を一回。
        if st == "F":
            fixed[row.relation.predicate] += 1
        else:
            names = tuple(sorted(p for p, n in v39.hist_counts(history[(d.name, row.slot_index)]).items() if n >= 1))
            if names:
                histories.append(names)
            else:
                empty += 1
    n_fh = v39.n_FH(d, history)
    scene_names = Counter(r.predicate for r in visible.values())
    return Terms(tuple(sorted(cross.items())), tuple(sorted(fixed.items())), tuple(histories),
                 old[1] + old[2], old[3] - n_fh, tuple(sorted(scene_names.items())),
                 old[4] - len(visible), empty)


@dataclass(frozen=True)
class Candidate:
    definition: object
    graph: object
    alignment: object
    support: int
    n: int
    terms: Terms
    answer: tuple | None = None


def candidates(state, scene):
    import v39
    out = []
    for d in state.definitions.values():
        n = v39.n_FH(d, state.slot_history)
        if n == 0:
            continue
        g, al = v39.map_v39(d, state.slot_history, scene)
        if al is None:
            continue
        sup = sum(v39.seat_state(d, row, state.slot_history) != "U"
                  and row.relation.relation_id in al.relation_mapping for row in d.constituents)
        out.append(Candidate(d, g, al, sup, n, terms(d, state.slot_history, al, scene)))
    return tuple(out)


def rank(cands, weights):
    eligible = [(c.terms.value(weights), c) for c in cands]
    eligible = [(q, c) for q, c in eligible if q is not None]
    return tuple(c for _q, c in sorted(eligible, key=lambda x: (
        -x[0], -x[1].n, -x[1].definition.registered_at, x[1].definition.name)))


def selected_result(chosen, ranked, weights, config):
    import abm.agent_runtime as ar
    if chosen is None:
        return None
    d, al = chosen.definition, chosen.alignment
    tie = sum(c.terms.value(weights) == chosen.terms.value(weights) and c.n == chosen.n
              and c.definition.registered_at == d.registered_at for c in ranked) > 1
    passed = [{"R": c.definition.name, "support": c.support, "m_live": c.n,
               "ratio": c.support / c.n, "selected": c is chosen}
              for c in ranked if c.support >= ar._need(config.tau_acc, c.n)]
    f_ids = {r.relation.relation_id for r in d.constituents if r.alive}
    al = replace(al, candidate_projections=tuple(x for x in al.candidate_projections if x in f_ids))
    return chosen.support / chosen.n, chosen.support, d, chosen.graph, al, chosen.n, tie, passed


@contextmanager
def _forced(result):
    """既存の predict をそのまま使い、選択の返り値だけを固定する。"""
    import v39
    original = v39.select_definition
    v39.select_definition = lambda state, scene, config: result
    try:
        yield
    finally:
        v39.select_definition = original


def _copy_mutable(value):
    if isinstance(value, dict):
        return {k: _copy_mutable(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_copy_mutable(v) for v in value]
    if isinstance(value, set):
        return set(value)
    if isinstance(value, tuple):
        return tuple(_copy_mutable(v) for v in value)
    return value


@contextmanager
def isolated():
    """候補の仮予測で既存の診断・キャッシュを汚さない。ファイルは開かない。"""
    from probeworld import SNAP_MODULES
    saved = []
    for name in (*SNAP_MODULES, "selectn3"):
        module = sys.modules.get(name)
        for attr in ("STATS", "CTX", "ST", "INFO", "TCTX", "REG", "UREG", "_POW", "LOG"):
            value = getattr(module, attr, None)
            if isinstance(value, dict):
                saved.append((value, _copy_mutable(value)))
    try:
        yield
    finally:
        for value, old in saved:
            value.clear()
            value.update(old)


def answer_key(prediction):
    from abm.domains import EdgePrediction
    if isinstance(prediction, EdgePrediction):
        return prediction.edge.predicate, tuple(prediction.edge.arguments)
    return None  # 黙る理由が違っても、答えは同じ黙り。


def _softmax(values):
    top = max(values)
    ex = [math.exp(x - top) for x in values]
    z = math.fsum(ex)
    return top + math.log(z), tuple(x / z for x in ex)


def loss_gradient(cands, weights, correct, beta):
    """正解の候補群への負の対数確率。正解を受け取らず、確定済みの mask を使う。"""
    if not math.isfinite(beta) or beta <= 0:
        raise ValueError("beta は有限・正でなければならない")
    if not cands or len(correct) != len(cands) or not any(correct):
        raise ValueError("正解の候補が必要")
    logits = [beta * float(c.terms.value(weights)) for c in cands]
    all_z, pi = _softmax(logits)
    ids = [i for i, ok in enumerate(correct) if ok]
    good_z, good_pi = _softmax([logits[i] for i in ids])
    conditional = {i: p for i, p in zip(ids, good_pi)}
    dq = [c.terms.gradient(weights) for c in cands]
    gradient = {p: beta * math.fsum((pi[i] - conditional.get(i, 0)) * g[p]
                                   for i, g in enumerate(dq)) for p in weights}
    return all_z - good_z, gradient, pi


def normalized_step(weights, gradient, eta, *, fixed_names=()):
    if not math.isfinite(eta) or eta < 0:
        raise ValueError("eta は有限・非負でなければならない")
    if fixed_names:
        # 固定名は 1、残りの平均も 1 にするので、全体の平均は 1 のまま。
        free = {p: w for p, w in weights.items() if p not in fixed_names}
        after = normalized_step(free, gradient, eta)
        return {p: 1.0 if p in fixed_names else after[p] for p in weights}
    clipped = {p: max(0.0, w - eta * gradient[p]) for p, w in weights.items()}
    if not clipped:
        return {}
    mean = math.fsum(clipped.values()) / len(clipped)
    # 全部 0 では平均 1 に戻せないため、初期値 1 に戻す補完。
    return {p: x / mean if mean else 1.0 for p, x in clipped.items()}


@dataclass(frozen=True)
class Prepared:
    agent_id: str
    trial: int
    output: object
    pending: object
    candidates: tuple
    before: tuple
    selected: str | None
    record_only: bool
    owner: object
    version: int


class Attention:
    """一個体で全定義に共有。個体ごとに別インスタンスを使う。"""
    def __init__(self, *, enabled=False, beta=5.0, eta=0.05, seen=(), fixed_names=()):
        if not math.isfinite(beta) or beta <= 0 or not math.isfinite(eta) or eta < 0:
            raise ValueError("beta は正、eta は非負、両方とも有限")
        self.enabled, self.beta, self.eta = enabled, beta, eta
        self.weights = {p: 1.0 for p in sorted(set(seen))}
        self.fixed_names = tuple(sorted(set(fixed_names)))
        if not set(self.fixed_names) <= self.weights.keys():
            raise ValueError("診断で固定する名前は開示前に見た名前でなければならない")
        self.version = 0
        self._finished = set()

    def observe(self, names):
        for name in sorted(set(names)):
            self.weights.setdefault(name, 1.0)

    def prepare(self, agent_id, trial, agent_input, state, config, rng, *, record_only=False, predictor=None):
        import v39
        predict = predictor or v39.predict
        if not self.enabled and not record_only:
            output, pending = predict(agent_input, state, config, rng)
            return Prepared(agent_id, trial, output, pending, (), tuple(sorted(self.weights.items())),
                            output.trace.get("R_used"), False, self, self.version)
        if not record_only:
            self.observe(r.predicate for r in agent_input.target_graph_partial.relations)
        before = dict(self.weights)
        with isolated():
            cs = candidates(state, agent_input.target_graph_partial)
            if self.fixed_names:
                cs = tuple(replace(c, terms=replace(c.terms, fixed_names=self.fixed_names)) for c in cs)
            ranked = rank(cs, before)
            frozen = []
            for c in ranked:
                clone = Random(1)
                clone.setstate(rng.getstate())  # 乱数の消費は本人と同じ出発点の写しだけ。
                with isolated(), _forced(selected_result(c, ranked, before, config)):
                    out, _pending = predict(agent_input, state, config, clone)
                frozen.append(replace(c, answer=answer_key(out.prediction)))
        if record_only:
            output, pending = predict(agent_input, state, config, rng)
        else:
            selected = ranked[0] if ranked else None
            with _forced(selected_result(selected, ranked, before, config)):
                output, pending = predict(agent_input, state, config, rng)
            if selected is not None and answer_key(output.prediction) != frozen[0].answer:
                raise RuntimeError("候補の仮予測と本人の予測が違う")
        selected_name = (ranked[0].definition.name if ranked and not record_only else
                         output.trace.get("R_used") or output.trace.get("R_identified"))
        return Prepared(agent_id, trial, output, pending, tuple(frozen), tuple(sorted(before.items())),
                        selected_name, record_only, self, self.version)

    def finish(self, prepared, row):
        """実台帳の開示を使う。非開示なら feedback_content を読む前に戻る。"""
        if not self.enabled and not prepared.record_only:
            return None
        if prepared.owner is not self or prepared.version != self.version or prepared.trial in self._finished:
            raise ValueError("他個体・古い試行・二重の更新は認めない")
        if int(row["prediction_order"]) != prepared.trial or row["agent_id"] != prepared.agent_id:
            raise ValueError("台帳の個体・試行が予測の控えと違う")
        f, disclosed = float(row["f_realized"]), row["f_fired"]
        if not math.isfinite(f) or not 0 <= f <= 1 or type(disclosed) is not bool:
            raise ValueError("実台帳の f と開示の欄が不正")
        if dict(prepared.before) != self.weights:
            raise ValueError("予測の後、開示の前に重みが変わった")
        reason, loss, gradient = "no_disclosure", None, None
        if prepared.record_only:
            reason = "record_only"
        elif disclosed:
            feedback = row["feedback_content"]
            if not isinstance(feedback, dict):
                raise ValueError("開示された関係が必要")
            self.observe([feedback["predicate"]])
            truth = feedback["predicate"], tuple(feedback["arguments"])
            mask = tuple(c.answer == truth for c in prepared.candidates)
            if not prepared.candidates:
                reason = "no_candidates"
            elif not any(mask):
                reason = "no_correct_candidate"
            else:
                loss, gradient, _pi = loss_gradient(prepared.candidates, self.weights, mask, self.beta)
                if len({c.answer for c in prepared.candidates}) == 1:
                    reason = "all_same_answer"
                elif self.eta == 0:
                    reason = "eta_zero"
                else:
                    after = normalized_step(self.weights, gradient, self.eta, fixed_names=self.fixed_names)
                    reason = "updated" if after != self.weights else "zero_step"
                    self.weights = after
        record = {"kind": "attn_select", "trial": prepared.trial, "agent_id": prepared.agent_id,
                  "f_realized": f, "f_fired": disclosed, "updated": reason == "updated", "reason": reason,
                  "L": loss, "weights_before": dict(prepared.before), "weights_after": dict(self.weights),
                  "beta": self.beta, "eta": self.eta, "selected_before_update": prepared.selected,
                  "candidates": [{"R": c.definition.name, "answer_before_disclosure": c.answer,
                                  "Q_before": float(c.terms.value(dict(prepared.before)))} for c in prepared.candidates]}
        if self.fixed_names:
            record["fixed_answer_names"] = list(self.fixed_names)
        if not prepared.record_only:
            self._finished.add(prepared.trial)
            self.version += 1
        return record


def write_record(stream, record):
    """記録だけ。記憶・注意・乱数に触れない。"""
    if record is not None:
        stream.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")

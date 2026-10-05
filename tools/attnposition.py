"""位置ごとの食い違いで固定候補を選ぶ下見の数値部品。

入力は開示前に固定済みのQ・食い違い・候補回答だけ。位置の鍵や
頻度表の抽出、研究者の分類はこの部品へ渡さない。模型は呼ばない。
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Mapping


@dataclass(frozen=True)
class Candidate:
    name: str
    q: float
    n: int
    registered_at: int
    mismatch: tuple[tuple[str, float], ...]
    answer: tuple | None
    payload: dict


def log_scores(candidates, attention):
    """Q>0の候補だけを同じ加算順で評価する。確率0の規則は別途確定する。"""
    result = []
    for candidate in candidates:
        if not math.isfinite(candidate.q) or candidate.q < 0:
            raise ValueError('Qは有限・非負')
        if candidate.q == 0:
            continue
        penalty = 0.
        for key, mismatch in candidate.mismatch:
            weight = attention.get(key, 0.)
            if not math.isfinite(mismatch) or mismatch < 0:
                raise ValueError('食い違いは有限・非負。確率0の規則を未決のまま進めない')
            if not math.isfinite(weight) or not 0 <= weight <= 10:
                raise ValueError('位置の注意は0以上10以下')
            penalty += weight * mismatch
        result.append((candidate, math.log(candidate.q)-penalty))
    return tuple(result)


def select(candidates, attention):
    scored = log_scores(candidates, attention)
    if not scored:
        return None
    # 今のN3の同点順（席の数、新しさ、名前）を保つ。
    return min(scored, key=lambda item: (-item[1], -item[0].n,
               -item[0].registered_at, item[0].name))[0]


def loss_gradient(candidates, attention, correct):
    """dL/da = 正解群内の期待食い違い − 全候補内の期待食い違い。"""
    scored = log_scores(candidates, attention)
    if not scored:
        return None, {}, 'no_positive_q_candidates'
    good = [index for index, (candidate, _) in enumerate(scored)
            if candidate.answer == correct]
    if not good:
        return None, {}, 'no_correct_candidates'
    all_top = max(score for _, score in scored)
    all_exp = [math.exp(score-all_top) for _, score in scored]
    all_total = sum(all_exp)
    good_top = max(scored[index][1] for index in good)
    good_exp = [math.exp(scored[index][1]-good_top) for index in good]
    good_total = sum(good_exp)
    loss = all_top+math.log(all_total)-good_top-math.log(good_total)
    gradient = {}
    for index, (candidate, _) in enumerate(scored):
        probability = all_exp[index]/all_total
        for key, mismatch in candidate.mismatch:
            gradient[key] = gradient.get(key, 0.)-probability*mismatch
    for index, exponential in zip(good, good_exp):
        probability = exponential/good_total
        for key, mismatch in scored[index][0].mismatch:
            gradient[key] = gradient.get(key, 0.)+probability*mismatch
    return loss, gradient, None


@dataclass(frozen=True)
class Prepared:
    trial: int
    candidates: tuple[Candidate, ...]
    attention_before: tuple[tuple[str, float], ...]
    selected: str | None
    payload: dict
    door_task: bool


class Learner:
    def __init__(self, eta=.1, *, fixed_one=False):
        if not math.isfinite(eta) or eta <= 0:
            raise ValueError('etaは有限・正')
        self.eta, self.fixed_one = eta, fixed_one
        self.attention = {}
        self.next_trial = 0
        self.pending = None

    def prepare(self, trial, door_task, baseline, candidates):
        if trial != self.next_trial or self.pending is not None:
            raise ValueError('試行順又は前の更新が未確定')
        if type(door_task) is not bool:
            raise ValueError('ドア課題は承認済みの指示bool')
        candidates = tuple(candidates)
        for candidate in candidates:
            for key, _ in candidate.mismatch:
                self.attention.setdefault(key, 1. if self.fixed_one else 0.)
        selected = select(candidates, self.attention) if door_task else None
        payload = baseline if selected is None else selected.payload
        prepared = Prepared(trial, candidates, tuple(sorted(self.attention.items())),
                            None if selected is None else selected.name, payload, door_task)
        self.pending = prepared
        return prepared

    def finish(self, prepared, feedback: Mapping):
        if self.pending is not prepared or dict(prepared.attention_before) != self.attention:
            raise ValueError('別の控え又は更新順の違反')
        if feedback['prediction_order'] != prepared.trial:
            raise ValueError('実台帳と試行が違う')
        fired, f = feedback['f_fired'], feedback['f_realized']
        if type(fired) is not bool or not math.isfinite(f) or not 0 <= f <= 1:
            raise ValueError('実際の開示とfの欄が不正')
        loss, gradient, reason, updated = None, {}, None, False
        if not prepared.door_task:
            reason = 'not_door_task'
        elif not fired:
            # 未開示では正解の欄へ到達しない。
            reason = 'not_disclosed'
        else:
            edge = feedback['feedback_content']
            correct = (edge['predicate'], tuple(edge['arguments']))
            loss, gradient, reason = loss_gradient(prepared.candidates, self.attention, correct)
            if reason is None and self.fixed_one:
                reason = 'fixed_attention_no_learning'
            elif reason is None:
                before = dict(self.attention)
                for key, value in gradient.items():
                    self.attention[key] = min(10., max(0., self.attention.get(key, 0.)-self.eta*value))
                updated = before != self.attention
                reason = 'updated' if updated else 'zero_or_clipped_step'
        record = {'trial': prepared.trial, 'f_realized': f, 'f_fired': fired,
                  'door_task': prepared.door_task, 'selected_before_update': prepared.selected,
                  'answer_before_update': prepared.payload,
                  'a_before': dict(prepared.attention_before), 'a_after': dict(self.attention),
                  'L': loss, 'gradient': gradient, 'updated': updated, 'reason': reason,
                  'eta': self.eta, 'fixed_a_one': self.fixed_one}
        self.pending = None
        self.next_trial += 1
        return record

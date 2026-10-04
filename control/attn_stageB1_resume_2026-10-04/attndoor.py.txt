"""段②の固定記憶上の選択。元の走行器へ接続せず、記憶も更新しない。

候補の門・投影・穴埋めは、開示前に元の予測器で計算した控えを使う。
課題指示としてドアを問うことが本人に伝えられている、という承認済みの
仮定の下で door_task を受け取る。正解・店・通常／例外は選択に渡さない。
"""
from dataclasses import dataclass, replace
import math
from types import SimpleNamespace

import attnsel as A

DOOR_NAMES = ('hold','hold_b')


@dataclass(frozen=True)
class FrozenCandidate:
    definition: object
    n: int
    support: int
    terms: A.Terms
    answer: tuple | None
    payload: dict


def decode_candidate(row):
    term = row['terms']
    terms = A.Terms(tuple(tuple(x) for x in term['cross']),
                    tuple(tuple(x) for x in term['fixed']),
                    tuple(tuple(x) for x in term['histories']),
                    term['cross_structure'],term['definition_structure'],
                    tuple(tuple(x) for x in term['scene_names']),term['scene_structure'],
                    term['empty_histories'])
    answer = row['answer']
    return FrozenCandidate(SimpleNamespace(name=row['R'],registered_at=row['registered_at']),
                           row['n'],row['support'],terms,
                           None if answer is None else (answer[0],tuple(answer[1])),row['payload'])


@dataclass(frozen=True)
class PreparedDoor:
    prepared: A.Prepared
    door_task: bool
    payload: dict
    selected: str | None


class DoorAttention:
    def __init__(self, arm, *, beta=5.,eta=.05):
        if arm not in (0,1,2):
            raise ValueError('腕は0・1・2')
        self.arm = arm
        self.learner = A.Attention(enabled=True,beta=beta,eta=eta)
        # 固定する世界の名前の集合と、本人が見た名前の集合は別。
        # 未見の名前を weights に入れず、平均1の範囲を広げない。
        self.learner.fixed_names = DOOR_NAMES if arm==2 else ()

    @property
    def weights(self):
        return self.learner.weights

    def prepare(self, agent_id, trial, public_names, door_task, baseline_payload, candidates):
        if type(door_task) is not bool:
            raise ValueError('課題の指示は明示的なboolで渡す')
        self.learner.observe(public_names)
        before = dict(self.weights)
        selected, cs = None, ()
        payload = baseline_payload
        if self.arm and door_task:
            cs = tuple(replace(c,terms=replace(c.terms,fixed_names=self.learner.fixed_names)) for c in candidates)
            cs = A.rank(cs,before)
            if cs:
                selected,payload = cs[0].definition.name,cs[0].payload
        prepared = A.Prepared(agent_id,trial,None,None,cs,tuple(sorted(before.items())),
                              selected,False,self.learner,self.learner.version)
        return PreparedDoor(prepared,door_task,payload,selected)

    def finish(self, prepared, row):
        p = prepared.prepared
        if self.arm and prepared.door_task:
            record = self.learner.finish(p,row)
        else:
            if (p.owner is not self.learner or p.version != self.learner.version
                    or p.trial in self.learner._finished or dict(p.before)!=self.weights):
                raise ValueError('別の個体・古い控え・二重の更新は使わない')
            if row['agent_id']!=p.agent_id or row['prediction_order']!=p.trial:
                raise ValueError('台帳の個体・試行が控えと異なる')
            f,disclosed=float(row['f_realized']),row['f_fired']
            if not math.isfinite(f) or not 0<=f<=1 or type(disclosed) is not bool:
                raise ValueError('実台帳のf・開示の欄が不正')
            # ドア以外でも、本人が実際に見た名前は平均の範囲に入る。
            # 非開示では正解の欄へ到達しない。勾配は計算しない。
            if disclosed:
                self.learner.observe([row['feedback_content']['predicate']])
            record = {'kind':'attn_select','trial':p.trial,'agent_id':p.agent_id,
                      'f_realized':f,'f_fired':disclosed,'updated':False,
                      'reason':'attention_disabled' if not self.arm else 'not_door_task',
                      'L':None,'weights_before':dict(p.before),'weights_after':dict(self.weights),
                      'beta':self.learner.beta,'eta':self.learner.eta,
                      'selected_before_update':None,'candidates':[]}
            self.learner._finished.add(p.trial)
            self.learner.version+=1
        record['arm']=self.arm
        record['door_task']=prepared.door_task
        record['fixed_door_names']=list(self.learner.fixed_names)
        record.pop('fixed_answer_names',None)
        if any(self.weights.get(p,1.)!=1. for p in self.learner.fixed_names):
            raise RuntimeError('固定したドア名の重みが1ではない')
        if any(not math.isfinite(v) or v<0 for v in self.weights.values()):
            raise RuntimeError('重みが有限・非負ではない')
        if self.weights and abs(math.fsum(self.weights.values())-len(self.weights))>1e-11:
            raise RuntimeError('見た名前の平均が1ではない')
        return record

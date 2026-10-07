"""出生の仮の問いを、予測前の固定した背景・注意で評価する窓口。

実際の問いの指示はドア／非ドアだけ。再照合のSessionを差し替えれば
C*でも同じ初期値の規則を使える。正解・研究者の型は受け取らない。
"""
from dataclasses import replace
from copy import deepcopy
import attnstage2_birth as B
from attnstage2_sme import Session


class VirtualInitial:
    def __init__(self, *, loss_mode, mode, position, epsilon, readout_policy=None,
                 feature_policy=None, session_class=Session):
        self.loss_mode,self.mode,self.position,self.epsilon=loss_mode,mode,position,epsilon
        self.readout_policy,self.feature_policy=readout_policy,feature_policy
        self.session_class=session_class
        self.cache={}
        self.records=[]

    def begin_trial(self):
        # 一つの定義の全席を一度で測る。別の実試行へ結果を流用しない。
        self.cache.clear()
        self.records.clear()

    def __call__(self, rec, why, context):
        if why=='new_generation':
            # 覚え直しと遅い記録の補完は、既存のreconcileの成績0を保つ。
            # 二材料による出生とは混ぜない。Aの出生初期値も写さない。
            self.records.append({'kind':'stage2_initial_reconcile',
                                 'trial':context['trial'],'key':list(context['key']),
                                 'why':context['why'],'generation':rec.gen,
                                 'initial':'native_reconcile_zero'})
            return B.choose_initial(rec,mode='zero')
        if why!='birth':raise ValueError('初期値の呼び出しの種類が不正')
        pre=context['pre']
        if pre is None:raise RuntimeError('出生の予測前の控えが無い')
        ai,before,config,rng_state,observations,attention,_,_,_=pre
        definition=context['definition'];trial=context['trial']
        key=(trial,definition.name)
        if key not in self.cache:
            # 可視構造だけを仮の問いへ使う。観察の頻度表は更新しない。
            frozen_observations=deepcopy(observations)
            frozen_attention=dict(attention)
            def factory(state, visible, door_task):
                return self.session_class(replace(ai,target_graph_partial=visible),state,config,
                    rng_state,deepcopy(frozen_observations),dict(frozen_attention),
                    mode=self.mode,position=self.position,door_task=door_task,
                    epsilon=self.epsilon,readout_policy=self.readout_policy,
                    feature_policy=self.feature_policy)
            import v39
            lengths=v39.code_lengths(before.p_hat)
            values,record=B.birth_values(before,definition,context['first_material'],
                context['second_visible'],context['questions'],trial,
                session_factory=factory,loss_mode=self.loss_mode,
                length_of=lambda name:float(v39.L_of(name,lengths)))
            self.cache[key]=values
            record.update(base_age=context['base_age'],
                          first_material_name_limit=True,
                          background_and_attention='prediction_before',
                          initialization_decay='native_16_columns',
                          reconcile_initialization='native_zero')
            self.records.append(record)
        value=self.cache[key][context['row'].slot_index]
        return B.choose_initial(rec,mode='virtual',virtual=value)

    def drain_records(self):
        records=self.records[:]
        self.records.clear()
        return records

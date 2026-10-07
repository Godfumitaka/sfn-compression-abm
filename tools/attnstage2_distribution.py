"""42⁵の答えの分布。公開の控えだけで席を読み、正解から選ばない。"""
import math
from abm.domains import EdgePrediction


def global_background(agent_input,state,config,door_task):
    """公開の問いの形と階が不明な場合の、絞らない予測前のp̂。"""
    total=state.p_hat.total
    return {name:count/total for name,count in state.p_hat.counts.items() if count>0} if total>0 else {}


def mix_distributions(distributions):
    """適格席を一様に混ぜる。未開示名や微小確率は足さない。"""
    if not distributions:return {}
    names=set().union(*(set(d) for d in distributions))
    return {name:math.fsum(d.get(name,0.) for d in distributions)/len(distributions)
            for name in sorted(names,key=lambda name:(name is None,'' if name is None else name))}


class Readout:
    def __init__(self, background_provider=global_background):
        if background_provider is None:
            raise ValueError('答える位置が無いときの共通bの規則が必要')
        self.background_provider=background_provider

    def background(self, agent_input,state,config,door_task):
        # 正解・生成器・未知の位置の形を追加で受け取らない。
        return dict(self.background_provider(agent_input,state,config,door_task))

    def prepare(self, definition,alignment,state,scene,config,output,pending,epsilon):
        import v39
        import v310be as B
        import answergap
        rows={r.slot_index:r for r in definition.constituents}
        by_id={r.relation.relation_id:r for r in definition.constituents}
        item={'gate_passed':output.trace.get('R_used')==definition.name,'slot':None,'P':None,
              'reason':None,'eligible_slots':[],'distribution_case':'p_hat_fallback'}
        if not item['gate_passed']:
            item['reason']='gate_or_structure_closed'
            return item
        # 席の候補は既存の穴埋めが開示前に作った分布の公開の行だけ。
        gaps=answergap.gap_ids(scene)
        eligible={}
        for distribution in pending.filling_candidate_distribution:
            candidate=rows[distribution['slot_index']]
            destination,_=B.role_target(definition,candidate,alignment,scene)
            if destination in gaps:eligible[candidate.slot_index]=candidate
        item['eligible_slots']=sorted(eligible)
        if B.EPSILON!=epsilon:
            raise RuntimeError('最終損と注意の混ぜのepsilonが一致していない')
        if len(eligible)>1:
            selected_rows=[eligible[slot] for slot in sorted(eligible)]
            statuses=[v39.seat_state(definition,row,state.slot_history) for row in selected_rows]
            distributions=[B.probabilities(definition,row,state,scene,config)[status]
                           for row,status in zip(selected_rows,statuses)]
            item.update(slot=tuple(item['eligible_slots']),states=statuses,
                        P=mix_distributions(distributions),reason='multiple_public_gap_distributions',
                        distribution_case='equal_slot_mixture')
            return item
        row=None
        if isinstance(output.prediction,EdgePrediction):
            rid=output.prediction.edge.relation_id
            if rid.startswith('sme_projection__'):
                row=by_id.get(rid[len('sme_projection__'):])
            else:
                filled=output.trace.get('filled_slots',())
                indices=output.trace.get('filled_slot_indices',())
                row=next((rows[slot] for relation,slot in zip(filled,indices)
                          if relation.relation_id==rid),None)
            if row is None:
                raise RuntimeError('既存の実際の回答の元の席を控えから読めない')
            item['reason']='native_answer_slot'
        else:
            if eligible:
                row=next(iter(eligible.values()));item['reason']='unique_public_gap_distribution'
            else:
                item['reason']='no_native_answer_slot'
                return item
        status=v39.seat_state(definition,row,state.slot_history)
        distribution=B.probabilities(definition,row,state,scene,config)[status]
        item.update(slot=row.slot_index,state=status,P=dict(distribution),distribution_case='single_slot')
        return item

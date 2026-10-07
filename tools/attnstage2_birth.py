"""第一材料の名前だけを持つ新定義で、誕生の仮の問いを値付けする。

型の名札・生成器・未開示の関係は受け取らない。第二材料は、本人が
実際に見た関係だけのグラフ。仮の問いの正解は候補計算の後で採点へ
渡す。初期値の容器と減衰は既存のSeatRecと同じ。
"""
from dataclasses import replace
import math
import time
import attnstage2 as T


def first_only_state(before, definition, first_material, trial):
    """新定義の形に、第一材料の名前までの情報だけを入れる。"""
    import v39
    if definition.name in before.definitions:
        raise ValueError('誕生の仮の新定義は予測前の記憶に無い名前')
    first = {r.relation_id:r for r in first_material.relations}
    rows, history, records = [], dict(before.slot_history), dict(before.v39_seats)
    for row in definition.constituents:
        key = (definition.name,row.slot_index)
        seen = first.get(row.relation.relation_id)
        if row.alive and seen is None:
            raise ValueError(('出生のF席の第一材料の名前を確認できない',key))
        # Fの名も二材料後の固定値を写さず、第一材料から読む。
        relation = replace(row.relation,predicate=seen.predicate if seen is not None else '⟨消去⟩')
        rows.append(replace(row,relation=relation))
        if seen is not None:
            history[key] = {seen.predicate:1}
        elif key in history:
            del history[key]
    fresh = replace(definition,constituents=tuple(rows))
    for row in fresh.constituents:
        key=(fresh.name,row.slot_index)
        state=v39.seat_state(fresh,row,history)
        records[key]=v39.SeatRec(0,state,trial,trial,v39.ZERO4,v39.ZERO4)
    # b、使用回数、既存の席の値はbeforeのまま。第二材料は引数にも無い。
    return replace(before,definitions={**before.definitions,fresh.name:fresh},
                   slot_history=history,v39_seats=records)


def partial_question(material, relation_id):
    """一つの既知の関係を伏せた入力。名前を問いの指示へ残さない。"""
    relations=tuple(r for r in material.relations if r.relation_id != relation_id)
    entity_ids={e.entity_id for e in material.entities}
    used={a for r in relations for a in r.arguments if a in entity_ids}
    return replace(material,relations=relations,
                   entities=tuple(e for e in material.entities if e.entity_id in used))


def initial_record(rec, value, mass, *, hu_value=None):
    """第一材料の共通のbの差は0。現在の重みつきΔだけをinitへ入れる。"""
    import v39
    if not math.isfinite(value) or not math.isfinite(mass) or mass<0:
        raise ValueError('誕生の差と問いの重みは有限')
    if hu_value is not None and not math.isfinite(hu_value):
        raise ValueError('誕生のH→Uの差は有限')
    values=(0.,value,value,mass) if rec.state=='F' else (0.,0.,value,mass) if rec.state=='H' else (0.,0.,0.,0.)
    if rec.state=='F' and hu_value is not None:
        # RH−RFがF→H、RU−RHがH→U。既存の四列・減衰は変えない。
        values=(0.,value,value+hu_value,mass)
    return replace(rec,init=tuple((float(v),)*16 for v in values),post=v39.ZERO4)


def birth_values(before, definition, first_material, second_visible, questions, trial,
                 *, session_factory, loss_mode, length_of, measure_birth_hu=False):
    """session_factoryに正解は渡さない。仮の問いは頻度・履歴を更新しない。"""
    import v39
    start=time.perf_counter()
    hypothetical=first_only_state(before,definition,first_material,trial)
    fresh=hypothetical.definitions[definition.name]
    seats=tuple(T.Seat(fresh.name,row.slot_index,v39.seat_state(fresh,row,hypothetical.slot_history),0)
                for row in fresh.constituents
                if v39.seat_state(fresh,row,hypothetical.slot_history)!='U')
    weights,counts=questions.virtual_weights(r.predicate for r in second_visible.relations)
    totals={row.slot_index:0. for row in fresh.constituents}
    masses={row.slot_index:0. for row in fresh.constituents}
    hu_totals={row.slot_index:0. for row in fresh.constituents} if measure_birth_hu else None
    records=[];work={'virtual_questions':len(weights),'evaluated_questions':0,'thinned_seats':0,'rerankings':0}
    for relation,weight in zip(second_visible.relations,weights):
        entry={'relation_id':relation.relation_id,'class':weight['class'],'weight':weight['weight']}
        if weight['weight']==0:
            records.append({**entry,'reason':'unexperienced_kind','rows':[]})
            continue
        visible=partial_question(second_visible,relation.relation_id)
        session=session_factory(hypothetical,visible,weight['class']=='door')
        # ここまで正解の名前は、選びの入力・照合・候補の回答へ渡していない。
        correct=(relation.predicate,tuple(relation.arguments))
        rows,measured=T.compare_seats(session.candidates,session.attention,seats,
                      session.rematched,None,correct=correct,ell=length_of(relation.predicate),
                      mode=loss_mode,choose=session.choose,background=session.background,method='rematched')
        for row in rows:
            slot=row['slot'];totals[slot]+=weight['weight']*row['delta'];masses[slot]+=weight['weight']
        hu_rows=[]
        if measure_birth_hu:
            for seat in seats:
                if seat.state!='F':
                    continue
                # この席だけをHにした記憶から、同じ仮の問いを評価し直す。
                # 他の席や候補を先に薄くせず、正解をSessionへ渡さない。
                after_fh=session_factory(session.thin(seat),visible,weight['class']=='door')
                measured_hu,hu_work=T.compare_seats(after_fh.candidates,after_fh.attention,
                    (replace(seat,state='H'),),after_fh.rematched,None,
                    correct=correct,ell=length_of(relation.predicate),mode=loss_mode,
                    choose=after_fh.choose,background=after_fh.background,method='rematched')
                hu_rows.extend(measured_hu)
                hu_totals[seat.slot]+=weight['weight']*measured_hu[0]['delta']
                for key in ('thinned_seats','rerankings'):
                    work[key]+=hu_work[key]
        work['evaluated_questions']+=1
        for key in ('thinned_seats','rerankings'):work[key]+=measured[key]
        record={**entry,'reason':'evaluated','rows':rows}
        if measure_birth_hu:record['hu_after_fh_rows']=hu_rows
        records.append(record)
    initial={slot:initial_record(hypothetical.v39_seats[fresh.name,slot],value,masses[slot],
                    **({'hu_value':hu_totals[slot]} if measure_birth_hu else {}))
             for slot,value in totals.items()}
    record={'kind':'stage2_birth_virtual','trial':trial,'R':fresh.name,
          'loss':loss_mode,'question_counts':{'door':questions.door,'other':questions.other},
          'virtual_counts':counts,'records':records,'delta_by_slot':totals,
          'mass_by_slot':masses,'first_material_common_delta':0.,
          'seconds':time.perf_counter()-start,**work}
    if measure_birth_hu:
        record.update(measure_birth_hu=True,hu_after_fh_delta_by_slot=hu_totals)
    return initial,record


def choose_initial(rec, *, mode, virtual=None):
    """Aは比べだけ。主のvirtualでAの値を写さない。"""
    import v39
    if mode=='A':return rec
    if mode=='zero':return replace(rec,init=v39.ZERO4,post=v39.ZERO4)
    if mode=='virtual' and virtual is not None:
        return replace(rec,init=virtual.init,post=v39.ZERO4)
    raise ValueError('誕生の仮の問いの初期値がまだ作られていない')

"""指示9：保持Dの照合使用をqとk2の注意で測る。旧Dは別の経路に保つ。

予測前の記憶・公開場面・採用済み対応と本人の注意だけを読む。
答えは1、同じ席の照合使用とのmax。誕生と16本の減衰は旧Dを使う。
"""
from __future__ import annotations

import json
import math
import useforget_evaluation as evaluation

AUDIT = {}
PROBE_CHECKS = []


def probe_snapshot():
    """Dの全控えと記録口を、復元せず前後照合する研究者側の字節。"""
    import useforget as D
    from pathlib import Path
    values = (D.ST, AUDIT)
    files = [(value.name, value.tell(), Path(value.name).read_bytes())
             for store in values for value in store.values()
             if hasattr(value, 'tell') and hasattr(value, 'name') and not value.closed]
    return repr((values, files)).encode('utf-8')


def install_probe_guard():
    """試験の全体を囲む。D/AUDITを戻して不変に見せることはしない。"""
    import probeworld
    import hashlib
    PROBE_CHECKS.clear()
    original_probe = probeworld._probe

    def probe(state, config, trial):
        before = probe_snapshot()
        result = original_probe(state, config, trial)
        after = probe_snapshot()
        same = before == after
        PROBE_CHECKS.append(dict(trial=trial, unchanged=same,
            before_sha256=hashlib.sha256(before).hexdigest(),
            after_sha256=hashlib.sha256(after).hexdigest()))
        if not same:
            raise RuntimeError(f'指示12：試験がDの状態又は記録を変えた（試行 {trial}）')
        return result

    probeworld._probe = probe


def attention_weight(key, attention):
    mean = sum(attention.values()) / len(attention) if attention else 0.0
    value = attention.get(key, 0.0) if key is not None else None
    return (1.0 if key is None else (1.0 + value) / (1.0 + mean)), value, mean


def use_amount(key, trial, amount):
    """同じ試行の同じ席では最大量だけを、旧Dと同じ減衰記録へ足す。"""
    if evaluation.active():
        return False
    import useforget as D
    if not math.isfinite(amount) or amount < 0:
        raise ValueError('使用の量が有限の非負でない')
    if amount == 0:
        return False
    if AUDIT.get('trial') != trial:
        AUDIT.update(trial=trial, amounts={}, matching=[], answers=[], births=[], selected=None)
    old = AUDIT['amounts'].get(key, 1.0 if key in D.ST['used_t'] else 0.0)
    if amount <= old:
        return False
    rec = D.ST['S'].get(key)
    vector = D._decayed(rec, trial) if rec is not None else [0.0] * 16
    D.ST['S'][key] = (trial, [x + (amount - old) for x in vector])
    AUDIT['amounts'][key] = amount
    if key not in D.ST['used_t']:
        D.ST['used_t'].add(key)
        D.ST['n_use'][key] = D.ST['n_use'].get(key, 0) + 1
        D.ST['stats']['uses'] += 1
    return True


def install(path, *, expected_usage=False, attention_usage=False):
    import useforget as D
    import v39
    import cstar_runtime as C
    import attnsme
    import attnposition_keys as K
    from abm.domains import EdgePrediction

    AUDIT.clear()
    AUDIT.update(f=open(path, 'w', encoding='utf-8'), trial=None, amounts={}, matching=[],
                 answers=[], births=[], selected=None, expected_usage=expected_usage,
                 attention_usage=attention_usage)

    def record_matching(state, scene, res):
        if evaluation.active():
            return
        _r, _s, definition, _g, alignment, _n, _tie, _passed = res
        trial = D.ST['t']
        if AUDIT['trial'] != trial:
            AUDIT.update(trial=trial, amounts={}, matching=[], answers=[], births=[], selected=None)
        visible = {row.relation_id: row for row in scene.relations}
        attention = dict(attnsme.ST['individual']['a']) if attention_usage else {}
        index = K.position_index([row.to_dict() for row in scene.relations],
                                 {entity.entity_id for entity in scene.entities}) if attention_usage else None
        AUDIT.update(selected=definition.name, mapping=dict(alignment.relation_mapping),
                     attention=attention)
        for row in definition.constituents:
            seat_state = v39.seat_state(definition, row, state.slot_history)
            destination = alignment.relation_mapping.get(row.relation.relation_id)
            if destination is None:
                continue
            observed = visible.get(destination)
            if seat_state == 'U' or observed is None:
                D.ST['rec']['struct'].append([row.slot_index, seat_state])
                continue
            if expected_usage:
                if not C.active():
                    raise RuntimeError('Dのqを読む時点でC*の予測窓口が有効でない')
                values = C.distributions(definition, row, state, scene, C.CTX['config'])
                q = values['P' if C.CFG['match_eps'] == 'shared' else 'q'][seat_state].get(observed.predicate, 0.0)
            else:
                q = float(observed.predicate == row.relation.predicate if seat_state == 'F' else
                          v39.hist_counts(state.slot_history.get((definition.name, row.slot_index))).get(observed.predicate, 0) >= 1)
            key = None
            if index is not None:
                candidate_key = index['keys'].get(destination)
                if candidate_key is not None and index['counts'].get(candidate_key) == 1:
                    key = candidate_key
            weight, a, mean = attention_weight(key, attention) if attention_usage else (1.0, None, 0.0)
            amount = q * weight
            used = use_amount(D._key(definition, row), trial, amount)
            if used:
                D.ST['rec']['uses'].append([definition.name, row.slot_index, '照合', seat_state])
            AUDIT['matching'].append(dict(R=definition.name, slot=row.slot_index, state=seat_state,
                mapped_to=destination, q=q, key=key, a=a, a_mean=mean, weight=weight, amount=amount))

    D._record_matching = record_matching

    def record_answer(state, output):
        if evaluation.active():
            return
        prediction, name = output.prediction, output.trace.get('R_used')
        if not isinstance(prediction, EdgePrediction) or name not in state.definitions:
            return
        definition = state.definitions[name]
        rid = prediction.edge.relation_id
        slot = None
        if rid.startswith('sme_projection__'):
            base = rid[len('sme_projection__'):]
            slot = next((row.slot_index for row in definition.constituents if row.relation.relation_id == base), None)
        elif rid.startswith('filling__'):
            slot = int(rid.rsplit('__', 2)[1])
        row = next((row for row in definition.constituents if row.slot_index == slot), None)
        if row is None:
            return
        seat_state = v39.seat_state(definition, row, state.slot_history)
        if seat_state == 'U':
            D.ST['rec']['answer'] = [name, slot, 'U（数えない）']
            return
        key = D._key(definition, row)
        already = key in D.ST['used_t']
        if use_amount(key, D.ST['t'], 1.0) and not already:
            D.ST['rec']['uses'].append([name, slot, '答え', seat_state])
        D.ST['rec']['answer'] = [name, slot, seat_state]
        AUDIT['answers'].append(dict(R=name, slot=slot, amount=1.0))

    D._record_answer = record_answer
    original_birth = D._birth

    def birth(key, trial):
        if evaluation.active():
            return
        original_birth(key, trial)
        if AUDIT['trial'] != trial:
            AUDIT.update(trial=trial, amounts={}, matching=[], answers=[], births=[], selected=None)
        AUDIT['amounts'][key] = 1.0
        AUDIT['births'].append(list(key))

    D._birth = birth
    original_conversions = v39.run_conversions

    def run_conversions(state, trial):
        if evaluation.active():
            return original_conversions(state, trial)
        before = [[d.name, row.slot_index, d.registered_at, v39.seat_state(d, row, state.slot_history),
                   D.strength(D.ST['S'].get(D._key(d, row)), trial)]
                  for d in state.definitions.values() for row in d.constituents
                  if v39.seat_state(d, row, state.slot_history) != 'U']
        prior_count = D.ST['stats']['no_candidate_below_tau']
        output = original_conversions(state, trial)
        record = dict(trial=trial, selected=AUDIT.get('selected'), mapping=AUDIT.get('mapping', {}),
            matching=AUDIT['matching'], answers=AUDIT['answers'], births=AUDIT['births'],
            attention=AUDIT.get('attention', {}), strengths_before=before, tau=D.ST['tau'],
            amounts=[[list(k), value] for k, value in AUDIT['amounts'].items()],
            no_candidate_below_tau=D.ST['stats']['no_candidate_below_tau'] - prior_count)
        AUDIT['f'].write(json.dumps(record, ensure_ascii=False) + '\n')
        AUDIT.update(trial=None, amounts={}, matching=[], answers=[], births=[], selected=None,
                     mapping={}, attention={})
        return output

    v39.run_conversions = run_conversions


def close():
    AUDIT['f'].close()
    if PROBE_CHECKS:
        from pathlib import Path
        Path(AUDIT['f'].name + '.probe_checks.json').write_text(
            json.dumps(PROBE_CHECKS, ensure_ascii=False, indent=2) + '\n')

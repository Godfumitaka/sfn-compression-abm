"""指示22：出生の仮の問いだけをforkし、親が元の順で記録・加算する。

既定offではこの部品を読み込まない。子の数えは研究者のSTATSだけを
増分として戻す。模型の状態・乱数・正解の入口を親へ持ち帰らない。
"""
from copy import deepcopy
from dataclasses import replace
import json
import multiprocessing as mp
import time
import attnstage2_birth as B
import attnstage2 as T
import attnstage2_runtime as RT

_JOB = {}
_KEEP = []
_WORKERS = 0
_ORIGINAL = B.birth_values
_KEYS = ('seconds', 'match_calls', 'result_cache_hits', 'engine_calls', 'engine_seconds',
         'foundation_builds', 'foundation_hits')


class _Capture:
    def __init__(self):
        self.lines = []

    def write(self, line):
        self.lines.append(line)


def _count_changes(before, after, path=()):
    """数えの増分と新しい鍵の順を控える。非数値の変更・鍵の削除は止める。"""
    if isinstance(after, dict):
        if not isinstance(before, dict) or any(key not in after for key in before):
            raise ValueError(('研究者の数えの形又は鍵が変わった', path))
        changes = []
        for key, value in after.items():
            here = path + (key,)
            if isinstance(value, dict):
                if key not in before:
                    changes.append(('container', here, type(value)))
                changes.extend(_count_changes(before.get(key, {}), value, here))
            elif isinstance(value, (int, float)) and not isinstance(value, bool):
                old = before.get(key, 0)
                if not isinstance(old, (int, float)) or isinstance(old, bool):
                    raise ValueError(('研究者の数えは数値', here))
                delta = value - old
                if delta or key not in before:
                    changes.append(('number', here, delta))
            elif key not in before or type(before[key]) is not type(value) or before[key] != value:
                raise ValueError(('数え以外の研究者欄を変更しない', here))
        return changes
    raise TypeError('研究者のSTATSは辞書')


def _add_counts(target, changes):
    for kind, path, value in changes:
        node = target
        for key in path[:-1]:
            node = node[key]
        key = path[-1]
        if kind == 'container':
            if key not in node:
                node[key] = value()
        elif kind == 'number':
            node[key] = node.get(key, 0) + value
        else:
            raise ValueError(('未知の数えの増分', kind))


def _one(index):
    import strictpc
    import v39
    job = _JOB
    relation, weight = job['pairs'][index]
    before = {name: deepcopy(module.STATS) for name, module in
              (('strictpc', strictpc), ('v39', v39))}
    stream = RT.ST.get('rematch_stream')
    cap = None
    if stream is not None:
        # gzip口の最後の参照を落とすと子のcloseが親のファイルを壊す。
        if not isinstance(stream, _Capture):
            _KEEP.append(stream)
        cap = _Capture()
        RT.ST['rematch_stream'] = cap
    visible = B.partial_question(job['second_visible'], relation.relation_id)
    session = job['factory'](job['hypothetical'], visible, weight['class'] == 'door')
    # 正解は元と同じく候補計算の後だけ採点に渡す。
    correct = (relation.predicate, tuple(relation.arguments))
    rows, measured = T.compare_seats(session.candidates, session.attention, job['seats'],
        session.rematched, None, correct=correct, ell=job['length_of'](relation.predicate),
        mode=job['loss_mode'], choose=session.choose, background=session.background, method='rematched')
    hu = []
    if job['measure_birth_hu']:
        for seat in job['seats']:
            if seat.state != 'F':
                continue
            after_fh = job['factory'](session.thin(seat), visible, weight['class'] == 'door')
            hu_rows, hu_work = T.compare_seats(after_fh.candidates, after_fh.attention,
                (replace(seat, state='H'),), after_fh.rematched, None,
                correct=correct, ell=job['length_of'](relation.predicate), mode=job['loss_mode'],
                choose=after_fh.choose, background=after_fh.background, method='rematched')
            hu.append((seat.slot, hu_rows, {key: hu_work[key] for key in ('thinned_seats', 'rerankings')}))
    counts = {name: _count_changes(before[name], module.STATS) for name, module in
              (('strictpc', strictpc), ('v39', v39))}
    return rows, {key: measured[key] for key in ('thinned_seats', 'rerankings')}, hu, (cap.lines if cap else None), counts


def _replay(lines):
    for line in lines:
        RT.ST['rematch_stream'].write(line)
        row = json.loads(line)
        total = RT.ST['rematch_totals'].setdefault(row['origin'], {})
        total['calls'] = total.get('calls', 0) + 1
        for key in _KEYS:
            total[key] = total.get(key, 0) + row[key]


def birth_values(before, definition, first_material, second_visible, questions, trial,
                 *, session_factory, loss_mode, length_of, measure_birth_hu=False):
    import strictpc
    import v39
    start = time.perf_counter()
    hypothetical = B.first_only_state(before, definition, first_material, trial)
    fresh = hypothetical.definitions[definition.name]
    seats = tuple(T.Seat(fresh.name, row.slot_index, v39.seat_state(fresh, row, hypothetical.slot_history), 0)
                  for row in fresh.constituents
                  if v39.seat_state(fresh, row, hypothetical.slot_history) != 'U')
    weights, counts = questions.virtual_weights(r.predicate for r in second_visible.relations)
    totals = {row.slot_index: 0. for row in fresh.constituents}
    masses = {row.slot_index: 0. for row in fresh.constituents}
    hu_totals = {row.slot_index: 0. for row in fresh.constituents} if measure_birth_hu else None
    records = []
    work = {'virtual_questions': len(weights), 'evaluated_questions': 0, 'thinned_seats': 0, 'rerankings': 0}
    pairs = list(zip(second_visible.relations, weights))
    todo = [index for index, (_, weight) in enumerate(pairs) if weight['weight'] != 0]
    if _JOB:
        raise RuntimeError('出生の並列の問いを入れ子にしない')
    _JOB.update(pairs=pairs, second_visible=second_visible, factory=session_factory,
                hypothetical=hypothetical, seats=seats, length_of=length_of,
                loss_mode=loss_mode, measure_birth_hu=measure_birth_hu)
    results = {}
    try:
        if todo:
            with mp.get_context('fork').Pool(min(_WORKERS, len(todo))) as pool:
                results = dict(zip(todo, pool.map(_one, todo, chunksize=1)))
    finally:
        _JOB.clear()
    # 浮動小数の足す順も、原記録・数えの新しい鍵の順も問いの元順。
    for index, (relation, weight) in enumerate(pairs):
        entry = {'relation_id': relation.relation_id, 'class': weight['class'], 'weight': weight['weight']}
        if weight['weight'] == 0:
            records.append({**entry, 'reason': 'unexperienced_kind', 'rows': []})
            continue
        rows, measured, hu, lines, increments = results[index]
        if lines is not None:
            _replay(lines)
        for name, module in (('strictpc', strictpc), ('v39', v39)):
            _add_counts(module.STATS, increments[name])
        for row in rows:
            slot = row['slot']
            totals[slot] += weight['weight'] * row['delta']
            masses[slot] += weight['weight']
        hu_rows = []
        if measure_birth_hu:
            for slot, measured_hu, hu_work in hu:
                hu_rows.extend(measured_hu)
                hu_totals[slot] += weight['weight'] * measured_hu[0]['delta']
                for key in ('thinned_seats', 'rerankings'):
                    work[key] += hu_work[key]
        work['evaluated_questions'] += 1
        for key in ('thinned_seats', 'rerankings'):
            work[key] += measured[key]
        record = {**entry, 'reason': 'evaluated', 'rows': rows}
        if measure_birth_hu:
            record['hu_after_fh_rows'] = hu_rows
        records.append(record)
    initial = {slot: B.initial_record(hypothetical.v39_seats[fresh.name, slot], value, masses[slot],
                   **({'hu_value': hu_totals[slot]} if measure_birth_hu else {}))
               for slot, value in totals.items()}
    record = {'kind': 'stage2_birth_virtual', 'trial': trial, 'R': fresh.name,
              'loss': loss_mode, 'question_counts': {'door': questions.door, 'other': questions.other},
              'virtual_counts': counts, 'records': records, 'delta_by_slot': totals,
              'mass_by_slot': masses, 'first_material_common_delta': 0.,
              'seconds': time.perf_counter() - start, **work}
    if measure_birth_hu:
        record.update(measure_birth_hu=True, hu_after_fh_delta_by_slot=hu_totals)
    return initial, record


def install(workers):
    global _WORKERS
    if not isinstance(workers, int) or isinstance(workers, bool) or not 0 <= workers <= 7:
        raise ValueError('出生の子の数は0〜7（親と合わせて模型8本まで）')
    if workers == 0:
        return
    if 'fork' not in mp.get_all_start_methods():
        raise RuntimeError('出生の並列の問いはforkが必要')
    if B.birth_values not in (_ORIGINAL, birth_values):
        raise RuntimeError('別の出生の入口へ重ねて接続しない')
    _WORKERS = workers
    B.birth_values = birth_values

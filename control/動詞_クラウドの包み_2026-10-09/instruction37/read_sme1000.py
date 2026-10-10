"""指示35/37。確定1000の原指紋で区切った三つの既存記録だけから表を作る。"""
from pathlib import Path
from collections import Counter
import csv
import gzip
import hashlib
import json
import math

HERE = Path(__file__).resolve().parent
NR = HERE.parent
OUT = NR / 'instruction27_production/19_seed001_flags_on/output'
DEST = HERE / 'readonly1000'


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def bounded_rows(entry):
    """増加中のgzipの確定した解凍byte数だけ読む。原行SHAを整形前に照合する。"""
    path = OUT / entry['path']
    total = lines = 0
    digest = hashlib.sha256()
    with gzip.open(path, 'rb') as source:
        while total < entry['bytes']:
            raw = source.readline(entry['bytes'] - total)
            assert raw and raw.endswith(b'\n'), '確定範囲の原行が閉じていない'
            total += len(raw)
            lines += 1
            digest.update(raw)
            yield lines, raw, json.loads(raw)
    assert total == entry['bytes'] and lines == entry['lines'] and digest.hexdigest() == entry['sha256']


def csv_file(path, rows):
    with path.open('x', newline='') as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def numeric(value):
    assert type(value) in (float, int) and math.isfinite(value) and value >= 0
    return value


def run():
    assert not DEST.exists(), '同じ読み取り・集計を再投入しない'
    DEST.mkdir()
    confirmed_path = OUT / 'comparison_checkpoints/completed_1000/confirmed.json'
    original = confirmed_path.read_bytes()
    confirmed = json.loads(original)
    assert confirmed['confirmed'] is True and confirmed['completed_trials'] == 1000 and confirmed['last_trial'] == 999
    assert confirmed['configured_trial_count'] == confirmed['horizon'] == 5000
    entries = confirmed['records']
    selected = {key: [e for e in entries if e['path'].startswith(prefix) and e['path'].endswith(suffix)]
                for key, prefix, suffix in [('attention', 'attention/', '.jsonl.gz'),
                    ('stage2', 'stage2/', 'seed001.jsonl.gz'),
                    ('birth', 'stage2/', '.initial.jsonl.gz')]}
    assert all(len(value) == 1 for value in selected.values())
    selected = {key: value[0] for key, value in selected.items()}
    (DEST / 'confirmed1000_original.json').write_bytes(original)
    write(DEST / 'input_manifest.json', dict(confirmed_sha256=hashlib.sha256(original).hexdigest(),
          records=selected, all_original_record_names=[e['path'] for e in entries],
          model_starts=0, configured_trial_count=5000, horizon=5000, read_completed_trials=1000,
          full_5000_completed=False, original_rows_modified=False, output_growing_tail_read=False))
    definitions = []
    for _, raw, row in bounded_rows(selected['attention']):
        assert row['trial'] == len(definitions) and type(row['definitions']) is int and row['definitions'] >= 0
        definitions.append(dict(trial=row['trial'], completed_trial=row['trial'] + 1,
            definitions=row['definitions'], original_row_sha256=hashlib.sha256(raw).hexdigest()))
    assert len(definitions) == 1000
    births = []
    kinds = Counter()
    for line, raw, row in bounded_rows(selected['birth']):
        kinds[row['kind']] += 1
        if row['kind'] != 'stage2_birth_virtual':
            continue
        trial = row['trial']
        assert type(trial) is int and 0 <= trial < 1000
        assert type(row['virtual_questions']) is int and row['virtual_questions'] >= 0
        seconds = numeric(row['seconds'])
        births.append(dict(original_line=line, trial=trial, completed_trial=trial + 1,
            definition_name=row['R'], definitions_after_trial=definitions[trial]['definitions'],
            seconds=seconds, virtual_questions=row['virtual_questions'],
            evaluated_questions=row['evaluated_questions'], thinned_seats=row['thinned_seats'],
            seconds_per_virtual_question=seconds / row['virtual_questions'] if row['virtual_questions'] else None,
            original_row_sha256=hashlib.sha256(raw).hexdigest()))
    stage2 = []
    for _, raw, row in bounded_rows(selected['stage2']):
        trial = row['trial']
        assert trial == len(stage2) and type(row['f_fired']) is bool
        assert type(row['thinned_seats']) is int and row['thinned_seats'] >= 0
        seconds = numeric(row['seconds'])
        stage2.append(dict(trial=trial, completed_trial=trial + 1,
            definitions_after_trial=definitions[trial]['definitions'], f_fired=row['f_fired'],
            reason=row['reason'], seconds=seconds, thinned_seats=row['thinned_seats'],
            seconds_per_thinned_seat=seconds / row['thinned_seats'] if row['thinned_seats'] else None,
            original_row_sha256=hashlib.sha256(raw).hexdigest()))
    assert len(stage2) == 1000
    table = []
    for start in range(0, 1000, 100):
        stop = start + 100
        defs = [r['definitions'] for r in definitions[start:stop]]
        born = [r for r in births if start <= r['trial'] < stop]
        disclosed = [r for r in stage2[start:stop] if r['f_fired']]
        bsec = sum(r['seconds'] for r in born)
        questions = sum(r['virtual_questions'] for r in born)
        dsec = sum(r['seconds'] for r in disclosed)
        seats = sum(r['thinned_seats'] for r in disclosed)
        table.append(dict(first_completed_trial=start + 1, last_completed_trial=stop,
            definitions_first=defs[0], definitions_last=defs[-1], definitions_min=min(defs),
            definitions_max=max(defs), definitions_mean=sum(defs) / len(defs),
            births=len(born), birth_seconds=bsec, birth_seconds_mean=bsec / len(born) if born else None,
            virtual_questions=questions, birth_seconds_per_virtual_question=bsec / questions if questions else None,
            disclosures=len(disclosed), disclosure_seconds=dsec,
            disclosure_seconds_mean=dsec / len(disclosed) if disclosed else None,
            thinned_seats=seats, disclosure_seconds_per_thinned_seat=dsec / seats if seats else None))
    csv_file(DEST / 'definitions.csv', definitions)
    csv_file(DEST / 'births.csv', births)
    csv_file(DEST / 'stage2_trials.csv', stage2)
    csv_file(DEST / 'per100.csv', table)
    write(DEST / 'table.json', table)
    write(DEST / 'completed.json', dict(passed=True, model_starts=0, input_hashes_verified=True,
          attention_rows=len(definitions), stage2_rows=len(stage2), initial_kinds=dict(kinds),
          births=len(births), disclosures=sum(r['f_fired'] for r in stage2), table_rows=10,
          completed_trials_read=1000, full_5000_completed=False, actual_model_comparison=False,
          content_gate_passed=None, definitions_stage='学習・忘却後のattention原definitions',
          birth_seconds_scope='原の一誕生の親側経過秒。出生子4のCPU秒ではない',
          disclosure_seconds_scope='第二段の計測と加算。元の会計はsecondsから除かれwrapper_secondsは含む',
          original_confirmed_unchanged=confirmed_path.read_bytes() == original))


if __name__ == '__main__':
    run()

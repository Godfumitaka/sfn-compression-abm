"""指示22の版・全旗・部分完了を読む。模型や原記録は変更しない。"""
from pathlib import Path
import gzip
import hashlib
import json
import re

ROOT = Path(__file__).resolve().parent
NR = ROOT.parent
SOURCE = '6e4bcba94874a4f49c5a1bae11d385534504e2e5'
OBSERVER = '6ca7af8f64dbc9599ac256f84d15930d37d102aeff56bf2e1f29b861c49217f4'
CELL = 'f0.5000_th2.1000_vt0.3842_first_order'


def read(path):
    return json.loads(Path(path).read_text())


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def validate_spec(spec, mode):
    reference = read(NR / 'instruction18_production/19_seed001/spec.json')
    plan = read(ROOT / 'plan.json')
    assert sha(NR / 'instruction18_production/19_seed001/spec.json') == plan['reference_production_spec_sha256']
    assert spec['flags'] == reference['flags'] + ['--verb-snap-append-only', 'on', '--stage2-birth-workers', '0' if mode == 'off' else '4']
    assert list(spec['sources'].values()) == [SOURCE]
    assert list(spec['observer_files'].values()) == [OBSERVER]
    assert spec['completed_trials'] == 100
    assert spec['configured_trial_count'] == spec['horizon'] == 5000
    assert spec['command'][3] == '100'
    assert spec['command'][6:] == spec['flags']
    assert sha(ROOT / 'instruction11_io.py') == plan['io_sha256']


def completion(case):
    case = Path(case)
    spec = read(case / 'spec.json')
    result = read(case / 'result.json')
    assert result['exit_code'] == 0
    output = Path(spec['output'])
    manifest = [json.loads(line) for line in (output / 'manifest.jsonl').read_text().splitlines()]
    assert len(manifest) == 1 and not manifest[0].get('error')
    partial = read(output / 'measurement/partial_done.json')
    for record in (manifest[0], partial):
        assert record['source_commit'] == SOURCE
        assert record['completed_trials'] == 100
        assert record['configured_trial_count'] == record['horizon'] == 5000
        assert record['full_5000_completed'] is False
    probes = manifest[0]['probeworld']
    assert probes['probes'] == probes['rows'] == 48
    assert probes['fingerprint_checks'] == 1
    checks = probes['attention_checks']
    assert len(checks) == 1 and checks[0]['t'] == 100 and checks[0]['passed'] is True
    assert checks[0]['attention_before'] == checks[0]['attention_after']
    assert checks[0]['questions_before'] == checks[0]['questions_after']
    probe_path = output / 'side' / CELL / 'seed001.probe.jsonl'
    probe_rows = [json.loads(line) for line in probe_path.read_text().splitlines()]
    assert len(probe_rows) == 48
    with gzip.open(output / 'ledgers/cells' / CELL / 'seed001.jsonl.gz', 'rt') as ledger:
        orders = [row['prediction_order'] for line in ledger
                  if 'prediction_order' in (row := json.loads(line))]
    assert orders == list(range(100))
    return dict(source_commit=SOURCE, completed_trials=100, configured_trial_count=5000,
                horizon=5000, full_5000_completed=False, probes=48, probe_rows=48,
                fingerprint_checks=1, attention_and_questions_restored=True,
                manifest_sha256=sha(output / 'manifest.jsonl'), partial_sha256=sha(output / 'measurement/partial_done.json'),
                result=result, original_probe_rows_excluded=0)


def time_values(path):
    original = Path(path).read_text()
    times = re.search(r'([\d.]+)\s+real\s+([\d.]+)\s+user\s+([\d.]+)\s+sys', original)
    rss = re.search(r'(\d+)\s+maximum resident set size', original)
    assert times and rss, '原timeの実時間と常駐が必要'
    return dict(real_seconds=float(times[1]), user_seconds=float(times[2]),
                system_seconds=float(times[3]), max_rss_bytes=int(rss[1]))

"""指示19の三つの失敗の原記録だけを読む。再走行・模型や観察入口の変更はしない。"""
from pathlib import Path
from datetime import datetime
import gzip
import hashlib
import json
import re

NR = Path(__file__).resolve().parent
DEST = NR / 'instruction19_failure_readonly.json'
assert not DEST.exists(), '同じ追加読み取りを二重に行わない'


def sha(path):
    digest = hashlib.sha256()
    with path.open('rb') as source:
        while chunk := source.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


report = dict(at=datetime.now().astimezone().isoformat(), learning_model_starts=0,
              original_records_changed=False, new_primary19_started=False, cases={})
for relative in ('instruction19_production/22_seed001', 'instruction19_production/22_seed002',
                 'instruction19_probe_pair/probe100_on'):
    case = NR / relative
    result = json.loads((case / 'result.json').read_text())
    assert result['exit_code'] == 3
    evidence = dict(result=result, files={}, ledgers=[], checkpoints={}, manifest_errors=[])
    for filename in ('spec.json', 'jobs.log', 'run.log', 'result.json', 'pid.json', 'status.json',
                     'admitted_finished.json', 'output/manifest.jsonl', 'output/timing100.jsonl'):
        path = case / filename
        if path.exists():
            evidence['files'][filename] = dict(bytes=path.stat().st_size, sha256=sha(path))
    for line in (case / 'output/manifest.jsonl').read_text().splitlines():
        record = json.loads(line)
        evidence['manifest_errors'].append(record.get('error'))
    for path in (case / 'output/ledgers').rglob('*.jsonl.gz'):
        orders = []
        with gzip.open(path, 'rt') as stream:
            for line in stream:
                row = json.loads(line)
                if 'prediction_order' in row:
                    orders.append(row['prediction_order'])
        evidence['ledgers'].append(dict(path=str(path.relative_to(case)), original_gzip_sha256=sha(path),
            prediction_rows=len(orders), first_order=orders[0] if orders else None,
            last_order=orders[-1] if orders else None, consecutive=orders == list(range(len(orders)))))
    checkpoint = case / 'output/comparison_checkpoints/completed_0500/confirmed.json'
    if checkpoint.exists():
        value = json.loads(checkpoint.read_text())
        evidence['checkpoints']['completed_0500'] = dict(completed_trials=value['completed_trials'],
            last_trial=value['last_trial'], confirmed=value['confirmed'], sha256=sha(checkpoint))
    evidence['attention_files'] = [str(path.relative_to(case)) for path in (case / 'output/attention').rglob('*.jsonl.gz')]
    log = (case / 'run.log').read_text()
    timing = re.search(r'([\d.]+)\s+real\s+([\d.]+)\s+user\s+([\d.]+)\s+sys', log)
    rss = re.search(r'(\d+)\s+maximum resident set size', log)
    evidence['original_time'] = dict(real_seconds=float(timing[1]), user_seconds=float(timing[2]),
        system_seconds=float(timing[3]), max_rss_bytes=int(rss[1])) if timing and rss else None
    if (case / 'output/timing100.jsonl').exists():
        evidence['timing100'] = [json.loads(line) for line in (case / 'output/timing100.jsonl').read_text().splitlines()]
    evidence['normal_full_5000_completed'] = False
    evidence['partial_done_exists'] = (case / 'output/measurement/partial_done.json').exists()
    report['cases'][relative] = evidence
with DEST.open('x') as target:
    target.write(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
print(json.dumps(dict(learning_model_starts=0, cases={name:dict(ledger=e['ledgers'], errors=e['manifest_errors'])
      for name, e in report['cases'].items()}), ensure_ascii=False), flush=True)

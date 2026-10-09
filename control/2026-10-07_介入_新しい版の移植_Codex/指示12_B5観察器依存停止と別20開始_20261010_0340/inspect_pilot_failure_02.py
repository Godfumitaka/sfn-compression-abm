"""模型を動かさず、元の20試行の依存停止と全資料を受付内で保存する。"""
from pathlib import Path
import datetime
import hashlib
import gzip
import importlib
import json
import shutil
import subprocess
import sys

here = Path(__file__).resolve().parent
port = here.parents[1]
sys.path.insert(0, str(port))
from admission_guard import census
rows, active, paused = census()
parents = set()
for pid in active | paused:
    parent = rows[pid]['parent']; seen = set()
    while parent in rows and parent not in seen:
        seen.add(parent)
        if parent in active | paused:
            parents.add(parent)
        parent = rows[parent]['parent']
active -= parents; paused -= parents
assert len(active) < 8 and shutil.disk_usage(here).free >= 20 * 2**30
at = datetime.datetime.now().astimezone().isoformat()
with (here / 'failure_inspection_before_start_02.json').open('x') as f:
    json.dump(dict(at_jst=at, active=len(active), paused=len(paused),
        excluded_parents=sorted(parents), free_disk_bytes=shutil.disk_usage(here).free,
        processes=[dict(pid=p, **rows[p]) for p in sorted(active | paused)]), f, ensure_ascii=False, indent=2)

def read(path):
    return json.loads(path.read_text())

def fingerprints(protected):
    return {root: {name: hashlib.sha256((Path(root) / name).read_bytes()).hexdigest()
            for name in files} for root, files in protected.items()}

case = here / 'B5_pilot20_before'
old = read(case / 'status.json')
protected = read(case / 'protected_before.json')
assert fingerprints(protected) == protected == read(case / 'protected_after.json')
assert old['exit_code'] == 0 and old['protected_unchanged']
comm = read(case / 'output/comm/run001.summary.json')
manifest = [json.loads(x) for x in (case / 'output/manifest.jsonl').read_text().splitlines()]
assert comm['trials'] == 20 and not comm['errors']
assert len(comm['agents']) == len(manifest) == 1
assert comm['agents'][0]['type'] == manifest[0]['type'] == 'error'
assert 'runtime_capture' in manifest[0]['error'] and 'ModuleNotFoundError' in manifest[0]['error']
performance = [json.loads(x) for x in (case / 'agent0.performance.jsonl').read_text().splitlines()]
assert [x['trial'] for x in performance] == list(range(20))
ledgers = list((case / 'output/ledgers').rglob('*.jsonl.gz'))
dones = list((case / 'output/ledgers').rglob('*.done'))
assert len(ledgers) == len(dones) == 1
with gzip.open(ledgers[0], 'rb') as f:
    ledger_rows = [json.loads(x) for x in f]
assert ledger_rows[0]['trial_count'] == 20
assert ledger_rows[0]['code_commit'] == old['command']['commit']
assert [x['prediction_order'] for x in ledger_rows[1:]] == list(range(20))
done = read(dones[0])
assert done['trial_count'] == 20 and done['code_commit'] == old['command']['commit']
assert done['ledger_bytes'] == ledgers[0].stat().st_size
assert all(x['f_realized'] == ledger_rows[0]['f_setting'] for x in ledger_rows[1:])
errors = [(i, line) for i, line in enumerate((case / 'model.log').read_text().splitlines(), 1)
          if 'ModuleNotFoundError' in line]
assert errors
hashes = {str(p.relative_to(case)): dict(sha256=hashlib.sha256(p.read_bytes()).hexdigest(), bytes=p.stat().st_size)
          for p in case.rglob('*') if p.is_file()}
proof = read(here / 'observer_dependency_01.json')
assert hashlib.sha256(Path(proof['source']).read_bytes()).hexdigest() == proof['sha256']
assert hashlib.sha256(Path(proof['destination']).read_bytes()).hexdigest() == proof['sha256']
sys.path[:0] = [str(here), str(port / 'source_coll_instruction12_baseline/tools')]
helper = importlib.import_module('runtime_capture')
assert Path(helper.__file__).resolve() == Path(proof['destination']).resolve()
assert callable(helper.runtime_values)
assert fingerprints(protected) == protected
for source, commit in [('source_coll_instruction12_baseline', 'c4cfed12a3944071951775b2c9373ca27705fb25'),
                       ('source_coll_instruction12_B5', '92913206f5d3b4b4cfbcd1015e0aebf5351bf567')]:
    assert subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=port / source, text=True).strip() == commit
    assert not subprocess.check_output(['git', 'status', '--porcelain'], cwd=port / source, text=True).strip()
result = dict(at_jst=at, state='stopped_observer_dependency', outer_exit_code=0,
    native_completed=True, native_ledger_rows=20, researcher_export_completed=False, case_accepted=False, first_error=dict(file=str(case / 'model.log'), line=errors[0][0], text=errors[0][1]),
    agent_error=manifest[0], performance_rows=20, observed_trials=[0, 19],
    peak_agent_rss_bytes=max(x['peak_rss_bytes'] for x in performance),
    peak_children_rss_bytes=old['peak_children_rss_bytes'], model_seconds=old['model_seconds'],
    admission_wait_seconds=None, admission_timing_valid=False, cpu_wait_seconds=old['cpu_wait_seconds'],
    model_outputs_mismatch_detected=False, protected_unchanged=True, original_hashes=hashes,
    dependency_copy_verified=proof, observer_unchanged=True, candidate_changed=False, inspection01_reader_stop_preserved=True, inspection01_cause='rg --filesの除外対象だった台帳を不存在と読んだ。実在する台帳と完了札を全量検査する。',
    no_model_rerun_in_inspection=True, followup='同梱の依存だけを置いた別出力の20を受付へ通す。200は必要記録を確認してから。')
with (here / 'pilot20_failure_evidence_02.json').open('x') as f:
    json.dump(result, f, ensure_ascii=False, indent=2); f.write('\n')
print(json.dumps({k: result[k] for k in ['state', 'first_error', 'peak_agent_rss_bytes', 'protected_unchanged']}, ensure_ascii=False))

"""指示17の100を一度だけ受付へ通し、指示15と同じ11ファイルを比べる。"""
from pathlib import Path
from datetime import datetime, timezone
from types import SimpleNamespace
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
NR = ROOT.parent
PY = '/opt/homebrew/opt/python@3.12/bin/python3.12'
JOBS = str(Path.home() / 'jobs/jobs.py')
sys.path.insert(0, str(NR))
from inbox_snapshot import snapshot


def save(name, value):
    (ROOT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def state(**value):
    save('status.json', dict(at=datetime.now().astimezone().isoformat(),
                            supervisor_pid=os.getpid(), production_started=False, **value))


def time_values(log):
    text = log.read_text()
    time_match = re.search(r'([\d.]+)\s+real\s+([\d.]+)\s+user\s+([\d.]+)\s+sys', text)
    rss_match = re.search(r'(\d+)\s+maximum resident set size', text)
    assert time_match and rss_match, '原timeの実時間と最大常駐が未記録'
    return dict(real_seconds=float(time_match[1]), user_seconds=float(time_match[2]),
                system_seconds=float(time_match[3]), max_rss_bytes=int(rss_match[1]))


try:
    assert not (ROOT / 'status.json').exists(), '監督を二重起動しない'
    case = ROOT / 'on100_append_only'
    spec = json.loads((case / 'spec.json').read_text())
    baseline = NR / 'instruction15_logfix/on100_logfix'
    prepared = json.loads((ROOT / 'prepared.json').read_text())
    assert prepared['structural_pytest_passed'] == 26
    assert json.loads((baseline / 'result.json').read_text())['exit_code'] == 0
    prior_comparison = json.loads((NR / 'instruction15_logfix/on100_logfix_comparison.json').read_text())
    assert prior_comparison['passed'] and prior_comparison['file_count'] == 11
    assert json.loads((NR / 'measurements/allin_s01_300/cancelled_by_instruction14.json').read_text())['started'] is False
    assert datetime.now(timezone.utc) < datetime.fromisoformat(spec['start_deadline_jst'])
    for path, sha in spec['observer_files'].items():
        assert hashlib.sha256(Path(path).read_bytes()).hexdigest() == sha
    for path, sha in spec['sources'].items():
        assert subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=path, text=True).strip() == sha
        assert not subprocess.check_output(['git', 'status', '--porcelain'], cwd=path, text=True)
    for name in ('result.json', 'pid.json', 'jobs.log', 'resources.jsonl'):
        assert not (case / name).exists(), '同じ100へ再投入しない'
    assert not Path(spec['output']).exists()
    assert not (ROOT / 'on100_append_only_comparison.json').exists()
    state(state='preparing_start', completed_trials_confirmed=0)
    # 新しい模型の開始直前だけ、Mac全体の実workerと機械の原値を記録する。
    snapshot(SimpleNamespace(workspace=NR.parent.parent, output=ROOT / 'before_start.json'))
    machine = {key: subprocess.check_output(command, text=True) for key, command in {
        'physical_cpu': ['/usr/sbin/sysctl', '-n', 'hw.physicalcpu'],
        'physical_memory_bytes': ['/usr/sbin/sysctl', '-n', 'hw.memsize'],
        'vm_stat': ['/usr/bin/vm_stat'],
        'swap': ['/usr/sbin/sysctl', 'vm.swapusage'],
        'thermal': ['/usr/bin/pmset', '-g', 'therm']}.items()}
    machine.update(at=datetime.now().astimezone().isoformat(), free_disk_bytes=shutil.disk_usage(case).free,
                   swap_window_minutes=10, swap_samples=(Path.home() / 'jobs/swap.tsv').read_text().splitlines()[-11:])
    save('machine_before_start.json', machine)
    state(state='running_or_waiting', label='on100_append_only', completed_trials_confirmed=0)
    command = ['/usr/bin/python3', JOBS, 'run', '--wait', '--owner', 'Codex 動詞 指示17 INFO・IDS 100',
               '--mem', str(spec['memory_reservation_gb']), '--disk-path', spec['output'], '--',
               PY, str(NR / 'run_case.py'), str(case)]
    with (case / 'jobs.log').open('x') as log:
        rc = subprocess.call(command, stdout=log, stderr=subprocess.STDOUT)
    assert rc == 0, ('on100_append_only', rc)
    result = json.loads((case / 'result.json').read_text())
    assert result['exit_code'] == 0
    manifest = [json.loads(line) for line in (case / 'output/manifest.jsonl').read_text().splitlines()]
    partial = json.loads((case / 'output/measurement/partial_done.json').read_text())
    assert len(manifest) == 1 and not manifest[0].get('error')
    for item in (manifest[0], partial):
        assert item['completed_trials'] == 100 and item['configured_trial_count'] == item['horizon'] == 5000
        assert item['full_5000_completed'] is False
    state(state='comparing100', completed_trials_confirmed=100)
    command = ['/usr/bin/python3', JOBS, 'run', '--wait', '--owner', 'Codex 動詞 指示17 100比較',
               '--mem', '.3', '--disk-path', str(ROOT), '--', PY, str(ROOT / 'compare_append_only100.py')]
    with (ROOT / 'comparison.jobs.log').open('x') as log:
        rc = subprocess.call(command, stdout=log, stderr=subprocess.STDOUT)
    comparison = json.loads((ROOT / 'on100_append_only_comparison.json').read_text())
    assert rc == 0 and comparison['passed'] and comparison['file_count'] == 11
    times = dict(baseline=time_values(baseline / 'run.log'), append_only=time_values(case / 'run.log'),
                 baseline_run_case=json.loads((baseline / 'result.json').read_text()),
                 append_only_run_case=result, configured_trial_count=5000, horizon=5000,
                 completed_trials=100, full_5000_completed=False)
    save('timing_comparison.json', times)
    state(state='append_only100_gate_passed', completed_trials_confirmed=100,
          comparison_passed=True, file_count=11, mismatching_files=0, timing_comparison=times)
except Exception as exc:
    state(state='stopped', reason=repr(exc))
    raise

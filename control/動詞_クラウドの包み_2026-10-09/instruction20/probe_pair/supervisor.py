"""指示20の同じMacの試験つき100を二本だけ受付し、完了後に一度だけ比べる。"""
from datetime import datetime, timezone
from pathlib import Path
import json
import os
import subprocess
from pair_common import ROOT, read, sha, validate_spec
from instruction11_io import save

PY = '/opt/homebrew/opt/python@3.12/bin/python3.12'
JOBS = str(Path.home() / 'jobs/jobs.py')


def state(**value):
    (ROOT / 'status.json').write_text(json.dumps(dict(at=datetime.now().astimezone().isoformat(),
          supervisor_pid=os.getpid(), production_started=False, **value), ensure_ascii=False, indent=2) + '\n')


try:
    assert not (ROOT / 'status.json').exists(), '二本の監督を二重起動しない'
    prepared = read(ROOT / 'prepared.json')
    assert prepared['non_model_tests_passed'] == 4
    for filename, expected in prepared['files'].items():
        assert sha(ROOT / filename) == expected
    cases = [ROOT / ('probe100_' + mode) for mode in ('off', 'on')]
    for case, mode in zip(cases, ('off', 'on')):
        spec = read(case / 'spec.json')
        validate_spec(spec, mode)
        assert datetime.now(timezone.utc) < datetime.fromisoformat(spec['start_deadline_jst'])
        assert not Path(spec['output']).exists()
        for filename in ('jobs.log', 'launcher_pid.json', 'result.json', 'pid.json', 'admitted_status.json'):
            assert not (case / filename).exists(), '同じ二本を再受付しない'
    assert not (ROOT / 'probe100_comparison.json').exists()
    state(state='submitting_pair', completed_trials_confirmed=0)
    children = []
    for case in cases:
        spec = read(case / 'spec.json')
        command = ['/usr/bin/python3', JOBS, 'run', '--wait', '--owner', 'Codex 動詞 指示20 ' + case.name,
                   '--mem', str(spec['memory_reservation_gb']), '--disk-path', spec['output'], '--',
                   PY, str(ROOT / 'admitted_gate.py'), str(case)]
        with (case / 'jobs.log').open('x') as log:
            child = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT)
        save(case / 'launcher_pid.json', dict(pid=child.pid, submitted_at=datetime.now().astimezone().isoformat(), command=command))
        children.append(child)
    state(state='pair_running_or_waiting', completed_trials_confirmed=0, jobs_pids=[child.pid for child in children])
    # 片側が失敗しても他方は停止せず、両方の原終了を待つ。
    return_codes = [child.wait() for child in children]
    assert return_codes == [0, 0], ('片側の例外・未完了は関門に使わない', return_codes)
    state(state='comparing_pair', completed_trials_confirmed=[100, 100])
    command = ['/usr/bin/python3', JOBS, 'run', '--wait', '--owner', 'Codex 動詞 指示20 試験つき100比較',
               '--mem', '.3', '--disk-path', str(ROOT), '--', PY, str(ROOT / 'compare_probe100.py')]
    with (ROOT / 'comparison.jobs.log').open('x') as log:
        rc = subprocess.call(command, stdout=log, stderr=subprocess.STDOUT)
    comparison = read(ROOT / 'probe100_comparison.json')
    assert rc == 0 and comparison['passed'], ('不一致は直さず新しい旗つき本番を保留', comparison['mismatching_files'])
    state(state='probe100_pair_gate_passed', completed_trials_confirmed=[100, 100], comparison_passed=True,
          mismatching_files=0, file_count=comparison['file_count'], probe_rows_excluded=0,
          timing_comparison=read(ROOT / 'timing_comparison.json'), new_primary19_started=False)
except Exception as exc:
    state(state='stopped', reason=repr(exc), new_primary19_started=False)
    raise

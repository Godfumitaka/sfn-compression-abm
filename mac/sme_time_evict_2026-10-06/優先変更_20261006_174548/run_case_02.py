"""受付済みの一条件。実時間・最大常駐・資源の記録を残す。"""
from pathlib import Path
from datetime import datetime
import json
import os
import signal
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parent
folder = Path(sys.argv[1]).resolve()
spec = json.loads((folder/'run_spec.json').read_text()) if (folder/'run_spec.json').exists() else {}
source = Path(spec.get('source', str(ROOT/'source')))
ns = {'__file__': str(ROOT / 'conditions_01.py')}
exec((ROOT.parent / 'codex_sme_keyfast_2026-10-04/run_profiles.py').read_text().split("for name in ('profile_A_01'")[0], ns)
conditions = ns['conditions']
row = conditions()
assert row['free_bytes'] >= 20*2**30 and not row['swap_grew'] and not row['thermal_warning'], row
assert not (folder / 'run.log').exists(), '記録の上書きと二重走行はしない'
expected = spec['commit']
assert subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=source, text=True).strip() == expected
assert not subprocess.check_output(['git', 'status', '--porcelain'], cwd=source, text=True).strip()
command = json.loads((folder / 'command.json').read_text())
validation = json.loads(Path(spec['validation_command']).read_text()) if spec.get('validation_command') else command
assert validation[validation.index('--seeds') + 1] in ('1', '2', '3')
(folder / 'resources_start.json').write_text(json.dumps(row, ensure_ascii=False, indent=2) + '\n')
env = dict(os.environ, PYTHONHASHSEED='0', SME_EXACT_SOURCE=str(source), SME_MEMORY_DIAG='1' if spec.get('memory_diag') else '0', SME_PROFILE_TRIAL_LIMIT=str(spec['measured_trials']))
for key in ('LC_ALL', 'LANG', 'LC_CTYPE'):
    env.pop(key, None)
begin = time.perf_counter()
started = datetime.now().astimezone().isoformat()
with (folder / 'run.log').open('x') as out:
    child = subprocess.Popen(command, cwd=source, env=env, stdin=subprocess.DEVNULL,
                             stdout=out, stderr=subprocess.STDOUT, start_new_session=True)
    (folder / 'model_pid.json').write_text(json.dumps({'pid': child.pid, 'pgid': child.pid,
        'source': str(source), 'command': command}) + '\n')
    next_sample = 0
    while child.poll() is None:
        if time.monotonic() >= next_sample:
            row = conditions()
            raw=subprocess.check_output(['/bin/ps','-axo','pid=,pgid=,rss=,command='],text=True)
            process_group=[]
            for line in raw.splitlines():
                at=line.strip().split(None,3)
                if len(at)==4 and int(at[1])==child.pid:
                    process_group.append({'pid':int(at[0]),'rss_kib':int(at[2]),'command':at[3]})
            row['own_process_group']=process_group
            row['own_process_group_rss_bytes']=sum(p['rss_kib'] for p in process_group)*1024
            with (folder / 'resources.jsonl').open('a') as log:
                log.write(json.dumps(row, ensure_ascii=False) + '\n')
            if row['free_bytes'] < 18.5*2**30 or row['swap_grew'] or row['thermal_warning']:
                assert os.getpgid(child.pid) == child.pid
                os.killpg(child.pid, signal.SIGSTOP)
                (folder / 'resource_stop.json').write_text(json.dumps({'at': datetime.now().astimezone().isoformat(),
                    'resource': row, 'paused_own_pgid': child.pid}, ensure_ascii=False, indent=2) + '\n')
                # 自分の止まった処理の受付を残し、後続に進めない。
                while True:
                    time.sleep(15)
            next_sample = time.monotonic()+15
        time.sleep(2)
    result = {'exit': child.returncode, 'wall_seconds': time.perf_counter()-begin,
              'started': started, 'finished': datetime.now().astimezone().isoformat(), 'cprofile': True}
(folder / 'run_result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
assert child.returncode == 0, '走行の不通。後続に進めない'
output = Path(spec.get('output',str(folder/'output')))
manifest = json.loads(next((output/'manifest.jsonl').open()))
assert not manifest.get('err') and not manifest.get('error'), manifest
assert manifest['trial_count'] == int(validation[validation.index('--trial-count')+1])
assert json.loads((folder/'timing_complete.json').read_text())['trials']==spec['measured_trials']
if spec['measured_trials']<manifest['trial_count']:
    assert manifest.get('measurement_only') and manifest['measured_trials']==spec['measured_trials']
    assert json.loads((folder/'prefix_complete.json').read_text())['next_trial_not_evaluated']
(folder / 'run_complete.json').write_text(json.dumps({'passed': True, 'run': result,
    'elapsed_sec': manifest['elapsed_sec'], 'peak_rss_mb': manifest['peak_rss_mb'],
    'trial_count': manifest['trial_count'], 'measured_trials':spec['measured_trials'], 'measurement_only':bool(manifest.get('measurement_only')), 'seed': manifest['seed'], 'commit': expected}, ensure_ascii=False, indent=2)+'\n')
print(folder.name, result, 'peak_rss_mb', manifest['peak_rss_mb'], flush=True)

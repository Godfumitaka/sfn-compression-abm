"""承認済みの機械停止から受付表で再開。関門合格後だけcProfileの一本を受付する。"""
from pathlib import Path
import hashlib
import json
import os
import signal
import subprocess
import sys
import time
import traceback

root = Path(__file__).resolve().parent
source = root / 'source'
sys.path[:0] = [str(source/'tools/v311c_checks'), str(source/'tools'), str(source)]
import coll8_gate as g
from v311c_fingerprint import VERSION

previous = json.loads((root/'evidence/restart-20261004/gates.json').read_text())
assert previous['status'] == 'stopped' and '機械の並列上限' in previous['reason']
assert all(c['passed'] for c in previous['checks'])
code = subprocess.check_output(['git','rev-parse','HEAD'], cwd=source, text=True).strip()
assert code == previous['source_commit'] and VERSION == previous['fingerprint_version']
ev = root/'evidence/resume-jobs-20261004'
out = root/'outputs/resume-jobs-20261004'
ev.mkdir(exist_ok=True)
out.mkdir(exist_ok=True)
assert not (ev/'gates.json').exists(), '夜の再開の出力を勝手に再使用しない'
g.OUT = out
jobs = Path('/Users/tatsu-admin/jobs/jobs.py')
result = {**previous, 'status': 'running', 'started': g.now(),
          'resumed_from': str(root/'evidence/restart-20261004/gates.json'),
          'previous_stop': {k:previous[k] for k in ('reason','finished')},
          'fingerprint_version': VERSION, 'source_commit': code, 'completed_new_jobs': [],
          'active_jobs': [], 'pending_jobs': [], 'profile_started': False,
          'jobs_sha256_initial': hashlib.sha256(jobs.read_bytes()).hexdigest(),
          'receipt_memory_gb_per_job': 4.0, 'own_receipt_backlog_limit': 3,
          'old_fixed_machine_process_cap_used': False, 'main_run_started': False}
result.pop('reason', None)
result.pop('traceback', None)
result.pop('finished', None)
completed = {r['name'] for r in previous['runs']}
old_out = root/'outputs/restart-20261004'
active = {}
pending = []

def checkpoint():
    result['active_jobs'] = list(active)
    result['pending_jobs'] = [s['name'] for s in pending]
    g.save(ev/'gates.json', result)

def specification(name, run, q, m, agent=None, kind='population'):
    kw = dict(run=run, q=q, m=m)
    if agent is not None:
        kw['solo_agent'] = agent
        kind = 'solo'
    reference = (old_out if run == 1 else out)/f'no_comm_r{run}'
    argv = g.argv(name, 1740, **kw)
    assert argv[argv.index('--v311c-runs')+1] in ('1','2','3')
    assert '--v311c-serial' in argv
    return {'name':name, 'kind':kind, 'run':run, 'q':q, 'm':m, 'agent':agent,
            'argv':argv, 'source_commit':code, 'reference':str(reference),
            'extra_env':({'COLL8_SOLO_AGENT':str(agent)} if agent is not None else {}),
            'dependency':None if q == 0 and agent is None else f'no_comm_r{run}'}

# 初めに通信なしを受付し、種2・3の独立比較と開示列比較の前提を揃える。
for run in (2,3):
    pending.append(specification(f'no_comm_r{run}', run, 0, 0))
for run in (1,2,3):
    for agent in range(8):
        name = f'solo_r{run}_a{agent}'
        if name not in completed:
            pending.append(specification(name, run, 0, 0, agent=agent))
    for m in (0,0.1,0.3):
        pending.append(specification(f'comm_m{m}_r{run}', run, 0.2, m))
assert len(pending) == 33
g.save(ev/'plan.json', pending)

def launch(spec):
    name = spec['name']
    folder = ev/name
    folder.mkdir()
    specfile = folder/'spec.json'
    g.save(specfile, spec)
    argv = [g.PYTHON, str(jobs), 'run', '--wait', '--owner', 'Codex3 集団化 '+name,
            '--mem','4.0','--disk-path',str(out),'--',g.PYTHON,
            str(root/'resume_registered_worker_20261004.py'),str(specfile)]
    log = (folder/'receipt-console.log').open('w')
    process = subprocess.Popen(argv, cwd=root, stdout=log, stderr=subprocess.STDOUT,
                               start_new_session=True)
    active[name] = {'process':process, 'log':log, 'spec':spec}
    g.save(folder/'receipt-command.json', {'argv':argv, 'pid':process.pid, 'submitted':g.now()})
    print('受付へ提出 '+name, flush=True)
    checkpoint()

def finish(name):
    task = active.pop(name)
    task['log'].close()
    file = ev/name/'gates.json'
    if not file.exists():
        raise RuntimeError('受付又は検査が不成立：'+name)
    local = json.loads(file.read_text())
    result['checks'].extend(local['checks'])
    result['runs'].extend(local['runs'])
    if task['process'].returncode != 0 or local['status'] != 'passed' or any(not c['passed'] for c in local['checks']):
        raise RuntimeError('関門不成立：'+name+': '+local.get('reason',''))
    completed.add(name)
    result['completed_new_jobs'].append(name)
    print('検査合格 '+name, flush=True)
    checkpoint()

def stop_own_jobs():
    for task in active.values():
        if task['process'].poll() is None:
            os.killpg(task['process'].pid, signal.SIGTERM)
    for task in active.values():
        try:
            task['process'].wait(timeout=30)
        except subprocess.TimeoutExpired:
            # 他セッションへは信号を送らない。
            os.killpg(task['process'].pid, signal.SIGKILL)
            task['process'].wait()
        task['log'].close()

def main():
    checkpoint()
    while pending or active:
        for name in list(active):
            if active[name]['process'].poll() is not None:
                finish(name)
        while len(active) < 3:
            spec = next((s for s in pending if not s['dependency'] or s['dependency'] in completed), None)
            if spec is None:
                break
            pending.remove(spec)
            launch(spec)
        time.sleep(2)
    result['gates_status'] = 'passed'
    result['gates_finished'] = g.now()
    checkpoint()
    print('全ての関門が合格。cProfileの試走一本だけを受付へ提出する。', flush=True)
    spec = specification('profile_r1_m0.1', 1, 0.2, 0.1, kind='profile')
    spec['argv'][1] = str(root/'profile_collective_20261004.py')
    spec['extra_env']['COLL8_PROFILE_DIR'] = str(out/spec['name']/'profiles')
    spec['equivalent'] = str(out/'comm_m0.1_r1')
    result['profile_started'] = True
    launch(spec)
    while active[spec['name']]['process'].poll() is None:
        time.sleep(2)
    finish(spec['name'])
    result.update(status='passed', finished=g.now())
    checkpoint()

if __name__ == '__main__':
    try:
        main()
    except BaseException as error:
        stop_own_jobs()
        result.update(status='stopped', reason=str(error), finished=g.now(), traceback=traceback.format_exc())
        checkpoint()
        print(result['traceback'], flush=True)
        sys.exit(1)

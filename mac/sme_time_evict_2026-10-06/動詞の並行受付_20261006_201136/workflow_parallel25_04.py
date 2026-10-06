"""動いているお店の計測を継承し、動詞を別に受付へ入れる。模型は変更しない。"""
from pathlib import Path
from datetime import datetime
from types import SimpleNamespace
import json, os, signal, subprocess, sys, time, traceback

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent / 'codex_logp_main_2026-10-06'))
from common_01 import PY, JOBS, conditions, cpu_reading, descendants, now, ps, save

PLAN = json.loads((ROOT / 'profile_plan_02.json').read_text())
START = json.loads((ROOT / 'parallel_priority25_adoption.json').read_text())
last_report = time.monotonic()
jobs = {}
cases = {c['name']: {'case': c, 'stage': 'profile', 'reported': False} for c in PLAN}

def report(phase, text, proofs):
    (ROOT / (phase + '.md')).write_text(text)
    save(ROOT / (phase + '_proofs.json'), proofs)
    subprocess.run([PY, str(ROOT / 'report_02.py'), phase], check=True)

def launch(folder, command, owner, case_name, stage):
    assert not (folder / 'claim_pid.json').exists(), '二重の受付をしない'
    resource = conditions()
    assert resource['free_bytes'] >= 20 * 2**30 and not resource['swap_grew'] and not resource['thermal_warning'], resource
    cmd = [PY, JOBS, 'run', '--wait', '--owner', owner, '--mem', '2.5', '--disk-path', str(folder), '--', *command]
    with (folder / 'claim.log').open('x') as out:
        child = subprocess.Popen(cmd, stdout=out, stderr=subprocess.STDOUT, start_new_session=True, stdin=subprocess.DEVNULL)
    save(folder / 'claim_pid.json', {'pid': child.pid, 'command': cmd, 'at': now()})
    jobs[case_name] = {'pid': child.pid, 'child': child, 'folder': folder, 'stage': stage, 'paused': False, 'adopted': False}
    return child.pid

def progress_rows():
    ans = {}
    for name, state in cases.items():
        folder = Path(state['case']['folder'])
        completed = None
        timing = folder / 'sec_trial.csv'
        if timing.exists():
            with timing.open('rb') as f:
                f.seek(max(0, timing.stat().st_size - 2048))
                lines = f.read().decode(errors='replace').splitlines()
            if lines and lines[-1].split(',', 1)[0].isdigit():
                completed = int(lines[-1].split(',', 1)[0]) + 1
        job = jobs.get(name)
        ans[name] = {'stage': state['stage'], 'claim_pid': job['pid'] if job else None,
                     'completed_trials': completed, 'measured_trials': state['case']['measured_trials'],
                     'cpu_paused': job['paused'] if job else False, 'reported': state['reported']}
    return ans

def pause_own(job, rows, reason, cpu=None):
    p = job['folder'] / 'model_pid.json'
    if not p.exists():
        return False
    pid = json.loads(p.read_text())['pid']
    if pid not in rows or pid not in descendants(job['pid'], rows) or rows[pid]['pgid'] != pid:
        return False
    os.killpg(pid, signal.SIGSTOP)
    job['paused'] = True
    with (job['folder'] / 'cpu_pauses.jsonl').open('a') as f:
        f.write(json.dumps({'at': now(), 'signal': 'SIGSTOP', 'pgid': pid, 'reason': reason, 'cpu': cpu or {}}, ensure_ascii=False) + '\n')
    return True

try:
    shop = PLAN[0]
    adopted_folder = Path(shop['folder'])
    pid = json.loads((adopted_folder / 'claim_pid.json').read_text())['pid']
    assert pid == START['adopted_shop_claim_pid']
    jobs[shop['name']] = {'pid': pid, 'child': None, 'folder': adopted_folder, 'stage': 'profile',
                          'paused': START['shop_cpu_paused'], 'adopted': True}
    verb = PLAN[1]
    launch(Path(verb['folder']), [PY, str(ROOT / 'registered_profile_gate_03.py'), verb['folder']],
           'SME25 動詞の先頭1000試行 並行計測', verb['name'], 'profile')
    save(ROOT / 'parallel25_started.json', {'at': now(), 'pid': os.getpid(), 'profiles': progress_rows(),
                                          'model_changed': False, 'logp_new_runs_and_replay_held': True})
    last_saved = 0
    while not all(s['reported'] for s in cases.values()):
        resource = conditions()
        assert resource['free_bytes'] >= 18.5 * 2**30 and not resource['swap_grew'] and not resource['thermal_warning'], resource
        # 新しい動詞の処理を先に止め、既存のお店をできるだけ進める。
        for name in reversed([c['name'] for c in PLAN]):
            job = jobs.get(name)
            if job is None or job['stage'] != 'profile':
                continue
            reading = cpu_reading([{'child': SimpleNamespace(pid=j['pid'])} for j in jobs.values()])
            rows = ps()
            if reading['total_compute_count'] > 8 and not job['paused']:
                pause_own(job, rows, '模型の過程の上限8本', reading)
            elif reading['total_compute_count'] < 8 and job['paused']:
                model = job['folder'] / 'model_pid.json'
                if model.exists():
                    mid = json.loads(model.read_text())['pid']
                    if mid in rows and mid in descendants(job['pid'], rows) and rows[mid]['pgid'] == mid:
                        os.killpg(mid, signal.SIGCONT)
                        job['paused'] = False
                        with (job['folder'] / 'cpu_pauses.jsonl').open('a') as f:
                            f.write(json.dumps({'at': now(), 'signal': 'SIGCONT', 'pgid': mid, 'cpu': reading}, ensure_ascii=False) + '\n')
            assert not (job['folder'] / 'resource_stop.json').exists(), '資源の停止。後続を始めない'

        for name in list(jobs):
            job = jobs[name]
            rows = ps()
            alive = job['pid'] in rows and 'Z' not in rows[job['pid']]['stat']
            if job['child'] is not None:
                exit_code = job['child'].poll()
                alive = exit_code is None
            else:
                exit_code = None
            if alive:
                continue
            if exit_code is not None:
                assert exit_code == 0, (name, job['stage'], exit_code)
            state = cases[name]
            folder = Path(state['case']['folder'])
            stage = job['stage']
            del jobs[name]
            if stage == 'profile':
                assert (folder / 'run_complete.json').exists(), (name, '走行の完了記録がない')
                next_stage, script, subfolder = 'compare', 'compare_profile_02.py', 'compare_02'
            elif stage == 'compare':
                assert json.loads((folder / 'comparison.json').read_text())['passed'], (name, '一致の関門不通')
                next_stage, script, subfolder = 'analyze', 'analyze_profile_02.py', 'analyze_02'
            else:
                assert json.loads((folder / 'analysis.json').read_text())['passed']
                subprocess.run([PY, str(ROOT / 'finish_profile_02.py'), name], check=True)
                report(name, (ROOT / (name + '.md')).read_text(), json.loads((ROOT / (name + '_proofs.json')).read_text()))
                state['stage'] = 'complete'
                state['reported'] = True
                continue
            sub = folder / subfolder
            sub.mkdir(exist_ok=False)
            state['stage'] = next_stage
            launch(sub, [PY, str(ROOT / script), name], 'SME25 ' + name + ' ' + next_stage, name, next_stage)

        if time.monotonic() - last_saved >= 15:
            cpu = cpu_reading([{'child': SimpleNamespace(pid=j['pid'])} for j in jobs.values()])
            status = {'at': now(), 'state': 'parallel_measurements_or_checks', 'case': 'お店と動詞の並行計測',
                      'claim_pid': None, 'cases': progress_rows(), 'cpu': cpu, 'resources': resource,
                      'logp_new_runs_and_replay_held': True}
            save(ROOT / 'priority_status.json', status)
            with (ROOT / 'parallel_resources_04.jsonl').open('a') as f:
                f.write(json.dumps({**status, 'cpu': {k: v for k, v in cpu.items() if k != 'external_compute_processes'}}, ensure_ascii=False) + '\n')
            last_saved = time.monotonic()
        if time.monotonic() - last_report >= 1800:
            phase = '並行計測の進み_' + datetime.now().strftime('%Y%m%d_%H%M%S')
            snapshot = json.loads((ROOT / 'priority_status.json').read_text())
            snapshot['cpu'].pop('external_compute_processes', None)
            save(ROOT / (phase + '.json'), snapshot)
            report(phase, 'お店1740試行と動詞の先頭1000試行を別の受付で並行計測。内訳はCPU秒、実時間は別の列。現在の試行数と受付を添付。log Pの新規走行と再生分類は再開の指示まで停止。\n', [phase + '.json'])
            last_report = time.monotonic()
        time.sleep(2)

    save(ROOT / 'computation_complete.json', {'at': now(), 'passed': True, 'cases': [x['name'] for x in PLAN]})
    subprocess.run([PY, str(ROOT / 'finish_proposals_02.py')], check=True)
    report('二本の内訳と案', (ROOT / '二本の内訳と案.md').read_text(), json.loads((ROOT / '二本の内訳と案_proofs.json').read_text()))
    save(ROOT / 'all_complete_priority25.json', {'at': now(), 'passed': True, 'measured_trials': [1740, 1000],
                                               'compared_native_records': True, 'model_changed': False,
                                               'reported': json.loads((ROOT / 'reported_二本の内訳と案.json').read_text())})
    save(ROOT / 'priority_status.json', {'at': now(), 'state': 'computation_complete', 'claim_pid': None,
                                       'logp_new_runs_and_replay_held': True})
except Exception as e:
    paused = []
    rows = ps()
    for name, job in jobs.items():
        if job['stage'] == 'profile' and pause_own(job, rows, '並行計測の停止'):
            paused.append(name)
    save(ROOT / 'workflow_priority25_stop.json', {'at': now(), 'reason': str(e), 'traceback': traceback.format_exc(),
                                               'paused_own_profiles': paused, 'model_changed': False})
    if not (ROOT / 'report_stop.json').exists():
        try:
            report('並行計測停止_' + datetime.now().strftime('%Y%m%d_%H%M%S'), '25′の停止の事実。\n\n```json\n' + (ROOT / 'workflow_priority25_stop.json').read_text() + '```\n', ['workflow_priority25_stop.json'])
        except Exception:
            pass
    raise

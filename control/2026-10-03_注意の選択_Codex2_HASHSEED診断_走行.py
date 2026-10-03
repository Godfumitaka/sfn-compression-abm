"""模型の種は1のまま、Pythonのhashの種だけ1と2に変えて直列で診断する。"""
import datetime
import importlib.util
import json
import os
from pathlib import Path
import signal
import subprocess
import time
from zoneinfo import ZoneInfo

JOB = Path(__file__).resolve().parent
BASE = JOB.parent
CODE = BASE / 'run3380344'
child = None
state = {'status': 'preparing', 'model_seed': 1, 'hashseeds': [1, 2], 'completed_hashseeds': [], 'seeds2_to20_started': False, 'world2_started': False, 'phase2_started': False}


def stamp():
    return datetime.datetime.now(ZoneInfo('Asia/Tokyo')).isoformat()


def status(**changes):
    state.update(changes)
    state['time'] = stamp()
    temporary = JOB / 'status.tmp'
    temporary.write_text(json.dumps(state, ensure_ascii=False, indent=2) + '\n')
    temporary.replace(JOB / 'status.json')


def main():
    global child
    if (JOB / 'status.json').exists():
        raise RuntimeError('既存の診断を上書きしない')
    commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=CODE, text=True).strip()
    assert commit == '3380344add7f85ce2c3608656de5805995dcf971'
    assert not subprocess.check_output(['git', 'status', '--porcelain'], cwd=CODE, text=True)
    spec = importlib.util.spec_from_file_location('machine_control', BASE / 'world1_rebuild_supervisor.py')
    control = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(control)
    control.JOB, control.stamp = JOB, stamp
    initial = json.loads((BASE / 'world1_rebuild/commands.jsonl').read_text())
    baseline_environment = json.loads((BASE / 'world1_mac_repro/environment.json').read_text())
    baseline_flags = json.loads((BASE / 'world1_rebuild/n3_w1_A_L50/flag.json').read_text())
    assert initial['seed'] == 1 and initial['command'][-2:] == ['--seeds', '1']
    assert initial['command'][initial['command'].index('--workers') + 1] == '1'
    status()
    for hashseed in (1, 2):
        run = JOB / f'hashseed_{hashseed}'
        run.mkdir(exist_ok=False)
        output = run / 'n3_w1_A_L50'
        args = list(initial['command'])
        args[3] = str(output)
        env = dict(os.environ)
        env.pop('V38_FROM', None)
        env['PYTHONHASHSEED'] = str(hashseed)
        selected_environment = {k: env.get(k) for k in baseline_environment}
        assert all(selected_environment[k] == v for k, v in baseline_environment.items() if k != 'PYTHONHASHSEED')
        probe = json.loads(subprocess.check_output([args[0], '-c', 'import os,json; print(json.dumps({"PYTHONHASHSEED":os.environ.get("PYTHONHASHSEED"),"hash_sig_e":hash("sig_e"),"hash_hold":hash("hold")}))'], env=env, text=True))
        assert probe['PYTHONHASHSEED'] == str(hashseed)
        (run / 'environment.json').write_text(json.dumps({'environment': selected_environment, 'probe': probe}, ensure_ascii=False, indent=2) + '\n')
        (run / 'command.json').write_text(json.dumps({'command': args, 'cwd': str(CODE), 'code_commit': commit, 'model_seed': 1, 'hashseed': hashseed, 'command_difference': 'output_root', 'environment_difference': 'PYTHONHASHSEED'}, ensure_ascii=False, indent=2) + '\n')
        while control.machine(f'PYTHONHASHSEED={hashseed}・種1の開始前') >= 4:
            status(status='waiting_for_slot', current_hashseed=hashseed)
            time.sleep(30)
        with (run / 'seed001.log').open('w') as log:
            child = subprocess.Popen(args, cwd=CODE, env=env, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
            started = stamp()
            status(status='running', current_hashseed=hashseed, child_pid=child.pid, started_at=started)
            print(started, f'PYTHONHASHSEED={hashseed}、模型の種1開始、並列1', flush=True)
            paused = False
            while child.poll() is None:
                time.sleep(15)
                count = control.machine(f'PYTHONHASHSEED={hashseed}・種1の走行中', group=child.pid)
                if count >= 4 and not paused:
                    os.killpg(child.pid, signal.SIGSTOP)
                    paused = True
                    status(status='paused_for_sme_priority')
                    print(stamp(), 'SME優先で自分の計算を一時停止', flush=True)
                elif count < 4 and paused:
                    os.killpg(child.pid, signal.SIGCONT)
                    paused = False
                    status(status='running')
                    print(stamp(), '並列の空きに合わせて再開', flush=True)
        if child.returncode:
            raise RuntimeError(f'hashの種{hashseed}・走行の終了値={child.returncode}')
        assert json.loads((output / 'flag.json').read_text()) == baseline_flags
        done = list(output.glob('ledgers/cells/*/seed001.done'))
        assert len(done) == 1
        assert len(list(output.glob('ledgers/cells/*/seed*.jsonl.gz'))) == 1
        (run / 'completion.json').write_text(json.dumps({'started_at': started, 'finished_at': stamp(), 'flag_exact_match': True, 'done': json.loads(done[0].read_text())}, ensure_ascii=False, indent=2) + '\n')
        child = None
        state['completed_hashseeds'].append(hashseed)
        status(status='finished_hashseed', child_pid=None)
        print(stamp(), f'PYTHONHASHSEED={hashseed}・種1完走、旗は全欄一致', flush=True)
    control.machine('PYTHONHASHSEEDの二回の種1終了後')
    status(status='finished_two_seed1_runs_only', finished_at=stamp())


if __name__ == '__main__':
    try:
        main()
    except BaseException as error:
        if child is not None and child.poll() is None:
            os.killpg(child.pid, signal.SIGCONT)
            os.killpg(child.pid, signal.SIGTERM)
            try:
                child.wait(timeout=15)
            except subprocess.TimeoutExpired:
                os.killpg(child.pid, signal.SIGKILL)
                child.wait()
        status(status='stopped', child_pid=None, error=repr(error))
        raise

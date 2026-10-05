"""承認済みの大きなηの格子。固定候補を再利用し種ごとに受付表へ登録する。"""
import csv
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import time

JOB = Path(__file__).resolve().parent
BASE = JOB.parent
SOURCE = BASE/'source'
B = BASE/'stageB_doors_2026-10-05'
C = BASE/'stageCD_doors_2026-10-05'
SUPERVISION = JOB/'supervision'
PYTHON = '/opt/homebrew/bin/python3.12'
CODE = 'b40a6d4ec0213b0377a2144821273e73f296511d'
sys.path[:0] = [str(SOURCE/'tools'), str(SOURCE)]
import attnreplay_doors as R
import attnsummary as S
import attnaggregate as G

spec = importlib.util.spec_from_file_location('resource_supervisor', BASE/'stageB1_resumed_2026-10-04/run_baseline_registered.py')
M = importlib.util.module_from_spec(spec)
spec.loader.exec_module(M)
M.JOB, M.OUTPUT, M.MAX_WORKERS = SUPERVISION, JOB, 4
MEM_GB = .5  # 同じ段C/Dの127標本の最大151.8MB。標本の3.37倍を予約。
M.state = {'status': 'preparing', 'completed': {'1': [], '2': []},
           'code_commit': CODE, 'reservation_gb_per_job': MEM_GB, 'grid': 'large-eta',
           'phase3_started': False, 'seeds21_to40_read_or_run': False,
           'resource_policy': 'jobs_claim_2026-10-04_night',
           'task_instruction_assumption': '本人にドア課題の指示が伝えられるとみなしheld_out_is_doorを使う'}


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n')


def fingerprint(path):
    digest = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1024*1024), b''):
            digest.update(block)
    return {'path': str(path), 'bytes': path.stat().st_size, 'sha256': digest.hexdigest()}


def leaf(world, seed):
    assert world in (1, 2) and seed in range(1, 21)
    root = f'n3_w{world}_A_L50'
    folder = JOB/'batches'
    done = folder/f'w{world}_seed{seed:03d}.json'
    assert not done.exists()
    frozen = B/'frozen'/root
    freeze = json.loads((frozen/f'seed{seed:03d}.freeze.check.json').read_text())
    case = json.loads((C/'cases'/root/f'seed{seed:03d}.case.check.json').read_text())
    assert freeze['full_census'] and freeze['unit_weights_answers_match'] and freeze['unit_weights_scores_match']
    assert case['full_census'] and case['trials_compared'] == 1740 and case['mismatch'] is None
    assert case['memory_state_hash_changes'] == 0 and not case['existing_rng_consumed']
    paths = [frozen/f'seed{seed:03d}.frozen.jsonl.gz', frozen/f'seed{seed:03d}.freeze.check.json',
             C/'cases'/root/f'seed{seed:03d}.cases.jsonl.gz', C/'cases'/root/f'seed{seed:03d}.case.check.json']
    for suffix in ('attn.jsonl.gz', 'check.json'):
        paths.append(B/'replay'/root/f'seed{seed:03d}.arm0.b5_e0.05.{suffix}')
    inputs = [fingerprint(path) for path in paths]
    variants, grid = S.grid_spec('large-eta')
    final = []
    replays = []
    for arm, beta, eta in variants[1:]:
        result = R.replay(frozen, seed, JOB/'replay', arm=arm, beta=beta, eta=eta)
        assert result['full_census'] and result['trials_compared'] == 1740
        assert result['mismatch'] is None and result['non_door_answers_match']
        assert not result['model_updated'] and not result['existing_rng_consumed']
        for name, weight in sorted(result['weights_final'].items()):
            if arm == 2 and name in ('hold', 'hold_b'):
                assert weight == 1.
            final.append({'world': world, 'seed': seed, 'arm': arm, 'beta': beta, 'eta': eta,
                          'name': name, 'weight': weight})
        replays.append(result)
    summary = S.summarize_seed(world, seed, JOB, C/'cases', JOB/'summary', grid_name='large-eta')
    assert summary['passed'] and summary['mismatch'] is None and summary['variants'] == 17
    out = JOB/'summary'/root/f'seed{seed:03d}'/'final_weights.csv'
    S.write_csv(out, final, ('world', 'seed', 'arm', 'beta', 'eta', 'name', 'weight'))
    # 入力を変えていないことも、同じ原記録のsha256で確かめる。
    assert inputs == [fingerprint(path) for path in paths]
    save(done, {'passed': True, 'world': world, 'seed': seed, 'grid': grid,
                'replay_count': len(replays), 'replays': replays, 'summary': summary,
                'inputs_unchanged': True, 'inputs': inputs, 'final_weights': fingerprint(out),
                'phase3_started': False})
    print(f'世界{world}・種{seed}：16件の注意学習と17条件の集計完了', flush=True)


def preparation():
    if (SUPERVISION/'status.json').exists():
        raise RuntimeError('既存の監督を重複起動しない')
    for path in (SUPERVISION, JOB/'batches', JOB/'replay', JOB/'summary'):
        path.mkdir(exist_ok=True)
    head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=SOURCE, text=True).strip()
    assert head == CODE and not subprocess.check_output(['git', 'status', '--porcelain'], cwd=SOURCE, text=True)
    gate = json.loads((B/'all_door_gates.json').read_text())
    assert gate['passed'] and all(gate[f'B{i}_passed'] for i in range(1, 6))
    for destination, target in [(JOB/'frozen', B/'frozen'), (JOB/'all_door_gates.json', B/'all_door_gates.json')]:
        if destination.exists():
            assert destination.is_symlink() and destination.resolve() == target.resolve()
        else:
            destination.symlink_to(target)
    for world in (1, 2):
        root = f'n3_w{world}_A_L50'
        (JOB/'replay'/root).mkdir(exist_ok=True)
        for seed in range(1, 21):
            for suffix in ('attn.jsonl.gz', 'check.json'):
                name = f'seed{seed:03d}.arm0.b5_e0.05.{suffix}'
                link = JOB/'replay'/root/name
                if link.exists():
                    assert link.is_symlink() and link.resolve() == (B/'replay'/root/name).resolve()
                else:
                    link.symlink_to(B/'replay'/root/name)
    save(JOB/'pre_result_decisions.json', {
        'recorded_at': M.stamp(), 'code_commit': CODE, 'variants': S.grid_spec('large-eta')[0],
        'attention_runs': 640, 'worlds': [1, 2], 'seeds': list(range(1, 21)),
        'baseline': '保存済みの腕0をそのまま比較に使い、再計算しない',
        'reused': '固定候補の点の係数・門を含む開示前回答・実開示・分類',
        'model_or_memory_rebuilt': False, 'matcher_or_prediction_rerun': False,
        'attention_learning': '各腕・β・ηを全重み1から試行順に学習。今の答えは更新前。',
        'normal_day_damage': '正解から外れ・黙りへの変化も全件を数える',
        'parameter_selection': False, 'evaluation_of_good_or_bad': False,
        'stageD_rerun': False, 'phase3_started': False,
        'task_instruction_assumption': M.state['task_instruction_assumption'],
        'tests': 'N3・注意・ドア・測度の33検査合格（既定の格子を保持、追加の格子の構造を検査）'})
    M.machine('大きなηの格子の開始前')
    M.status(status='prepared')


def start(world, seed):
    M.machine(f'大きなηの格子・世界{world}種{seed}の開始前')
    command = [PYTHON, M.JOBS, 'run', '--wait', '--owner', f'Codex2 大η W{world} seed{seed:03d}',
               '--mem', str(MEM_GB), '--disk-path', str(JOB), '--', PYTHON, str(Path(__file__)), 'leaf', str(world), str(seed)]
    log = (SUPERVISION/f'w{world}_seed{seed:03d}.log').open('x')
    process = subprocess.Popen(command, cwd=SOURCE, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
    M.active.append({'world': world, 'seed': seed, 'pid': process.pid, 'process': process, 'log': log, 'adopted': False})
    M.append('commands.jsonl', {'world': world, 'seed': seed, 'command': command, 'pid': process.pid})
    M.status(status='running_or_waiting_for_claim')


def main():
    preparation()
    pending = [(world, seed) for world in (1, 2) for seed in range(1, 21)]
    while pending or M.active:
        M.machine('大きなηの格子の稼働中')
        for item in list(M.active):
            if item['process'].poll() is None:
                continue
            path = JOB/'batches'/f"w{item['world']}_seed{item['seed']:03d}.json"
            result = json.loads(path.read_text()) if path.exists() else None
            if item['process'].returncode or not result or not result['passed']:
                M.state['failure'] = {'world': item['world'], 'seed': item['seed'],
                                      'exit_code': item['process'].returncode, 'check': result}
                raise RuntimeError('注意学習又は集計の検査で停止。該当ログ・欄を報告する')
            M.state['completed'][str(item['world'])].append(item['seed'])
            M.state['completed'][str(item['world'])].sort()
            M.append('summaries.jsonl', {'world': item['world'], 'seed': item['seed'],
                                       'passed': True, 'trial_records': result['summary']['trial_records']})
            M.registration('release', '--pid', str(item['pid']))
            item['log'].close()
            M.active.remove(item)
            M.status(status='running_or_waiting_for_claim')
            print(M.stamp(), f"世界{item['world']}・種{item['seed']}完了", flush=True)
        while pending and len(M.active) < 4:
            start(*pending.pop(0))
        if M.active:
            time.sleep(10)
    assert M.state['completed'] == {'1': list(range(1, 21)), '2': list(range(1, 21))}
    M.machine('大きなηの格子・40種の合計前')
    command = [PYTHON, M.JOBS, 'run', '--wait', '--owner', 'Codex2 大η 全集計', '--mem', '2.0',
               '--disk-path', str(JOB/'summary'), '--', PYTHON, str(SOURCE/'tools/attnaggregate.py'),
               '--aggregate-fixed-memory', '--stage', 'C', '--attn-grid', 'large-eta', '--output', str(JOB/'summary')]
    with (SUPERVISION/'aggregate.log').open('x') as log:
        child = subprocess.Popen(command, cwd=SOURCE, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        item = {'world': 0, 'seed': 0, 'pid': child.pid, 'process': child, 'adopted': False}
        M.active.append(item)
        M.append('commands.jsonl', {'command': command, 'pid': child.pid})
        M.status(status='aggregating')
        while child.poll() is None:
            time.sleep(10)
            M.machine('大きなηの格子の全集計中')
        path = JOB/'summary/all_C.json'
        check = json.loads(path.read_text()) if path.exists() else None
        if child.returncode or not check or not check['passed']:
            M.state['failure'] = {'stage': 'aggregate', 'exit_code': child.returncode, 'check': check}
            raise RuntimeError('追加格子の合計で停止')
        assert check['trial_records'] == 1183200 and check['door_trial_records'] == 107202
        M.registration('release', '--pid', str(child.pid))
        M.active.remove(item)
    M.machine('大きなηの格子の終了後')
    M.status(status='complete_large_eta_ready_for_report', finished_at=M.stamp())


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == 'leaf':
        leaf(int(sys.argv[2]), int(sys.argv[3]))
    else:
        try:
            main()
        except BaseException as error:
            M.stop_own_jobs()
            M.status(status='stopped', error=repr(error))
            raise

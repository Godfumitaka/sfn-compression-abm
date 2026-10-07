"""案(b)と較正の旗なしの全長関門。各本・比較を直列にし不通で止まる。"""
from pathlib import Path
import csv, gzip, json, os, signal, subprocess, sys, time

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / 'components_source'
WORK = ROOT / 'components_full_gate_01'
BASE = ROOT / 'native_full_01'
PY = '/opt/homebrew/opt/python@3.12/bin/python3.12'
sys.path[:0] = [str(ROOT.parent / 'codex_logp_main_2026-10-06'), str(ROOT.parent / 'codex_sme_time_evict_2026-10-06')]
from common_01 import save, now, conditions, ps, descendants
from cpu_guard_05 import cpu_reading
from compare_gate_01 import compare


def run(name, command):
    case = WORK / name
    assert not case.exists(), '完了済み・途中の本を二重に起動しない'
    case.mkdir()
    resources = conditions()
    assert resources['free_bytes'] >= 20 * 2**30 and not resources['swap_grew'] and not resources['thermal_warning']
    assert cpu_reading([])['total_compute_count'] < 8
    save(WORK / 'current.json', dict(at=now(), case=name, command=command, cwd=str(SOURCE), resources=resources))
    start, held_at, paused, peak = time.monotonic(), None, 0.0, 0
    with (case / 'run.log').open('x') as log:
        proc = subprocess.Popen(command, cwd=SOURCE, env=dict(os.environ, PYTHONHASHSEED='0'),
                                stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        save(case / 'started.json', dict(at=now(), runner_pid=proc.pid, command=command,
                                       env={'PYTHONHASHSEED': '0'}, memory_claim_gb=12))
        while proc.poll() is None:
            time.sleep(2)
            safe = conditions()
            count = cpu_reading([])['total_compute_count']
            processes = ps()
            rss = sum(processes[p]['rss'] for p in descendants(proc.pid, processes) if p in processes)
            peak = max(peak, rss)
            with (case / 'resources.jsonl').open('a') as stream:
                stream.write(json.dumps(dict(at=now(), rss_bytes=rss, free_bytes=safe['free_bytes'],
                                             swap_mb=safe['swap_mb'], swap_grew=safe['swap_grew'],
                                             thermal_warning=safe['thermal_warning'], model_processes=count)) + '\n')
            bad = safe['free_bytes'] < 18.5 * 2**30 or safe['swap_grew'] or safe['thermal_warning'] or count > 8
            if bad and held_at is None:
                os.killpg(proc.pid, signal.SIGSTOP)
                held_at = time.monotonic()
                save(case / 'resources_hold.json', dict(at=now(), resources=safe, model_processes=count))
            elif held_at is not None and not bad and safe['free_bytes'] >= 20 * 2**30 and count < 8:
                os.killpg(proc.pid, signal.SIGCONT)
                paused += time.monotonic() - held_at
                held_at = None
        code = proc.returncode
    save(case / 'finished.json', dict(at=now(), exit=code, wall_seconds=time.monotonic()-start,
         paused_seconds=paused, maximum_observed_model_tree_rss_bytes=peak, sampling_seconds=2))
    if code:
        raise RuntimeError(name + '：全長の不通\n' + (case / 'run.log').read_text()[-4000:])
    manifest = json.loads((case / 'output/manifest.jsonl').read_text().splitlines()[-1])
    assert manifest['trial_count'] == 1740
    assert manifest['smereplay']['predictions'] == manifest['smereplay']['updates'] == 1740
    return case / 'output'


def candidate_comparison(online, replay):
    path_left = next((online / 'researcher').rglob('*.candidates.jsonl.gz'))
    path_right = next((replay / 'side').rglob('*.sme.candidates.jsonl.gz'))
    fields = ('R', 'prediction', 'hit', 'gate_passed', 'abstain_reason', 'source', 'slot', 'prediction_path')
    answers = next((online / 'side').rglob('*.answers.csv'))
    with answers.open() as stream:
        answer_rows = {int(r['trial']): r for r in csv.DictReader(stream)}
    n = 0
    with gzip.open(path_left, 'rt') as left, gzip.open(path_right, 'rt') as right:
        for line in left:
            actual = json.loads(line)
            expected = json.loads(next(right))
            assert actual['trial'] == expected['trial'] == n
            for key in ('prediction', 'chosen_R', 'original_hit', 'correct_gate_passed'):
                if actual[key] != expected[key]:
                    save(WORK / 'candidate_mismatch.json', dict(trial=n, field=key, actual=actual[key], expected=expected[key]))
                    raise RuntimeError(f'全長の再生分類：試行{n}、{key}が違う')
            observed = {c['R']: {k: c[k] for k in fields} for c in actual['candidates'] if c['gate_passed']}
            reference = {c['R']: {k: c[k] for k in fields} for c in expected['candidates'] if c['gate_passed']}
            if observed != reference:
                save(WORK / 'candidate_mismatch.json', dict(trial=n, actual=observed, expected=reference))
                raise RuntimeError(f'全長の再生分類：試行{n}の門を通る候補が違う')
            selected = next((c for c in actual['candidates'] if c['selected']), None)
            if n in answer_rows:
                assert selected is not None and selected['source'] == answer_rows[n]['source'], (n, '本物の答えの出どころ')
            n += 1
        assert next(right, None) is None and n == 1740
    save(WORK / 'candidate_comparison.json', dict(at=now(), passed=True, trials=n, fields=fields,
         source_compared_to_actual_answers=True, researcher_rows_only=True))


try:
    assert not (WORK / 'started.json').exists(), '監督の二重起動'
    assert json.loads((BASE / 'complete.json').read_text())['passed']
    assert json.loads((ROOT / 'components_replay_answers_gate_01/complete.json').read_text())['passed']
    head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=SOURCE, text=True).strip()
    assert head.startswith('7aaacc9') and not subprocess.check_output(['git', 'status', '--porcelain'], cwd=SOURCE).strip()
    save(WORK / 'started.json', dict(at=now(), pid=os.getpid(), source=head,
         memory_claim_gb=12, memory_basis='C*全1740試行のru_maxrss最大10458.6MiBと比較用の余裕',
         sequence=['off_A', 'off_L', 'online_Cstar', 'replay_Cstar']))
    for name in ('off_A', 'off_L'):
        command = list(json.loads((BASE / (name + '.json')).read_text())['command'])
        command[3] = str(WORK / name / 'output')
        output = run(name, command)
        compare(BASE / name / 'output', output, WORK / (name + '_comparison.json'), stop_first=True)
    command = list(json.loads((BASE / 'on_own.json').read_text())['command'])
    command[3] = str(WORK / 'online_Cstar/output')
    command += ['--sme-online-candidates', '--sme-online-check']
    online = run('online_Cstar', command)
    compare(BASE / 'on_own/output', online, WORK / 'online_Cstar_comparison.json', stop_first=True)
    original = list(json.loads((BASE / 'on_own.json').read_text())['command'])
    command_file = WORK / 'replay_command.json'
    command_file.write_text(json.dumps(original, ensure_ascii=False) + '\n')
    states = next((online / 'side').rglob('*.sme.states.jsonl.gz'))
    command = [PY, str(SOURCE / 'tools/selcands_sme.py'), '--answers-only', str(command_file),
               str(WORK / 'replay_Cstar/output'), str(states)]
    replay = run('replay_Cstar', command)
    candidate_comparison(online, replay)
    save(WORK / 'complete.json', dict(at=now(), passed=True, code=head, trials=1740,
         flags_off_A_and_logp_bytes=True, online_Cstar_model_bytes=True, replay_classification_equal=True))
except Exception as e:
    save(WORK / 'STOP.json', dict(at=now(), passed=False, reason=str(e), remaining_not_started=True))
    raise

"""指示8の小さな関門。既存の20試行を基準にし、最初の不通で止まる。"""
from pathlib import Path
import gzip, json, os, signal, subprocess, sys, time

ROOT = Path(__file__).resolve().parent
WORK = ROOT / 'components_preflight_01'
SOURCE = ROOT / 'components_source'
REFERENCE = ROOT / 'native_preflight_02'
PY = '/opt/homebrew/opt/python@3.12/bin/python3.12'
sys.path[:0] = [str(ROOT.parent / 'codex_logp_main_2026-10-06'), str(ROOT.parent / 'codex_sme_time_evict_2026-10-06')]
from common_01 import conditions, now, save
from cpu_guard_05 import cpu_reading
from compare_gate_01 import compare


def run(name, command):
    case = WORK / name
    assert not case.exists(), '同じ小走行を二重に起動しない'
    case.mkdir()
    safe = conditions()
    cpu = cpu_reading([])
    save(case / 'start.json', dict(at=now(), resources=safe, cpu=cpu, command=command,
                                 cwd=str(SOURCE), env={'PYTHONHASHSEED': '0'}))
    assert cpu['total_compute_count'] < 8 and safe['free_bytes'] >= 20 * 2**30
    assert not safe['swap_grew'] and not safe['thermal_warning']
    start = time.monotonic()
    with (case / 'run.log').open('x') as log:
        proc = subprocess.Popen(command, cwd=SOURCE, env=dict(os.environ, PYTHONHASHSEED='0'),
                                stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        held = False
        while proc.poll() is None:
            time.sleep(2)
            safe = conditions()
            count = cpu_reading([])['total_compute_count']
            bad = (safe['free_bytes'] < 18.5 * 2**30 or safe['swap_grew'] or safe['thermal_warning'] or count > 8)
            if bad and not held:
                os.killpg(proc.pid, signal.SIGSTOP)
                held = True
                save(case / 'resource_hold.json', dict(at=now(), resources=safe, count=count))
            elif held and safe['free_bytes'] >= 20 * 2**30 and not bad and count < 8:
                os.killpg(proc.pid, signal.SIGCONT)
                held = False
        code = proc.returncode
    save(case / 'finished.json', dict(at=now(), exit=code, wall_seconds=time.monotonic()-start))
    if code:
        raise RuntimeError(name + '：小走行の不通\n' + (case / 'run.log').read_text()[-3000:])
    return case / 'output'


def compare_candidates(online, replay, name):
    def read(path):
        with gzip.open(path, 'rt') as stream:
            return {r['trial']: r for r in map(json.loads, stream)}
    left = read(next((online / 'researcher').rglob('*.candidates.jsonl.gz')))
    right = read(next((replay / 'side').rglob('*.sme.candidates.jsonl.gz')))
    assert left.keys() == right.keys() == set(range(20))
    fields = ('R', 'prediction', 'hit', 'gate_passed', 'abstain_reason')
    for trial, row in left.items():
        ref = right[trial]
        for key in ('prediction', 'chosen_R', 'original_hit', 'correct_gate_passed'):
            if row[key] != ref[key]:
                raise RuntimeError(f'{name}：試行{trial}、{key}、{row[key]!r} != {ref[key]!r}')
        candidates = {c['R']: {k: c[k] for k in fields} for c in row['candidates'] if c['gate_passed']}
        expected = {c['R']: {k: c[k] for k in fields} for c in ref['candidates'] if c['gate_passed']}
        if candidates != expected:
            raise RuntimeError(f'{name}：試行{trial}の門を通る候補の答え・正誤が違う：{candidates!r} != {expected!r}')
    save(WORK / (name + '_candidates_comparison.json'), dict(at=now(), passed=True, trials=20, fields=list(fields)))


try:
    assert not (WORK / 'started.json').exists(), '同じ監督を二重に起動しない'
    save(WORK / 'started.json', dict(at=now(), pid=os.getpid(), implementation='a0d99f7', mem_gb=1,
                                   memory_basis='既存20試行のC*最大常駐68.3MB、比較用の余裕を含め1GB'))
    for baseline in ('off_A', 'off_L', 'on_own'):
        base_command = json.loads((REFERENCE / (baseline + '.json')).read_text())['command']
        command = list(base_command)
        command[3] = str(WORK / (baseline + '_off') / 'output')
        off = run(baseline + '_off', command)
        compare(REFERENCE / baseline / 'output', off, WORK / (baseline + '_off_comparison.json'), stop_first=True)
        on_command = list(base_command)
        on_command[3] = str(WORK / (baseline + '_online') / 'output')
        on_command += ['--sme-online-candidates', '--sme-online-check']
        online = run(baseline + '_online', on_command)
        compare(off, online, WORK / (baseline + '_online_comparison.json'), stop_first=True)
        if baseline != 'on_own':
            command_file = WORK / (baseline + '_command.json')
            command_file.write_text(json.dumps(base_command, ensure_ascii=False) + '\n')
            states = next((off / 'side').rglob('*.sme.states.jsonl.gz'))
            replay_command = [PY, str(SOURCE / 'tools/selcands_sme.py'), str(command_file),
                              str(WORK / (baseline + '_replay') / 'output'), str(states)]
            replay = run(baseline + '_replay', replay_command)
            compare_candidates(online, replay, baseline)
    command = list(json.loads((REFERENCE / 'on_own.json').read_text())['command'])
    command[3] = str(WORK / 'no_forget' / 'output')
    command += ['--no-forget-exec']
    noforget = run('no_forget', command)
    rows = list(map(json.loads, gzip.open(next((noforget / 'researcher').rglob('*.calibration.jsonl.gz')), 'rt')))
    assert [r['trial'] for r in rows] == list(range(20))
    assert all(c['V'] == c['numerator'] / c['denominator'] for r in rows for c in r['candidates'])
    save(WORK / 'no_forget_values.json', dict(at=now(), passed=True, trials=20,
         values=sum(len(r['candidates']) for r in rows), excluded=sum(len(r['excluded']) for r in rows)))
    save(WORK / 'complete.json', dict(at=now(), passed=True,
         cstar_replay_classification_gate='未実施。C*の対応と支持の門に再生の道具を接続する必要を確認中'))
except Exception as e:
    save(WORK / 'STOP.json', dict(at=now(), passed=False, reason=str(e), later_cases_not_started=True))
    raise

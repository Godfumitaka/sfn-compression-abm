"""列19pの指定を固定した自分の控えで、通常pushを確認して一度だけ受付へ通す。"""
from pathlib import Path
from datetime import datetime
import fcntl, hashlib, importlib.util, json, os, re, shutil, subprocess, sys

R = Path(__file__).resolve().parent
ROOT = R.parent
REPO = ROOT / 'codex_worldv4_2026-10-01/results'
LOCK = ROOT / 'codex_sme_light_2026-10-04/control_writer_01.lock'
VERB = ROOT / 'codex_verb_2026-10-04'
TOOLS = VERB / 'newport_2026-10-07/instruction27'
ORIGINAL = VERB / 'newport_2026-10-07/instruction27_production/19_seed001_flags_on'
CASE = R / 'queue19p_20261010/19_seed001_flags_on'
PUBLIC_SPEC = 'control/動詞_クラウドの包み_2026-10-09/instruction27/mac/spec.json'
REPORT = 'control/2026-10-07_C星の照合とディリクレ_実装_Codex.md'
QUEUE = 'control/走行の列_2026-10-08.md'
HEAD = '6e4bcba94874a4f49c5a1bae11d385534504e2e5'
PY = '/opt/homebrew/opt/python@3.12/bin/python3.12'
phase = sys.argv[1]
assert re.fullmatch(r'heartbeat_\d{8}_\d{4}', phase)
data = json.loads((R / (phase + '.json')).read_text())
assert not CASE.exists(), '自分の取得と受付を重複しない'
assert not any(not x['received'] and not x['held'] for x in data['instructions'])
assert data['cpu']['own_compute_count'] == data['cpu']['own_reserved_slots'] == 0
assert data['eligible_mac_rows'][0]['#'] == '19p'

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def git(*args):
    p = subprocess.run(['git', *args], cwd=REPO, capture_output=True, text=True)
    with (R / (phase + '_row19p_git.jsonl')).open('a') as f:
        f.write(json.dumps({'at': datetime.now().astimezone().isoformat(), 'args': args,
                           'exit': p.returncode, 'out': p.stdout, 'err': p.stderr}, ensure_ascii=False) + '\n')
    assert p.returncode == 0, p.stderr
    return p.stdout

try:
    # 動詞の係の開始待ちとの競合も、既存の同じロックで防ぐ。
    with (ORIGINAL / 'start_waiter.lock').open('a') as singleton:
        fcntl.flock(singleton, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with LOCK.open('a') as writer:
            fcntl.flock(writer, fcntl.LOCK_EX)
            assert not git('status', '--porcelain').strip(), '追記以外の汚れを解決しない'
            git('fetch', 'origin', 'results-2026-09-27')
            git('rebase', 'origin/results-2026-09-27')
            fetched = git('rev-parse', 'origin/results-2026-09-27').strip()
            for path, text in data['files'].items():
                assert git('show', fetched + ':' + path) == text, '新しい受け箱か列を先に読み直す'
            portable = git('show', fetched + ':' + PUBLIC_SPEC)
            local_expected = json.loads(portable.replace('$WORKSPACE', str(VERB)))
            original_bytes = (ORIGINAL / 'spec.json').read_bytes()
            original_spec = json.loads(original_bytes)
            assert local_expected == original_spec and original_spec['ready_to_start'] is False
            assert original_spec['source_commit'] == HEAD
            assert original_spec['cpu_start_slots'] == 6 and original_spec['model_start_slots'] == 5
            assert original_spec['memory_reservation_gb'] == 10 and original_spec['seed'] == 1
            assert datetime.now().astimezone() < datetime.fromisoformat(original_spec['start_deadline_jst'])
            for name in ('launcher_pid.json', 'pid.json', 'queue_claim_published.json', 'result.json', 'run.log'):
                assert not (ORIGINAL / name).exists(), '他係の取得や開始を重複しない'
            assert not Path(original_spec['output']).exists()
            source = Path(original_spec['cwd'])
            assert subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=source, text=True).strip() == HEAD
            assert not subprocess.check_output(['git', 'status', '--porcelain'], cwd=source)
            assert sha(TOOLS / 'run_registered.py') == original_spec['runner_sha256']
            assert all(sha(p) == h for p, h in original_spec['observer_files'].items())
            assert all(sha(TOOLS / p) == h for p, h in json.loads((TOOLS / 'fixed_tools.json').read_text()).items())
            for label in ('20', '22'):
                gate = json.loads((TOOLS / f'evidence/comparison{label}_approved.json').read_text())
                assert gate['passed'] and gate['mismatching_files'] == 0
                assert gate['manifest_counts_comparison']['passed']
            preparation = json.loads((TOOLS / 'preparation_checks.json').read_text())
            assert preparation['passed'] and preparation['model_starts'] == 0
            baseline = Path(original_spec['baseline_case'])
            assert sha(baseline / 'spec.json') == original_spec['baseline_spec_sha256']
            assert original_spec['flags'] == json.loads((baseline / 'spec.json').read_text())['flags'] + [
                '--verb-snap-append-only', 'on', '--stage2-birth-workers', '4']
            sys.path.insert(0, str(TOOLS))
            module_spec = importlib.util.spec_from_file_location('sme_row19p_registered', TOOLS / 'run_registered.py')
            module = importlib.util.module_from_spec(module_spec); module_spec.loader.exec_module(module)
            raw = subprocess.check_output(['/bin/ps', '-axo', 'pid=,ppid=,pgid=,rss=,stat=,args='], text=True)
            counts = module.start_counts(raw)
            assert counts['model_process_count'] + 5 <= 8 and counts['unknown_active_spawn'] == 0
            assert counts['outside_heavy'] + 6 <= 8
            sys.path.insert(0, str(ROOT / 'codex_sme_time_evict_2026-10-06'))
            from cpu_guard_05 import cpu_reading
            cpu = cpu_reading([])
            assert cpu['total_compute_count'] + 6 <= cpu['cap']
            assert shutil.disk_usage(ORIGINAL).free >= 20 * 2**30
            thermal = subprocess.check_output(['/usr/bin/pmset', '-g', 'therm'], text=True)
            assert 'No thermal warning level has been recorded' in thermal
            assert not re.search(r'CPU_Speed_Limit\s*=\s*(?!100(?:\s|$))\d+', thermal)
            swap = (Path.home() / 'jobs/swap.tsv').read_text().splitlines()[-11:]
            assert len(swap) == 11 and all(line.split('\t')[3] == 'ok' for line in swap)
            assert max(float(line.split('\t')[1]) for line in swap) == min(float(line.split('\t')[1]) for line in swap)
            assert int(swap[-1].split('\t')[0]) - int(swap[0].split('\t')[0]) >= 600
            assert datetime.now().timestamp() - int(swap[-1].split('\t')[0]) < 120
            assert (ORIGINAL / 'spec.json').read_bytes() == original_bytes
            CASE.mkdir(parents=True)
            (CASE / 'original_spec.json').write_bytes(original_bytes)
            spec = dict(original_spec, ready_to_start=True)
            (CASE / 'spec.json').write_text(json.dumps(spec, ensure_ascii=False, indent=2) + '\n')
            at = datetime.now().astimezone().isoformat()
            before = {'at': at, 'fetched_commit': fetched, 'cpu': cpu, 'model_count': counts['model_process_count'],
                      'outside_heavy': counts['outside_heavy'], 'unknown_models': counts['unknown_active_spawn'],
                      'cpu_start_slots': 6, 'model_start_slots': 5, 'memory_gib': 10,
                      'free_bytes': shutil.disk_usage(ORIGINAL).free, 'thermal': thermal, 'swap': swap,
                      'source_commit': HEAD, 'spec_sha256': sha(CASE / 'spec.json'),
                      'original_spec_sha256': sha(CASE / 'original_spec.json'), 'runner_sha256': sha(TOOLS / 'run_registered.py'),
                      'observer_files': spec['observer_files'], 'original_case_unchanged': True}
            (CASE / 'before_claim.json').write_text(json.dumps(before, ensure_ascii=False, indent=2) + '\n')
            lines = (REPO / QUEUE).read_text().splitlines()
            index = next(i for i, line in enumerate(lines) if line.startswith('| 19p |'))
            fields = lines[index].split('|'); assert fields[-2].strip() == '未着手'
            fields[-2] = f' 走行中（マック・SMEの係・列取得{at}、CPU6枠・実模型5枠・10GiB。通常push後に受付。開始控え{CASE.relative_to(ROOT)}） '
            lines[index] = '|'.join(fields)
            (REPO / QUEUE).write_text('\n'.join(lines) + '\n')
            proof = 'mac/cstar_2026-10-10/queue19p_claim_01'
            dest = REPO / proof; assert not dest.exists(); dest.mkdir(parents=True)
            for name in ('original_spec.json', 'spec.json', 'before_claim.json'):
                shutil.copy2(CASE / name, dest / name)
            shutil.copy2(__file__, dest / Path(__file__).name)
            for snapshot_phase in ('heartbeat_20261010_0356', phase):
                shutil.copy2(R / (snapshot_phase + '.json'), dest / (snapshot_phase + '.json'))
            shutil.copy2(R / 'heartbeat_20261010_0356_sampler.json', dest / 'heartbeat_20261010_0356_sampler.json')
            (dest / 'sha256.json').write_text(json.dumps({p.name: sha(p) for p in dest.iterdir() if p.is_file()}, indent=2) + '\n')
            received = '・'.join(re.search(r'指示 (\d+)', x['header'])[1] for x in data['instructions'] if x['received'])
            done = '・'.join(re.search(r'指示 (\d+)', x['header'])[1] for x in data['instructions'] if x['done'])
            with (REPO / REPORT).open('a') as f:
                f.write(f'\n\n### 継続確認と列19pの取得：{at}\n\n取り込み{fetched}。受領済み指示{received}、済み{done}。指示全体の保留0件、旧診断3欄の省略の仕様確認1件は保留。新規未受領0件。\n\n')
                for snapshot_phase in ('heartbeat_20261010_0356', phase):
                    s = json.loads((R / (snapshot_phase + '.json')).read_text())
                    f.write(f"確認{s['at']}、取り込み{s['fetched_commit']}。模型の過程は自分{s['cpu']['own_compute_count']}・他{s['cpu']['external_count']}・計{s['cpu']['total_compute_count']}本、上限8。列19pは未着手1件。\n\n")
                f.write(f"取得直前は模型の過程{cpu['total_compute_count']}本、実模型{counts['model_process_count']}本、未知0。指定CPU6枠を足して8以下、実模型5枠を足して8以下。10GiBの元の見込みを維持し、空き{before['free_bytes']}バイト、熱警告なし、10分のスワップ増加0。\n\n")
                f.write(f'列の上から取れる最初の行19pを取得。版{HEAD}、種1・試行5000・horizon5000、元の全旗に指定の二旗だけ、観察器の固定SHA一致、既存の小関門20・22は不一致0件。模型や関門検査を再実行していない。元の開始待ちのPID45475・26749は生存なし、元の出力・受付・模型の開始印なし。元の仕様と他係の作業状態は変更せず、自分の仕様の控えだけ開始可能と記録。通常pushと最新の取得を確認後、同じ指定出力へ10GiBの受付を一度作る。全5000の旗あり結果は未完了・仮、λは動詞較正まで仮。\n\n')
                f.write(f'小さい証拠：{proof}。30分間隔と2026-10-13 09:00日本時間の期限を維持。完了した25′・C*の観測・比較・集計を再起動せず、古いlog Pと再生分類の停止を維持。\n')
            git('sparse-checkout', 'add', proof)
            git('add', '--sparse', QUEUE, REPORT, proof)
            git('commit', '-m', 'SME: 指定枠と固定仕様を確認して列19pを取得')
            git('fetch', 'origin', 'results-2026-09-27')
            git('rebase', 'origin/results-2026-09-27')
            git('push', 'origin', 'HEAD:results-2026-09-27')
            commit = git('rev-parse', 'HEAD').strip()
            git('fetch', 'origin', 'results-2026-09-27')
            latest = git('rev-parse', 'origin/results-2026-09-27').strip()
            claimed = next(line for line in git('show', latest + ':' + QUEUE).splitlines() if line.startswith('| 19p |'))
            assert claimed == lines[index], '最新でも自分の取得が有効でなければ始めない'
            assert git('show', latest + ':control/受け箱/SMEの係.md') == data['files']['control/受け箱/SMEの係.md']
            claim = {'at': at, 'case_label': CASE.name, 'normal_push_succeeded': True, 'machine': 'Mac',
                     'commit': commit, 'latest_checked_commit': latest, 'spec_sha256': sha(CASE / 'spec.json'),
                     'queue_row': '19p', 'proof': proof, 'own_case': str(CASE), 'output': spec['output']}
            (CASE / 'queue_claim_published.json').write_text(json.dumps(claim, ensure_ascii=False, indent=2) + '\n')
            pending = json.loads((R / 'pending_01.json').read_text())
            pending['queue19p_case'] = str(CASE); pending['queue19p_claim'] = claim
            pending['heartbeat_mac_ready_resource_wait'] = None
            (R / 'pending_01.json').write_text(json.dumps(pending, ensure_ascii=False, indent=2) + '\n')
        assert datetime.now().astimezone() < datetime.fromisoformat(spec['start_deadline_jst'])
        assert not Path(spec['output']).exists() and not (CASE / 'launcher_pid.json').exists()
        command = [PY, str(Path.home() / 'jobs/jobs.py'), 'run', '--wait', '--owner', 'SME_Codex_queue19p_seed1',
                   '--mem', '10', '--disk-path', spec['output'], '--', PY, str(TOOLS / 'run_registered.py'), str(CASE)]
        (CASE / 'admission_command.json').write_text(json.dumps({'at': datetime.now().astimezone().isoformat(),
                    'command': command}, ensure_ascii=False, indent=2) + '\n')
        with (CASE / 'jobs.log').open('x') as log:
            child = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        admitted = {'at': datetime.now().astimezone().isoformat(), 'pid': child.pid, 'command': command}
        (CASE / 'launcher_pid.json').write_text(json.dumps(admitted, ensure_ascii=False, indent=2) + '\n')
        pending = json.loads((R / 'pending_01.json').read_text())
        pending['queue19p_claim_pid'] = child.pid
        (R / 'pending_01.json').write_text(json.dumps(pending, ensure_ascii=False, indent=2) + '\n')
        for snapshot_phase in ('heartbeat_20261010_0356', phase):
            result = {'at': datetime.now().astimezone().isoformat(), 'confirmation_at': json.loads((R / (snapshot_phase + '.json')).read_text())['at'],
                      'reported': True, 'commit': commit, 'included_in': proof}
            (R / (snapshot_phase + '_reported.json')).write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
        print(json.dumps({'claim': claim, 'admission': admitted}, ensure_ascii=False), flush=True)
except Exception as e:
    (R / (phase + '_row19p_STOP.json')).write_text(json.dumps({'at': datetime.now().astimezone().isoformat(),
                    'reason': str(e), 'model_started_by_claim_script': False}, ensure_ascii=False, indent=2) + '\n')
    raise

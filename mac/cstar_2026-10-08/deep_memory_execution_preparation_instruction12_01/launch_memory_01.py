"""最新の受け箱・完了記録・過程を確かめ、固定した受付を一回だけ作る。"""
from pathlib import Path
from datetime import datetime
import fcntl, hashlib, json, os, subprocess, sys

ROOT = Path(__file__).resolve().parent
BASE = ROOT.parent.parent
REPO = BASE/'codex_worldv4_2026-10-01/results'
PY = '/opt/homebrew/opt/python@3.12/bin/python3.12'
PHASE = sys.argv[1]
SNAPSHOT = Path(sys.argv[2]).resolve()
assert PHASE in ('preflight20_01', 'full1740_01')
sys.path[:0] = [str(BASE/'codex_sme_time_evict_2026-10-06'), str(BASE/'codex_logp_main_2026-10-06')]
from common_01 import ps, conditions
from cpu_guard_05 import cpu_reading

def git(*args):
    return subprocess.check_output(['git', *args], cwd=REPO, text=True)

with (ROOT/'launch_01.lock').open('a') as own_lock:
    fcntl.flock(own_lock, fcntl.LOCK_EX)
    with (BASE/'codex_sme_light_2026-10-04/control_writer_01.lock').open('a') as control_lock:
        fcntl.flock(control_lock, fcntl.LOCK_EX)
        at = datetime.now().astimezone()
        assert at.isoformat() < '2026-10-09T09:00:00+09:00'
        snapshot = json.loads(SNAPSHOT.read_text())
        assert 0 <= (at-datetime.fromisoformat(snapshot['at'])).total_seconds() < 180
        assert len(snapshot['instructions']) == 16 and all(x['received'] for x in snapshot['instructions']), '新しい指示を先に読む'
        assert not snapshot['eligible_mac_rows']
        assert snapshot['cpu']['own_compute_count'] == snapshot['cpu']['own_reserved_slots'] == 0
        assert not git('status', '--porcelain').strip(), '汚れた結果の作業状態。解決しない'
        git('fetch', 'origin', 'results-2026-09-27')
        git('rebase', 'origin/results-2026-09-27')
        for path in ('control/受け箱/SMEの係.md', 'control/走行の列_2026-10-08.md', 'control/受け箱/README.md'):
            assert git('show', 'origin/results-2026-09-27:'+path) == snapshot['files'][path], '最新の指示と列を読み直す'
        plan = json.loads((ROOT/'execution_plan_01.json').read_text())
        prepared = json.loads((ROOT/'preparation_01.json').read_text())
        for name, sha in plan['scripts_sha256'].items():
            assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest() == sha
        source = Path(prepared['source'])
        assert not subprocess.check_output(['git', 'status', '--porcelain'], cwd=source).strip()
        assert subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=source, text=True).strip() == prepared['source_commit']
        structure = BASE/'codex_cstar_structure_2026-10-08/full1740_01'
        complete = json.loads((structure/'complete.json').read_text())
        assert complete['passed'] and set(complete['completed']) == {'off_A', 'off_L', 'off_Cstar', 'structure_Cstar'}
        assert not (structure/'STOP.json').exists()
        rows = ps()
        previous_claim = json.loads((structure/'claim.json').read_text())['pid']
        assert previous_claim not in rows or 'Z' in rows[previous_claim]['stat']
        assert not any('codex_cstar_structure_2026-10-08/run_gates_01.py' in x['command']
                       and 'Z' not in x['stat'] for x in rows.values())
        assert not any(str(ROOT/'observe_memory_01.py') in x['command'] and 'Z' not in x['stat'] for x in rows.values())
        registry = Path('/Users/tatsu-admin/jobs/registry.tsv').read_text().splitlines()[1:]
        for line in registry:
            cells = line.split('\t')
            if len(cells) >= 2 and cells[1].startswith('SME_'):
                pid = int(cells[0])
                assert pid not in rows or 'Z' in rows[pid]['stat'], '自分の別の受付が残っている'
        assert cpu_reading([])['total_compute_count'] < 8
        safe = conditions()
        assert safe['free_bytes'] >= 20*2**30 and not safe['swap_grew'] and not safe['thermal_warning']
        work = ROOT/PHASE
        assert not work.exists(), '受付・途中・完成の観測を重複しない'
        if PHASE == 'full1740_01':
            assert json.loads((ROOT/'preflight20_01/complete.json').read_text())['passed']
            check = ROOT/'full_memory_check_01.json'
            if not check.exists():
                inputs = [ROOT/'preflight20_01/finished.json',
                          BASE/'codex_cstar_structure_2026-10-08/preflight20_01/off_Cstar/finished.json',
                          BASE/'codex_cstar_structure_2026-10-08/full1740_01/off_Cstar/finished.json']
                observed, small, full = [json.loads(p.read_text())['maximum_observed_model_tree_rss_bytes'] for p in inputs]
                estimate = full + plan['bitmap_limit_bytes'] + plan['observer_margin_bytes'] + max(0, observed-small)
                value = dict(at=datetime.now().astimezone().isoformat(),
                             native_full_model_tree_peak_bytes=full, native20_model_tree_peak_bytes=small,
                             observed20_model_tree_peak_bytes=observed, bitmap_limit_bytes=plan['bitmap_limit_bytes'],
                             observer_margin_bytes=plan['observer_margin_bytes'], estimated_full_peak_bytes=estimate,
                             claim_bytes=11*2**30, fits=estimate <= 11*2**30,
                             input_sha256={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs},
                             interpretation='実測した原版の常駐へ固定した観測の控えと余裕を足した受付の見込み。厳密な常駐の上限ではない。')
                check.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n')
            assert json.loads(check.read_text())['fits'], '固定した11GBの受付へ収まる見込みがない。全長は受け付けない'
        assert datetime.now().astimezone().isoformat() < '2026-10-09T09:00:00+09:00'
        work.mkdir()
        memory = 1 if PHASE == 'preflight20_01' else 11
        command = [PY, str(Path.home()/'jobs/jobs.py'), 'run', '--owner', 'SME_deep_memory_instruction12_'+PHASE,
                   '--wait', '--mem', str(memory), '--disk-path', str(work), '--', PY, str(ROOT/'run_memory_01.py'), PHASE]
        with (work/'claim.log').open('x') as log:
            proc = subprocess.Popen(command, cwd=BASE, env=dict(os.environ, PYTHONHASHSEED='0'), stdout=log,
                                    stderr=subprocess.STDOUT, start_new_session=True)
        value = dict(at=at.isoformat(), pid=proc.pid, command=command, memory_claim_gb=memory,
                     snapshot=str(SNAPSHOT), fetched_commit=git('rev-parse', 'origin/results-2026-09-27').strip(),
                     source_commit=prepared['source_commit'], phase=PHASE, started_once=True)
        (work/'claim.json').write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n')
        pending_file = BASE/'codex_cstar_pending_2026-10-06/pending_01.json'
        pending = json.loads(pending_file.read_text())
        pending.update(state='waiting_or_running_instruction12_deep_memory',
                       structure_full_gate_done=True, structure_full_claim_pid=None,
                       deep_memory_claim_pid=proc.pid, deep_memory_phase=PHASE,
                       deep_memory_started_once=True)
        pending_file.write_text(json.dumps(pending, ensure_ascii=False, indent=2)+'\n')
        print(json.dumps(value, ensure_ascii=False), flush=True)

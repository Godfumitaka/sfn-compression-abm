"""最新の受け箱・資源の確認後に、同じ受付を一度だけ起動する。"""
from pathlib import Path
from datetime import datetime
import fcntl, hashlib, json, os, subprocess, sys

ROOT = Path(__file__).resolve().parent
BASE = ROOT.parent
PY = '/opt/homebrew/opt/python@3.12/bin/python3.12'
PHASE = sys.argv[1]
SNAPSHOT = Path(sys.argv[2]).resolve()
assert PHASE in ('preflight20_01','full1740_01')

with (ROOT/'launch_01.lock').open('a') as lock:
    fcntl.flock(lock,fcntl.LOCK_EX)
    at = datetime.now().astimezone()
    assert at.isoformat() < '2026-10-09T09:00:00+09:00'
    snapshot = json.loads(SNAPSHOT.read_text())
    assert 0 <= (at-datetime.fromisoformat(snapshot['at'])).total_seconds() < 180, '最新の確認が必要'
    assert all(x['received'] or x['held'] for x in snapshot['instructions'])
    assert len(snapshot['instructions']) == 16, '新しい指示を先に読む'
    assert not snapshot['eligible_mac_rows']
    assert snapshot['cpu']['own_compute_count'] == snapshot['cpu']['own_reserved_slots'] == 0
    assert snapshot['cpu']['total_compute_count'] < 8
    assert snapshot['resources']['free_bytes'] >= 20*2**30
    assert not snapshot['resources']['swap_grew'] and not snapshot['resources']['thermal_warning']
    assert json.loads((ROOT/'checks_01.json').read_text())['passed']
    assert json.loads((BASE/'codex_cstar_profile_2026-10-08/match_times_instruction10_01/complete.json').read_text())['passed']
    assert (BASE/'codex_cstar_pending_2026-10-06/match_timing_complete_reported_01.json').exists()
    plan = json.loads((ROOT/'gate_plan_01.json').read_text())
    for name, sha in plan['scripts_sha256'].items():
        assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest() == sha
    source = ROOT/'source'
    assert not subprocess.check_output(['git','status','--porcelain'],cwd=source).strip()
    assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=source,text=True).strip() == plan['source_commit']
    work = ROOT/PHASE
    assert not work.exists(), '途中・完了・受付済みを二重に起動しない'
    if PHASE == 'full1740_01':
        assert json.loads((ROOT/'preflight20_01/complete.json').read_text())['passed']
    memory = 1 if PHASE == 'preflight20_01' else 11
    work.mkdir()
    command = [PY,str(Path.home()/'jobs/jobs.py'),'run','--owner','SME_structure_reuse_'+PHASE,
               '--wait','--mem',str(memory),'--disk-path',str(work),'--',PY,str(ROOT/'run_gates_01.py'),PHASE]
    with (work/'claim.log').open('x') as log:
        proc = subprocess.Popen(command,cwd=BASE,env=dict(os.environ,PYTHONHASHSEED='0'),stdout=log,
                                stderr=subprocess.STDOUT,start_new_session=True)
    result = dict(at=at.isoformat(),pid=proc.pid,command=command,memory_claim_gb=memory,
                  snapshot=str(SNAPSHOT),fetched_commit=snapshot['fetched_commit'],source_commit=plan['source_commit'],
                  phase=PHASE,started_once=True)
    (work/'claim.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(result,ensure_ascii=False),flush=True)

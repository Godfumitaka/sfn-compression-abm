"""受け箱と既存の受付を再確認し、指示15の200試行を4GBで一度だけ受け付ける。"""
from pathlib import Path
from datetime import datetime
import fcntl, hashlib, json, subprocess, sys
ROOT = Path(__file__).resolve().parent
WORK = ROOT/'gates200_instruction15_01'
PENDING = ROOT.parent/'codex_cstar_pending_2026-10-06/pending_01.json'
MATCH = ROOT.parent/'codex_cstar_profile_2026-10-08/match_times_instruction10_01'
REPO = ROOT.parent/'codex_worldv4_2026-10-01/results'
LOCK = ROOT.parent/'codex_sme_light_2026-10-04/control_writer_01.lock'
snapshot = json.loads(Path(sys.argv[1]).read_text())
assert not any(not x['received'] for x in snapshot['instructions']), '未受領を先に読む'
assert any(x['header'].startswith('## 指示 15（') and x['received'] for x in snapshot['instructions'])
assert not snapshot['eligible_mac_rows']
assert snapshot['cpu']['own_compute_count'] == 0 and snapshot['cpu']['total_compute_count'] < 8
assert not (MATCH/'started.json').exists(), '個別計測が先に始まった。200試行は待つ'
assert not (MATCH/'STOP.json').exists()
safe = snapshot['resources']
assert safe['free_bytes'] >= 20*2**30 and not safe['swap_grew'] and not safe['thermal_warning']
assert datetime.now().astimezone() < datetime.fromisoformat('2026-10-09T09:00:00+09:00')
assert not WORK.exists(), '完了・途中や同じ受付を重複起動しない'
with LOCK.open('a') as lock:
    fcntl.flock(lock,fcntl.LOCK_EX)
    def git(*args): return subprocess.check_output(['git',*args],cwd=REPO,text=True)
    assert not git('status','--porcelain').strip(), '汚れた作業状態。解決しない'
    git('fetch','origin','results-2026-09-27')
    git('rebase','origin/results-2026-09-27')
    commit = git('rev-parse','origin/results-2026-09-27').strip()
    for path in ('control/受け箱/SMEの係.md','control/走行の列_2026-10-08.md'):
        assert git('show',commit+':'+path) == snapshot['files'][path], '新たな受け箱又は列を先に読む'
WORK.mkdir()
command = ['/opt/homebrew/opt/python@3.12/bin/python3.12','/Users/tatsu-admin/jobs/jobs.py','run',
           '--owner','SME_Cstar_fast200_instruction15_01','--wait','--mem','4','--disk-path',str(WORK),
           '--','/opt/homebrew/opt/python@3.12/bin/python3.12',str(ROOT/'run_gates200_instruction15_01.py')]
with (WORK/'claim.log').open('x') as log:
    proc = subprocess.Popen(command,cwd=ROOT.parent,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
claim = dict(at=datetime.now().astimezone().isoformat(),claim_pid=proc.pid,command=command,
             memory_claim_gb=4,disk_path=str(WORK),fetched_commit=commit,instruction=15)
(WORK/'claim.json').write_text(json.dumps(claim,ensure_ascii=False,indent=2)+'\n')
pending = json.loads(PENDING.read_text())
pending.update(instruction15_received=True,instruction15_small_claim_pid=proc.pid,
               instruction15_small_root=str(WORK),instruction15_small_started_once=True,
               instruction15_small_gate_done=False,fast_full_gate_done=False,
               current_priority='指示15の200試行を既存の個別計測の待機中に直列で行う。全長はデスクトップ係へ。')
PENDING.write_text(json.dumps(pending,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(claim,ensure_ascii=False))

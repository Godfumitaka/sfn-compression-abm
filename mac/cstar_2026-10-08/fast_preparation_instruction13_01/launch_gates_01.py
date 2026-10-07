"""個別計測と集計が済んだ後、指定の関門を一度だけ受付へ入れる。"""
from pathlib import Path
from datetime import datetime
import json, subprocess, sys
ROOT = Path(__file__).resolve().parent
WORK = ROOT/'gates_01'
PROFILE = ROOT.parent/'codex_cstar_profile_2026-10-08'
PENDING = ROOT.parent/'codex_cstar_pending_2026-10-06/pending_01.json'
snapshot = json.loads(Path(sys.argv[1]).read_text())
assert not any(not x['received'] for x in snapshot['instructions']), '未受領の指示を先に読む'
assert not snapshot['eligible_mac_rows'], '取得可能な列を先に確認する'
assert snapshot['cpu']['own_reserved_slots'] == 0, '自分の計測の既存の受付が先'
assert snapshot['cpu']['total_compute_count'] < 8
safe = snapshot['resources']
assert safe['free_bytes'] >= 20*2**30 and not safe['swap_grew'] and not safe['thermal_warning']
assert datetime.now().astimezone().isoformat() < '2026-10-09T09:00:00+09:00'
assert json.loads((PROFILE/'match_times_instruction10_01/complete.json').read_text())['passed']
assert (PROFILE/'match_times_instruction10_01/full1740_01/analysis.json').exists()
assert not WORK.exists(), '同じ受付や途中の関門を重複起動しない'
WORK.mkdir()
command = ['/opt/homebrew/opt/python@3.12/bin/python3.12','/Users/tatsu-admin/jobs/jobs.py','run',
           '--owner','SME_Cstar_fast_gates_instruction13_01','--wait','--mem','11','--disk-path',str(WORK),
           '--','/opt/homebrew/opt/python@3.12/bin/python3.12',str(ROOT/'run_gates_01.py')]
with (WORK/'claim.log').open('x') as log:
    proc = subprocess.Popen(command,cwd=ROOT.parent,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
claim = dict(at=datetime.now().astimezone().isoformat(),claim_pid=proc.pid,command=command,
             memory_claim_gb=11,disk_path=str(WORK),fetched_commit=snapshot['fetched_commit'])
(WORK/'claim.json').write_text(json.dumps(claim,ensure_ascii=False,indent=2)+'\n')
pending = json.loads(PENDING.read_text())
pending.update(state='waiting_or_running_instruction13_fast_gates',fast_gate_claim_pid=proc.pid,
               fast_gate_root=str(WORK),fast_gate_source=json.loads((ROOT/'gate_plan_01.json').read_text())['source_commit'],
               fast_gate_started_once=True,fast_full_gate_done=False)
PENDING.write_text(json.dumps(pending,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(claim,ensure_ascii=False))

"""指示10・11の受付を一度だけ作る。受付の拒否・待機はjobs.pyに任せる。"""
from pathlib import Path
from datetime import datetime
import json, subprocess, sys
ROOT=Path(__file__).resolve().parent
CASE=ROOT/'match_times_instruction10_01'
PENDING=ROOT.parent/'codex_cstar_pending_2026-10-06/pending_01.json'
snapshot=json.loads(Path(sys.argv[1]).read_text())
assert not any(not x['received'] for x in snapshot['instructions'])
assert not snapshot['eligible_mac_rows'], '優先する取得可能行があれば読み直す'
assert snapshot['resources']['free_bytes']>=20*2**30
assert snapshot['cpu']['total_compute_count']<8
assert not snapshot['resources']['swap_grew'] and not snapshot['resources']['thermal_warning']
assert datetime.now().astimezone().isoformat()<'2026-10-09T09:00:00+09:00'
assert json.loads((ROOT/'complete.json').read_text())['passed']
assert json.loads((ROOT/'profile1740_01/analysis.json').read_text())['passed']
assert not CASE.exists(), '既存の受付・途中・完成を二重に始めない'
CASE.mkdir()
command=['/opt/homebrew/opt/python@3.12/bin/python3.12', '/Users/tatsu-admin/jobs/jobs.py', 'run',
         '--owner','SME_Cstar_matchtime_instruction10_01','--wait','--mem','11','--disk-path',str(CASE),
         '--','/opt/homebrew/opt/python@3.12/bin/python3.12',str(ROOT/'run_match_timing_01.py')]
with (CASE/'claim.log').open('x') as log:
    proc=subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT,cwd=ROOT.parent,start_new_session=True)
claim=dict(at=datetime.now().astimezone().isoformat(),claim_pid=proc.pid,command=command,memory_claim_gb=11,
           disk_path=str(CASE),receipt='受付の可否はclaim.logとstarted.jsonで区別する',
           fetched_commit=snapshot['fetched_commit'])
(CASE/'claim.json').write_text(json.dumps(claim,ensure_ascii=False,indent=2)+'\n')
v=json.loads(PENDING.read_text())
v.update(state='waiting_or_running_instruction10_match_timing', profile_analysis_done=True,
         profile_full_gate_done=True, profile_complete_report=json.loads((ROOT/'reported_profile_complete_01.json').read_text()),
         match_timing_claim_pid=proc.pid, match_timing_root=str(CASE), match_timing_started_once=True,
         match_timing_full_gate_done=False, match_timing_analysis_done=False,
         current_priority='指示10・11の照合ごとの時間の計測。指示12のコードの点検を並行。')
PENDING.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(claim,ensure_ascii=False))

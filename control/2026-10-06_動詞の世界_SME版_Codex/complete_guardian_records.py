"""終了済みの監督の原本から待機秒を確定する。プロセスの操作はしない。"""
from pathlib import Path
import json

root=Path(__file__).resolve().parent
folder=root/'pilot_A_global_s01'
assert json.loads((root/'status.json').read_text())['state']=='pilot_complete'
assert not (folder/'guardian_complete.json').exists()
attachment=json.loads((folder/'guardian_attachment.json').read_text())
old=[json.loads(x) for x in (folder/'resources_original_supervisor.jsonl').read_text().splitlines()]
new=[json.loads(x) for x in (folder/'resources_guardian.jsonl').read_text().splitlines()]
assert new[-1]['event']=='guardian_model_finished'
rows=[r for r in old if r.get('epoch_seconds',r.get('finished_epoch',float('inf')))<=attachment['attached_epoch']]+new
start=None;paused_seconds=0
for row in rows:
    if row['event']=='paused':
        assert start is None
        start=row['epoch_seconds']
    elif row['event']=='resumed':
        assert start is not None
        paused_seconds+=row['epoch_seconds']-start;start=None
assert start is None
result=json.loads((folder/'result.json').read_text())
assert result['exit_code']==0
result['paused_seconds_original_supervisor']=result['paused_seconds']
result['paused_seconds']=paused_seconds
result['model_process_group_unchanged']=attachment['model_process_group_unchanged']
result['model_worker_pid_unchanged']=attachment['model_worker_pid_unchanged']
result['cpu_guardian_attachment_epoch']=attachment['attached_epoch']
result['guardian_finalization_repaired']='終了行の時刻はfinished_epoch。原本を残し、epoch_secondsが無い行を境界後として除いた。'
(folder/'resources.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows))
(folder/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
(folder/'guardian_complete.json').write_text(json.dumps({'completed':True,'paused_seconds':paused_seconds,'exit_code':0,'finalization_repaired':True})+'\n')
print(json.dumps(result,ensure_ascii=False))

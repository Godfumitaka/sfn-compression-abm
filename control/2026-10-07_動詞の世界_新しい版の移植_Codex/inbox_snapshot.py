"""受け箱確認用の小さい状態記録。模型や受付は変更しない。"""
import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
import subprocess
import tomllib

p=argparse.ArgumentParser()
p.add_argument('--workspace',type=Path,required=True)
p.add_argument('--output',type=Path,required=True)
a=p.parse_args()
repo=a.workspace/'codex_verb_2026-10-04/report-results'
source=a.workspace/'codex_verb_2026-10-04/sme_2026-10-06/source'
raw=subprocess.check_output(['ps','-axo','pid,ppid,stat,rss,command'],text=True)
rows={}
for line in raw.splitlines()[1:]:
    v=line.split(None,4)
    if len(v)==5:
        rows[int(v[0])]={'pid':int(v[0]),'ppid':int(v[1]),'state':v[2],
                         'rss_bytes':int(v[3])*1024,'command':v[4]}
models=[];other_spawn=[];paused=[]
for row in rows.values():
    executable=row['command'].split(None,1)[0]
    if 'python' not in Path(executable).name.lower() or 'spawn_main' not in row['command']:
        continue
    parent=rows.get(row['ppid'],{})
    argv=parent.get('command','').split()
    # v3_runや計測用の観察過程の子を模型として数える。jobsの命令文に
    # 同じ文字があっても、実際の模型の親とはみなさない。
    model=any(Path(arg).name in {'v3_run.py','observe_02.py','observe_memory_02.py','observe_04.py'} for arg in argv[1:3])
    item={**row,'parent_command':parent.get('command')}
    if 'T' in row['state'] or 'Z' in row['state']:
        paused.append(item)
    elif model:
        models.append(item)
    else:
        other_spawn.append(item)
auto=tomllib.loads((Path.home()/'.codex/automations/automation/automation.toml').read_text())
assert auto['name']=='動詞の世界・受け箱と移植の継続確認'
assert auto['rrule']=='FREQ=MINUTELY;INTERVAL=30;UNTIL=20261009T000000Z'
docs=['control/受け箱/動詞の世界の係.md','control/受け箱/README.md',
      'control/走行の列_2026-10-08.md','control/2026-10-06_渡す委任書_Claude.md',
      'control/2026-10-06_GPTの返事_照合と分布の統一.md',
      'control/2026-10-06_GPTの返事_四つの判断.md',
      'control/2026-10-07_走行の計画_案_Claude.md',
      'control/2026-10-07_C星の照合とディリクレ_実装_Codex.md',
      'control/2026-10-07_注意の第二段_実装_Codex2.md',
      'control/2026-10-06_動詞の世界_SME版_Codex/port.patch']
hashes=[]
for rel in docs:
    data=(repo/rel).read_bytes()
    hashes.append({'path':rel,'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()})
for rel in ['tools/v3_run.py','tools/verbworld.py','tools/probeworld.py',
            'tools/verb/analyze.py','tools/verb/replay_state.py','tools/verbtiming.py']:
    data=(source/rel).read_bytes()
    hashes.append({'path':'$WORKSPACE/codex_verb_2026-10-04/sme_2026-10-06/source/'+rel,
                   'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()})
eligible=[]
for line in (repo/'control/走行の列_2026-10-08.md').read_text().splitlines():
    fields=[v.strip() for v in line.split('|')[1:-1]]
    if len(fields)==9 and fields[8]=='未着手' and fields[6] in {'マック','どちらでも'} and fields[7] and not fields[7].startswith('（'):
        eligible.append({'row':fields[0],'machine':fields[6],'version_flags_output':fields[7]})
data={'checked_at':datetime.now().astimezone().isoformat(timespec='seconds'),
      'report_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip(),
      'source_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=source,text=True).strip(),
      'model_process_count':len(models),'model_processes':models,
      'other_active_spawn_workers':other_spawn,'paused_or_zombie_spawn_workers':paused,
      'own_model_process_count':sum(str(a.workspace/'codex_verb_2026-10-04') in m['parent_command'] for m in models),
      'eligible_mac_queue_rows':eligible,
      'counting_rule':'実際のv3_run/計測観察過程のspawn workerを一個体一回。親の監督とSTAT T/Zは稼働数へ加えない。受付のメモリ予約は変えない。',
      'automation':{'id':auto['id'],'status':auto['status'],'target_thread_id':auto['target_thread_id'],
                    'created_at_jst':datetime.fromtimestamp(auto['created_at']/1000).astimezone().isoformat(timespec='milliseconds'),
                    'interval_minutes':30,'expires_at_jst':'2026-10-09T09:00:00+09:00',
                    'expiry_saved_verified':True},'inputs':hashes}
text=json.dumps(data,ensure_ascii=False,indent=2)
text=text.replace(str(a.workspace),'$WORKSPACE').replace(str(Path.home()),'$USER_HOME')
a.output.parent.mkdir(parents=True,exist_ok=True)
a.output.write_text(text+'\n')
print(json.dumps({'checked_at':data['checked_at'],'models':len(models),'other_active_spawn':len(other_spawn),
                  'automation':data['automation']},ensure_ascii=False))

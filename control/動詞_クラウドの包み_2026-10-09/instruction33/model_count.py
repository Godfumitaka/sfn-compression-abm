"""受け箱確認用の小さい状態記録。模型や受付は変更しない。"""
import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
import subprocess
import tomllib

MODEL_HOSTS={'v3_run.py','observe_02.py','observe_memory_02.py','observe_04.py',
             'sme_evict_observe_20261007.py','uposition_run.py','selcands_sme.py',
             'material_keep_driver_01.py','observe_cstar_01.py','observe_off.py','observe_on.py','observe.py','observe_match_times_01.py','observe_cpu_01.py','observe_light.py','observe_memory_01.py','gate_driver.py','measurement_driver.py'}

def script_name(command):
    # psは空白を含むscriptのパスをquoteしない。split()[1]では判定しない。
    head=command.split(None,1)
    if len(head)!=2 or 'python' not in Path(head[0]).name.lower():
        return None
    match=re.match(r'(.+?\.py)(?:\s|$)',head[1])
    return Path(match[1]).name if match else None

def count_models(rows):
    models=[];other_spawn=[];paused=[];paused_models=[]
    for row in rows.values():
        head=row['command'].split(None,1)
        if not head or 'python' not in Path(head[0]).name.lower():
            continue
        parent=rows.get(row['ppid'],{})
        parent_script=script_name(parent.get('command',''))
        spawn='spawn_main' in row['command']
        # 同じ命令を継承したforkの個体を数える。親のtime・監督は除く。
        fork=(script_name(row['command']) in MODEL_HOSTS
              and parent_script==script_name(row['command'])
              and parent.get('command')==row['command'])
        model=(spawn and parent_script in MODEL_HOSTS) or fork
        if not model and not spawn:
            continue
        item={**row,'parent_command':parent.get('command'),
              'worker_kind':'fork' if fork else 'spawn'}
        if 'T' in row['state'] or 'Z' in row['state']:
            paused.append(item)
            if model:
                paused_models.append(item)
        elif model:
            models.append(item)
        else:
            other_spawn.append(item)
    return models,other_spawn,paused,paused_models

def queue_rows(text):
    # 各tableの見出しから列を引く。8列・旧9列とも同じ入口。
    eligible=[];headers=None
    for line in text.splitlines():
        if not line.strip().startswith('|'):
            headers=None
            continue
        fields=[v.strip() for v in line.split('|')[1:-1]]
        if all(name in fields for name in ('機械','版・旗・出力先','状態')):
            headers=fields
            continue
        if headers is None or len(headers)!=len(fields):
            continue
        item=dict(zip(headers,fields))
        value=item['版・旗・出力先']
        if (item['状態']=='未着手' and item['機械'] in {'マック','Mac','どちらでも'}
            and value and not value.startswith(('（','未定'))):
            eligible.append({'row':item.get('#'),'machine':item['機械'],
                             'version_flags_output':value})
    return eligible

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--workspace',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    snapshot(a)

def snapshot(a):
    repo=a.workspace/'codex_verb_2026-10-04/report-results'
    source=a.workspace/'codex_verb_2026-10-04/sme_2026-10-06/source'
    raw=subprocess.check_output(['ps','-axo','pid,ppid,stat,rss,command'],text=True)
    rows={}
    for line in raw.splitlines()[1:]:
        v=line.split(None,4)
        if len(v)==5:
            rows[int(v[0])]={'pid':int(v[0]),'ppid':int(v[1]),'state':v[2],
                             'rss_bytes':int(v[3])*1024,'command':v[4]}
    models,other_spawn,paused,paused_models=count_models(rows)
    auto=tomllib.loads((Path.home()/'.codex/automations/automation/automation.toml').read_text())
    assert auto['name']=='動詞の世界・受け箱と移植の継続確認'
    assert auto['rrule']=='FREQ=MINUTELY;INTERVAL=30;UNTIL=20261013T000000Z'
    docs=['control/受け箱/動詞の世界の係.md','control/受け箱/README.md',
          'control/走行の列_2026-10-08.md','control/2026-10-06_渡す委任書_Claude.md',
          'control/2026-10-06_GPTの返事_照合と分布の統一.md',
          'control/2026-10-06_GPTの返事_四つの判断.md',
          'control/2026-10-07_走行の計画_案_Claude.md',
          'control/2026-10-07_C星の照合とディリクレ_実装_Codex.md',
          'control/2026-10-07_注意の第二段_実装_Codex2.md',
          'control/2026-10-06_SMEの一本の時間の内訳_Codex.md',
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
    eligible=queue_rows((repo/'control/走行の列_2026-10-08.md').read_text())
    data={'checked_at':datetime.now().astimezone().isoformat(timespec='seconds'),
          'report_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip(),
          'source_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=source,text=True).strip(),
          'model_process_count':len(models),'model_processes':models,
          'other_active_spawn_workers':other_spawn,'paused_or_zombie_spawn_workers':paused,
          'paused_or_zombie_model_workers':paused_models,
          'own_model_process_count':sum(str(a.workspace/'codex_verb_2026-10-04') in m['parent_command'] for m in models),
          'eligible_mac_queue_rows':eligible,
          'counting_rule':'実際のv3_run/計測観察過程、material_keep_driver_01のv3_run起動とselcands_smeの模型予測再生のspawnとforkの個体workerを一個体一回。RSSやCPU%を足切りにしない。親の監督・time・resource_trackerとSTAT T/Zは稼働数へ加えない。停止模型は別欄、受付のメモリ予約は変えない。未知のspawnは別欄で要確認。列の候補は実行前に版・旗・出力先と合格を本文で確かめる。',
          'automation':{'id':auto['id'],'status':auto['status'],'target_thread_id':auto['target_thread_id'],
                        'created_at_jst':datetime.fromtimestamp(auto['created_at']/1000).astimezone().isoformat(timespec='milliseconds'),
                        'interval_minutes':30,'expires_at_jst':'2026-10-13T09:00:00+09:00',
                        'expiry_saved_verified':True},'inputs':hashes}
    text=json.dumps(data,ensure_ascii=False,indent=2)
    text=text.replace(str(a.workspace),'$WORKSPACE').replace(str(Path.home()),'$USER_HOME')
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(text+'\n')
    print(json.dumps({'checked_at':data['checked_at'],'models':len(models),'other_active_spawn':len(other_spawn),
                      'automation':data['automation']},ensure_ascii=False))

if __name__=='__main__':
    main()

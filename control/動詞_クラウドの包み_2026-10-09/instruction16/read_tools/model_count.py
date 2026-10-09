"""Macの既存の個体workerの数え方を、そのままクラウドでも使う。"""
from pathlib import Path
import re

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


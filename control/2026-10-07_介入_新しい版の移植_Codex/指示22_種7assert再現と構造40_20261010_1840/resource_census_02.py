"""実模型と、原字節・状態で確認した構造受付待ち親を分ける。"""
from pathlib import Path
import hashlib,json
from resource_census_01 import census as native_census
WAIT_SOURCE=Path('/Users/tatsu-admin/Documents/ChatGPT/New project/codex_verb_2026-10-04/newport_2026-10-07/instruction35/wait_for_structural_resources_once.py')
WAIT_STATE=Path('/Users/tatsu-admin/Documents/ChatGPT/New project/codex_verb_2026-10-04/newport_2026-10-07/instruction35/structural_resource_waiter_status.json')
WAIT_SOURCE_SHA='6518d5fa99a379a97a0f7b20c9f5124d381b15e479bd45c410248a257717e117'

def census():
    rows,active,paused=native_census()
    if WAIT_SOURCE.exists() and WAIT_STATE.exists() and hashlib.sha256(WAIT_SOURCE.read_bytes()).hexdigest()==WAIT_SOURCE_SHA:
        state=json.loads(WAIT_STATE.read_text())
        pid=state.get('pid')
        if (pid in active|paused and str(WAIT_SOURCE) in rows[pid]['command']
            and state.get('state')=='waiting_for_recorded_birth_children_and_B6_worker_to_exit'
            and state.get('model_starts')==0):
            active.discard(pid);paused.discard(pid)
    return rows,active,paused

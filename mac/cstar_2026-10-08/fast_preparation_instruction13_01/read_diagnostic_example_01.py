"""済んだ種1の保存記録から、旧照合の診断が保存状態にもある小例を読む。"""
from pathlib import Path
from datetime import datetime
import gzip,hashlib,json
ROOT = Path(__file__).resolve().parent
OUT = ROOT/'diagnostic_saved_state_example_01.json'
assert not OUT.exists(), '同じ読み取りを繰り返さない'
source = ROOT.parent/'codex_cstar_2026-10-07/native_preflight_02/on_own/output'
paths = list((source/'side').glob('*/seed001.sme.states.jsonl.gz'))
assert len(paths) == 1
def find(value,path='$'):
    if isinstance(value,dict):
        if value.get('module') == 'smeshared' and value.get('name') == 'SharedAlignment':
            return value,path
        for key,child in value.items():
            found = find(child,path+'/'+str(key))
            if found: return found
    elif isinstance(value,list):
        for i,child in enumerate(value):
            found = find(child,path+'/'+str(i))
            if found: return found
    return None
with gzip.open(paths[0],'rt',encoding='utf-8') as stream:
    for line_number,line in enumerate(stream,1):
        value = json.loads(line)
        found = find(value)
        if not found: continue
        alignment,path = found
        items = alignment['fields']['sme_audit']['items']
        names = ('old_selected_score','old_entity_mapping','old_relation_mapping')
        old = {key:child for key,child in items if key in names}
        assert set(old) == set(names)
        before = (json.dumps(value,ensure_ascii=False)+'\n').encode()
        alignment['fields']['sme_audit']['items'] = [x for x in items if x[0] not in names]
        after = (json.dumps(value,ensure_ascii=False)+'\n').encode()
        assert before != after
        result = dict(at=datetime.now().astimezone().isoformat(), source=str(paths[0]),
                      line=line_number,trial=value['trial'],kind=value['kind'],alignment_path=path,
                      old_fields=old,original_record_bytes=len(before),
                      diagnostic_omission_record_bytes=len(after),
                      original_record_sha256=hashlib.sha256(before).hexdigest(),
                      diagnostic_omission_record_sha256=hashlib.sha256(after).hexdigest(),
                      omission_changes_saved_state=True,examples=1,model_not_run=True,
                      model_files_not_modified=True,note='メモリ内だけで3欄を除いて確かめる。原ファイルを書き換えず、大きい状態を複製しない。')
        OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
        print(json.dumps({k:result[k] for k in ('line','trial','kind','alignment_path','examples','omission_changes_saved_state')},ensure_ascii=False))
        break
    else:
        raise AssertionError('保存されたSharedAlignmentの小例が見つからない')

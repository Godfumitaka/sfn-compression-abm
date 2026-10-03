"""保存済み状態の全スナップショットを読取り、旧記録を変更せず指紋を別に保存する。"""
from pathlib import Path
import gzip, hashlib, json, sys, time

root=Path(__file__).resolve().parent
sys.path.insert(0,str(root/'source/tools'))
sys.path.insert(0,str(root/'source/tools/v311c_checks'))
sys.path.insert(0,str(root/'source'))
from v311c_fingerprint import fingerprint, VERSION
from abm.loop import _apply
import coll8_gate as gate

ev=root/'evidence'
dest=ev/'canonical-saved-v1'
dest.mkdir(exist_ok=False)
health,_=gate.health()
gate.save(ev/'canonical-recheck-initial-machine.json',health)
if len(health['foreign_heavy'])+1>4:
    raise RuntimeError('保存記録の再検査も機械の上限で停止')
started=time.monotonic()
last=started
files=[]
unknown_names=set()
dictionary=set(json.loads((root/'source/tools/shop/U-011_seed_shop.json').read_text())['marginal'])
import shopworld
dictionary.update(shopworld.NEW_PREDICATES)
def status():
    gate.save(ev/'canonical-saved-recheck.json',{'fingerprint_version':VERSION,
       'scope':'保存された台帳スナップショット。元の全型・列順の模型状態とは区別する',
       'status':'reading','files':files,'rows_checked':sum(f['rows_checked'] for f in files),
       'runtime_state_hashes_recomputable':False,'original_records_modified':False,
       'unknown_slot_history_names':sorted(unknown_names),'elapsed_seconds':time.monotonic()-started})

for p in sorted((root/'outputs').rglob('*.jsonl.gz')):
    if 'ledgers' not in p.parts or 'cells' not in p.parts:continue
    relative=p.relative_to(root/'outputs')
    target=dest/(str(relative).replace('/','__')+'.fingerprints.jsonl.gz')
    digest=hashlib.sha256(); n=0; snapshot=None; error=None
    try:
        with gzip.open(p,'rt') as inp, gzip.open(target,'wt') as out:
            header=json.loads(next(inp))
            for line in inp:
                r=json.loads(line)
                snap=r.get('state_snapshot')
                if not isinstance(snap,dict):
                    raise ValueError('状態スナップショットが無い')
                if snap['kind']=='full':snapshot=snap['value']
                elif snap['kind']=='delta':
                    if snapshot is None:raise ValueError('差分の土台が無い')
                    snapshot=_apply(snapshot,snap['changes'])
                else:raise ValueError('未対応の状態記録方式: '+snap['kind'])
                for history in snapshot.get('slot_history',{}).values():
                    unknown_names.update(set(history)-dictionary)
                result={'trial':r['timestamp'] if 'trial' not in r else r['trial'],
                        'agent':r['agent_id'],'stored_snapshot_fingerprint':fingerprint(snapshot)}
                encoded=json.dumps(result,ensure_ascii=False,separators=(',',':'))+'\n'
                out.write(encoded);digest.update(encoded.encode());n+=1
                current=time.monotonic()
                if current-last>10:
                    h,_=gate.health()
                    if len(h['foreign_heavy'])+1>4:
                        raise RuntimeError('機械の並列上限で保存記録の読取りを停止')
                    gate.save(ev/'canonical-recheck-latest-machine.json',h)
                    last=current
    except (EOFError, gzip.BadGzipFile) as exc:
        error=type(exc).__name__+': '+str(exc)
    files.append({'path':str(p),'recorded_fingerprints':str(target),
        'rows_checked':n,'fingerprints_sha256':digest.hexdigest(),'compressed_file_complete':error is None,
        'incomplete_reason':error})
    status()
    print(relative,n,error,flush=True)

legacy=[]
for p in sorted((root/'outputs').rglob('*.state.jsonl')):
    n=0
    for line in p.open():
        row=json.loads(line)
        if not {'t','agent','state','rng'} <= set(row):raise ValueError('旧監査の欄が不一致')
        n+=1
    legacy.append({'path':str(p),'rows':n,'full_state_available':False,
        'status':'旧SHA256だけから集合の順を正規化して再計算することはできない'})
data=json.loads((ev/'canonical-saved-recheck.json').read_text())
data.update(status='completed_available_records',legacy_runtime_fingerprint_files=legacy,
    legacy_runtime_rows=sum(r['rows'] for r in legacy),elapsed_seconds=time.monotonic()-started,
    full_runtime_fingerprint_recheck_complete=False)
gate.save(ev/'canonical-saved-recheck.json',data)
print('保存台帳の状態',data['rows_checked'],'旧監査ハッシュ',data['legacy_runtime_rows'],flush=True)

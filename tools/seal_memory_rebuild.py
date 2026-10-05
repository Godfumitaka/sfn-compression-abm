"""旧い照合の記憶を作り、公開された本体hashと11列表の両方で停止を判定する。"""
from pathlib import Path
import argparse,gzip,hashlib,json,subprocess,sys
import sealrestore as sr

BASE='3380344add7f85ce2c3608656de5805995dcf971'
WORK=Path(__file__).resolve().parents[2]
PUBLIC=Path('/Users/tatsu-admin/v33prod/results/ataru-0608')
REPORT=WORK/'github_report'
ARMS=('f_grid/fg_f050_C_L50','f_grid/fg_f050_A_L50','lambda_grid/lg_w2_A_lam0.065',
      'chance/ch_w2_A_uabs','n3_lambda/n3l_w2_A_lam0.0187',
      'n3/n3_w1_C_L50','n3/n3_w2_C_L50','n3/n3_w1_D_t04','n3/n3_w2_D_t04')

def file_hash(path):
    h=hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()

def input_fingerprints(root,seed,cell):
    paths=[root/'flag.json',root/'ledgers/cells'/cell/f'seed{seed:03d}.jsonl.gz',
           root/'ledgers/cells'/cell/f'seed{seed:03d}.done',*sorted((root/'side'/cell).glob(f'seed{seed:03d}.*'))]
    return {str(p):{'bytes':p.stat().st_size,'sha256':file_hash(p)} for p in paths}

def gate_passed(result,mac_rebuild):
    return result['table_match'] and (result.get('internal_state_match',False) if mac_rebuild else result['body_hash_match'])


def public_proof(relative):
    proofs={}
    for name in ('flag.json','sha256.jsonl','trials.tsv.gz'):
        path='ataru-0608/'+relative+'/'+name
        listing=subprocess.check_output(['git','ls-tree','origin/results-2026-09-27','--',path],cwd=REPORT,text=True).strip()
        if not listing:raise ValueError('公開枝に参照が無い：'+path)
        blob=listing.split()[2]
        local=subprocess.check_output(['git','hash-object',str(PUBLIC/relative/name)],cwd=REPORT,text=True).strip()
        if blob!=local:raise ValueError('ローカル参照が公開枝と一致しない：'+path)
        proofs[name]=blob
    return proofs


def reference_hash(root,seed):
    with (root/'sha256.jsonl').open() as stream:
        for raw in stream:
            record=json.loads(raw)
            if record['seed']==seed:return record
            if record['seed']>=20:break
    raise ValueError('指定の種の参照hashが無い')


def table_rows(root,seed):
    rows=[]
    with gzip.open(root/'trials.tsv.gz','rb') as stream:
        header=stream.readline();assert len(header.rstrip().split(b'\t'))==11
        while True:
            prefix=b''
            while True:
                ch=stream.read(1)
                if not ch or ch==b'\t':break
                prefix+=ch
            if not ch:break
            n=int(prefix)
            # 次の種の欄を読まずに止め、21〜40の行を読み込まない。
            if n>seed or n>20:break
            raw=prefix+b'\t'+stream.readline()
            if n==seed:rows.append(raw)
    return header,rows


def verify(root,seed,reference,*,internal=False):
    from abm.loop import _apply,_json_bytes
    hashes=reference_hash(reference,seed);header,expected=table_rows(reference,seed)
    cell=hashes['cell'];side=root/'side'/cell;bits={}
    with (side/f'seed{seed:03d}.jsonl').open() as stream:
        for raw in stream:
            rec=json.loads(raw)
            if rec.get('kind')=='v39':bits[rec['trial']]=(rec['bits_after'],rec['defs'])
    body=hashlib.sha256();rows=[];snapshots={};state=None;state_checks=0
    with gzip.open(root/'ledgers/cells'/cell/f'seed{seed:03d}.jsonl.gz','rb') as stream:
        meta=json.loads(next(stream));assert meta['run_seed']==seed and meta['code_commit']==BASE
        for raw in stream:
            body.update(raw);r=json.loads(raw);t=r['prediction_order']
            assert t==len(rows)
            snapshots[r['state_snapshot']['kind']]=snapshots.get(r['state_snapshot']['kind'],0)+1
            if internal:
                snapshot=r['state_snapshot']
                state=snapshot['value'] if snapshot['kind']=='full' else _apply(state,snapshot['changes'])
                if hashlib.sha256(_json_bytes(state)).hexdigest()!=r['agent_state_snapshot_hash']:
                    raise RuntimeError(f'台帳内部の状態指紋が不一致：種{seed}・試行{t}')
                state_checks+=1
            outcome='a' if r['prediction_kind']=='Abstain' else 'c' if r['hit']==1 else 'w'
            bit_count,defs=bits.get(t,('',''))
            values=(seed,t,int(bool(r['f_fired'])),outcome,r.get('abstain_reason') or '',int(bool(r.get('held_out_is_door'))),
                    r.get('shop_type',''),r.get('shop_cue',''),r.get('door_pred',''),bit_count,defs)
            rows.append(('\t'.join(map(str,values))+'\n').encode())
    assert snapshots.get('full')==1 and snapshots.get('delta',0)==len(rows)-1
    differences=sum(a!=b for a,b in zip(rows,expected))+abs(len(rows)-len(expected))
    data={'seed':seed,'trials':len(rows),'body_sha256':body.hexdigest(),'reference_body_sha256':hashes['body_sha256'],
          'body_hash_match':body.hexdigest()==hashes['body_sha256'],'different_table_rows':differences,
          'table_match':rows==expected,'table_sha256':hashlib.sha256(header+b''.join(rows)).hexdigest(),
          'reference_table_sha256':hashlib.sha256(header+b''.join(expected)).hexdigest()}
    if internal:
        data.update(internal_state_trials=state_checks,internal_state_match=state_checks==len(rows),
                    original_body_status='未照合',material_label='マックでの作り直し（試行表は元と一致、台帳本体は未照合）')
    return data


def one(relative,seed,dest,*,mac_rebuild=False):
    if seed not in range(1,21):raise ValueError('種は1〜20だけ')
    reference=PUBLIC/relative;proof=public_proof(relative);fl=json.loads((reference/'flag.json').read_text())
    hashes=reference_hash(reference,seed);dest.mkdir(parents=True,exist_ok=True)
    task,cfg=sr.make_task(str(reference),hashes['cell'],seed,str(dest))
    task['code_commit']=BASE
    if not (dest/'ledgers/cells'/hashes['cell']/f'seed{seed:03d}.done').exists():
        import v3_run
        v3_run.worker(task)
    fl.update(commit=BASE,workers=1)
    flag_path=dest/'flag.json'
    if not flag_path.exists():flag_path.write_text(json.dumps(fl,ensure_ascii=False)+'\n')
    elif json.loads(flag_path.read_text())!=fl:raise RuntimeError('既存材料の旗が公開旗から構成した旗と異なる')
    result=verify(dest,seed,reference,internal=mac_rebuild);result.update(arm=relative,public_git_blobs=proof)
    if mac_rebuild:result['input_fingerprints']=input_fingerprints(dest,seed,hashes['cell'])
    suffix='mac_gate' if mac_rebuild else 'comparison'
    (dest/f'seed{seed:03d}.{suffix}.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(result,ensure_ascii=False),flush=True)
    passed=gate_passed(result,mac_rebuild)
    if not passed:raise SystemExit(3)


if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('arm',choices=ARMS);ap.add_argument('dest',type=Path)
    ap.add_argument('--seed',required=True,type=int)
    ap.add_argument('--mac-rebuild',action='store_true',help='公開11列表と台帳内部の全試行指紋を関門とする承認済み再作成')
    a=ap.parse_args();one(a.arm,a.seed,a.dest.resolve(),mac_rebuild=a.mac_rebuild)

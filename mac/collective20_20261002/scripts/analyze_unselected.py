"""予測前の記憶に例外由来の受信先が残り、選ばれなかった誤答を数える。入力を編集しない。"""
from collections import Counter
import gzip, hashlib, json, sys
from pathlib import Path

ROOT=Path(__file__).resolve().parent
sys.path[:0]=[str(ROOT/'source'),str(ROOT/'source/tools')]
from abm.loop import _apply, _json_bytes

def one(run, counted):
    comm=[json.loads(line) for line in (run/'comm'/f"run{counted['group_seed']:03d}.jsonl").read_text().splitlines()]
    summary=next(r for r in comm if r['kind']=='summary')
    receipts=counted['exception_receipts']
    C=Counter()
    errors=[]
    for agent,meta in enumerate(summary['agents']):
        by_t={}
        for r in receipts:
            if r['recipient']==agent and r['incorporated']:
                by_t.setdefault(r['t'],[]).append(r)
        pre=None
        pre_hash=None
        seen={}
        path=run/'ledgers/cells'/meta['cell']/f"seed{meta['seed']:03d}.jsonl.gz"
        with gzip.open(path,'rt') as f:
            next(f)
            for line in f:
                row=json.loads(line)
                t=row['prediction_order']
                # 世界の予測は、その試行の世界の学びと受信より先。前試行の末尾に受信済み。
                for r in by_t.get(t-1,[]):
                    key=(r['R'],r['R_born'])
                    seen.setdefault(key,[]).append({'t':r['t'],'sender':r['sender'],'bundle':r['bundle']})
                if row['coverage']==1 and row['hit']!=1:
                    C['誤答']+=1
                    C['例外ドアの誤答']+=bool(row['held_out_is_door'] and row['shop_cue']=='e')
                    C['例外由来を取り込んだ後の誤答']+=bool(seen)
                    live={R:dd['registered_at'] for R,dd in ((pre or {}).get('definitions') or {}).items()}
                    alive=[key for key in seen if live.get(key[0])==key[1]]
                    unselected=[key for key in alive if key[0]!=row.get('R_used')]
                    chosen=[key for key in alive if key[0]==row.get('R_used')]
                    C['例外由来の受信先が記憶にある誤答']+=bool(alive)
                    C['例外由来の受信先が記憶にあり未選択の誤答']+=bool(unselected)
                    C['例外由来の受信先が選ばれた誤答']+=bool(chosen)
                    if unselected:
                        C['未選択の受信先の延べ数']+=len(unselected)
                        C['例外ドアで受信先が記憶にあり未選択の誤答']+=bool(row['held_out_is_door'] and row['shop_cue']=='e')
                    errors.append({'agent':agent,'world_seed':meta['seed'],'trial':t,
                                   'shop_cue':row['shop_cue'],'held_out_is_door':row['held_out_is_door'],
                                   'selected_R':row.get('R_used'),'previous_state_hash':pre_hash,
                                   'exception_receipts_so_far':sum(len(rs) for rs in seen.values()),
                                   'exception_definitions_alive':[list(k) for k in alive],
                                   'exception_definitions_unselected':[{'R':k[0],'R_born':k[1],'receipts':seen[k]} for k in unselected]})
                ss=row['state_snapshot']
                assert ss['kind'] in ('full','delta')
                if ss['kind']=='delta': assert ss['base_hash']==pre_hash
                post=ss['value'] if ss['kind']=='full' else _apply(pre,ss['changes'])
                post_hash=hashlib.sha256(_json_bytes(post)).hexdigest()
                assert post_hash==row['agent_state_snapshot_hash'],(agent,t)
                C['状態の指紋一致']+=1
                pre,pre_hash=post,post_hash
    assert C['状態の指紋一致']==3480
    assert C['誤答']==counted['common']['数'].get('誤答',0)
    assert C['例外ドアの誤答']==counted['doors']['e'].get('誤答',0)
    return {'counts':dict(C),'errors':errors,
            'definition':'受信結果が同化/誕生で、送信元の実場面が例外の受信先。同じ名前と誕生試行で追跡。現在の正答能力は判定していない。'}

if __name__=='__main__':
    run=Path(sys.argv[1])
    counted=json.loads(Path(sys.argv[2]).read_text())
    dest=Path(sys.argv[3]);assert not dest.exists()
    dest.write_text(json.dumps(one(run,counted),ensure_ascii=False,indent=1)+'\n')

"""Cを始める前に、Aの40集団と関門・全数表の閉じた記録を確かめる。模型は動かさない。"""
from collections import Counter
from pathlib import Path
import json, subprocess

ROOT=Path(__file__).resolve().parent
EXPECTED='34667a55a4e68d7cda64614ead95e84a361b0118'

def check():
    finished=json.loads((ROOT/'finished.json').read_text())
    assert finished['complete'] and finished['populations']==40 and finished['tasks']==139200,finished
    assert not (ROOT/'failure.json').exists() and not (ROOT/'stopped.json').exists()
    gate=json.loads((ROOT/'gate_passed.json').read_text())
    assert gate['populations']==6 and gate['ledgers']==12 and len(gate['checks'])==6
    assert all(g['counts_match'] for g in gate['checks'])
    assert gate['exception_door_errors']=={'no_comm':43,'recvA':38}
    dest=ROOT.parent/'codex_worldv4_2026-10-01/results/mac/collective20_20261002'
    scope=json.loads((dest/'source_and_scope.json').read_text())
    assert scope['complete'] and scope['completed_populations']==40 and scope['source']==EXPECTED
    totals={m:Counter() for m in ('no_comm','recvA')}
    doors={m:{c:Counter() for c in ('n','e')} for m in totals}
    manifests=[];checks=[];first3=Counter()
    for seed in range(1,21):
        for mode in totals:
            name=f'pilot_w2_{mode}_g{seed:03d}'
            p=json.loads((ROOT/'analysis'/(name+'.json')).read_text())
            u=json.loads((ROOT/'analysis'/(name+'.unselected.json')).read_text())
            assert (p['world'],p['mode'],p['group_seed'])==(2,mode,seed)
            assert p['world_seeds']==[seed,seed+1000]
            assert p['common']['失敗']==0 and p['common']['数']['課題']==3480
            n=p['common']['数'];audit=p['common']['突き合わせ']
            assert n.get('正解',0)+n.get('誤答',0)+n.get('棄権',0)==3480
            assert sum(n.get('誤答_'+k,0) for k in ('F','H','U'))==n.get('誤答',0)
            assert p['prediction_bundle_mismatches']==0 and u['counts']['状態の指紋一致']==3480
            assert audit['個体の課題の和']==audit['誤答の出どころの和']==2
            assert audit['一致の四分類の和']==p['common']['probes']
            assert all(audit[k]==1 for k in ('送信＝配達','配達＝受け取りの記録','束のある試行は実際に答えた試行','一個体一試行に束は一つまで','受け取りで束を送らない'))
            assert all(n.get('STATS_'+k,0)==0 for k in ('recv_score_changed','recv_merit_changed','dC_mismatch'))
            argv=json.loads((ROOT/'outputs'/(name+'.argv.json')).read_text())['argv']
            assert '--cf-learn' not in argv and argv[argv.index('--v311c-runs')+1]==str(seed)
            for flag,value in [('--v39-price','0.0187'),('--e-price','0.0187'),('--shop-world','2'),('--v311c-f','0.5,0.5'),('--v311c-q','0.2' if mode=='recvA' else '0')]:
                assert argv[argv.index(flag)+1]==value,(name,flag)
            totals[mode].update(n)
            for cue in ('n','e'):
                d=p['doors'][cue]
                assert sum(d.get(k,0) for k in ('正解','誤答','棄権'))==d['課題']
                doors[mode][cue].update(d)
            if seed<=3: first3[mode]+=p['doors']['e'].get('誤答',0)
            stored=json.loads((dest/'runs'/name/'counts.json').read_text())
            assert stored==p
            manifest=json.loads((dest/'runs'/name/'ledger_manifest.json').read_text())
            assert len(manifest)==2
            assert {Path(m['path']).name for m in manifest}=={f'seed{seed:03d}.jsonl.gz',f'seed{seed+1000:03d}.jsonl.gz'}
            assert all(m['rows']==1740 and Path(m['path']).is_file() for m in manifest)
            manifests.extend(manifest)
            checks.append({'condition':name,'world_tasks':3480,'counts_and_audits_match':True})
    aggregate=json.loads((dest/'aggregate.json').read_text())
    for mode in totals:
        assert totals[mode]['課題']==69600 and aggregate[mode]['numbers']==dict(totals[mode])
        for cue in ('n','e'):
            assert aggregate[mode]['doors'][cue]==dict(doors[mode][cue])
    assert all(doors['no_comm'][c]['課題']==doors['recvA'][c]['課題'] for c in ('n','e'))
    assert dict(first3)=={'no_comm':43,'recvA':38}
    assert len(manifests)==80 and sum(m['rows'] for m in manifests)==139200
    sha=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT/'source',text=True).strip()
    assert sha==EXPECTED and not subprocess.check_output(['git','diff','--name-only'],cwd=ROOT/'source',text=True).strip()
    return {'A_complete':True,'populations':40,'individual_ledgers':80,'world_tasks':139200,
            'source':sha,'A_finished':finished,'A_gate':gate,'counts':{m:dict(n) for m,n in totals.items()},
            'doors':{m:{c:dict(n) for c,n in ds.items()} for m,ds in doors.items()},'checks':checks,
            'ledger_validation':'各走行の保存時に1740行の本体の指紋を計算済み。ここでは80本の保存と行数の和を照合。'}

if __name__=='__main__': print(json.dumps(check(),ensure_ascii=False,indent=1))

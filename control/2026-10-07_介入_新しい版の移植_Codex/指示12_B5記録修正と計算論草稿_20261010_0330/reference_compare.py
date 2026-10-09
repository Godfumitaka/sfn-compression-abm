"""結果を見る前に固定した同一機械・全量比較。新しい不一致は保存して停止。"""
from collections import Counter
import copy
import gzip
import hashlib
import itertools
import json
from pathlib import Path
import sys
from run import HERE,B,C,E,read,save,validate,spec_sha

PAIRS={
    'off2':('off2_baseline200','off2_candidate200'),
    'off8':('off8_baseline200','off8_candidate200'),
    'off8-parallel':('off8_candidate200','off8_parallel200'),
    'on1-f0.1':('on1_f0.1_independent200','on1_f0.1_collective200'),
    'on1-f0.9':('on1_f0.9_independent200','on1_f0.9_collective200'),
    'receive-replay':('on2_receive200','on2_replay200')}

def lines(p):
    with (gzip.open(p,'rb') if p.suffix=='.gz' else p.open('rb')) as f:yield from f
def rows(p):
    for line in lines(p):yield json.loads(line)
def encode(x):return json.dumps(x,ensure_ascii=False,separators=(',',':')).encode()
def byte_check(name,a,b):
    h=[hashlib.sha256(),hashlib.sha256()];n=[0,0];first=None
    for i,pair in enumerate(itertools.zip_longest(a,b),1):
        for k,v in enumerate(pair):
            if v is not None:h[k].update(v);n[k]+=1
        if pair[0]!=pair[1] and first is None:first=i
    return dict(name=name,passed=first is None,lines=n,first_difference=first,sha256=[v.hexdigest() for v in h])

def header_diff(a,b,commits):
    assert a.keys()==b.keys()
    assert (a['code_commit'],b['code_commit'])==commits
    changed=[k for k in a if a[k]!=b[k]]
    assert changed==(['code_commit'] if commits[0]!=commits[1] else []),('見出しの差',changed)
    return changed

def checked_done(row,out,commit,replay=None):
    assert row['code_commit']==commit,'固定specと版が違う'
    p=out/'ledgers/cells'/row['cell']/f"seed{row['seed']:03d}.jsonl.gz"
    assert row['ledger_bytes']==p.stat().st_size,'圧縮サイズが実体と違う'
    assert next(rows(p))['code_commit']==commit
    result=copy.deepcopy(row)
    for k in ('code_commit','ledger_bytes','elapsed_sec','finished_at','peak_rss_mb'):result.pop(k,None)
    if replay is not None and 'smereplay' in result:
        assert result['smereplay']['replayed'] is replay
        # 再生を実際に検査してから、計算の違いを表す値だけを比較外へ。
        result['smereplay']['replayed']=False
    return result

def normalized(p):
    # 名称で特定した時計以外は落とさない。stage2の全値と順序を残す。
    if p.parent.parent.name=='stage2' and p.name.endswith('.summary.json'):
        x=read(p);assert 'seconds' in x;x.pop('seconds');yield encode(x);return
    for line in lines(p):
        if p.name.endswith('.cfvalue.jsonl'):
            x=json.loads(line);assert 'sec_trial' in x;x.pop('sec_trial');yield encode(x)
        elif p.parent.parent.name=='stage2' and p.name.startswith('seed') and p.name.endswith('.jsonl.gz') and '.initial.' not in p.name and '.rematch.' not in p.name:
            x=json.loads(line);assert 'seconds' in x and 'wrapper_seconds' in x
            x.pop('seconds');x.pop('wrapper_seconds');yield encode(x)
        else:yield line

def filemap(out,directory):
    return {str(p.relative_to(out)):p for p in (out/directory).rglob('*') if p.is_file()}

def complete(root,name):
    ev=root/'evidence'/name;r=read(ev/'runtime.json');validate(r)
    fixed=read(HERE/'specs'/f'{name}.json')
    assert r['plan_spec_sha256']==spec_sha(fixed)
    for key in ('name','commit','models','phase','parallel','seeds','model_argv','config','config_sha256','requires'):
        assert r[key]==fixed[key],('固定specとの差',key)
    resource=read(ev/'resource.json');assert resource['exitcode']==0 and not resource['warnings']
    assert resource['host']==r['host']
    out=Path(r['output']);ledgers=sorted((out/'ledgers/cells').glob('*/*.jsonl.gz'))
    assert len(ledgers)==r['models']
    T=int(r['argv'][r['argv'].index('--trial-count')+1])
    completion=[];headers={}
    for p in ledgers:
        stream=rows(p);h=next(stream);assert h['code_commit']==r['commit'] and h['trial_count']==T
        body=list(stream);assert len(body)==T and [x['prediction_order'] for x in body]==list(range(T))
        assert all(x['f_realized']==h['f_setting'] for x in body)
        headers[str(p.relative_to(out))]=h
    done=list((out/'ledgers/cells').glob('*/*.done'));assert len(done)==r['models']
    for p in done:checked_done(read(p),out,r['commit']);completion.append(str(p.relative_to(out)))
    if '--v311c' in r['model_argv']:
        s=read(out/'comm/run001.summary.json');assert s['trials']==T and not s['errors']
        assert len(s['agents'])==r['models']
        for agent in s['agents']:
            checked_done(agent,out,r['commit'])
            assert agent['v39'].get('not_in_dictionary',0)==0
            expected=2*T+(T//100 if '--v311c-probe-shop' in r['model_argv'] else 0)
            assert agent['v311c']['dictionary_checks']==2*T
        if r['phase']=='off' and r['models']==8:assert s['delivered']==0
        if r['phase'] in ('receive','replay'):assert s['delivered']>0
    tomb=list((out/'evictions').glob('*/*.summary.json'));assert len(tomb)==r['models']
    for p in tomb:
        x=read(p);assert x['tombstone_enabled'] and x['tombstone_hits']==0
        assert x['last_trial']==T-1
    return r,resource,out,headers,completion

def mandatory_negative(out,commit,h1,h2,commits):
    row=read(next((out/'ledgers/cells').glob('*/*.done')));rejected=[]
    for field in ('code_commit','ledger_bytes'):
        bad=dict(row);bad[field]='wrong' if field=='code_commit' else row[field]+1
        try:checked_done(bad,out,commit)
        except AssertionError:rejected.append(field)
        else:raise AssertionError('誤ったメタデータを通した')
    bad=copy.deepcopy(h2);bad['agent_ids']=['wrong']
    try:header_diff(h1,bad,commits)
    except AssertionError:rejected.append('header.agent_ids')
    else:raise AssertionError('誤った見出しを通した')
    return rejected

def compare(root,mode):
    names=PAIRS[mode];both=[complete(root,n) for n in names]
    a,b=[v[0] for v in both];outs=[v[2] for v in both];hs=[v[3] for v in both]
    assert a['host']==b['host'],'マック／クラウド・別機械を混ぜない'
    assert a['config_sha256']==b['config_sha256'] and a['models']==b['models']
    aa,bb=a['model_argv'][:],b['model_argv'][:]
    if mode=='off8-parallel':aa.remove('--v311c-serial')
    if mode=='receive-replay':i=bb.index('--v311c-sme-replay');del bb[i:i+2]
    if mode.startswith('on1'):
        for k in ('--v311c','--v311c-serial','--v311c-no-tags','--v311c-audit','--v311c-probe-shop','--v311c-lineage'):
            bb.remove(k)
        for k in ('--v311c-f','--v311c-groups','--v311c-q','--v311c-m','--v311c-runs','--v311c-recv','--v311c-b-n','--v311c-probe-every'):
            i=bb.index(k);del bb[i:i+2]
    assert aa==bb,'指定の旗の差以外がある'
    assert hs[0].keys()==hs[1].keys()
    commits=(a['commit'],b['commit']);checks=[];metadata=[]
    for key in hs[0]:metadata.append(dict(file=key,difference=header_diff(hs[0][key],hs[1][key],commits)))
    negative=mandatory_negative(outs[0],a['commit'],next(iter(hs[0].values())),next(iter(hs[1].values())),commits)
    for d in ('ledgers','side','evictions','attention','stage2'):
        maps=[filemap(out,d) for out in outs]
        if mode.startswith('on1') and d=='side':
            # 独立単独には集団の追加状態のnativeファイルがない。同じ読み取り符号の外部保存と比較する。
            extra=[k for k in maps[1] if k.endswith('.collective-runtime.jsonl.gz')]
            assert len(extra)==1
            checks.append(byte_check('追加状態：独立の外部保存対集団のnative全量',
                lines(root/'evidence'/names[0]/'agent0.runtime.jsonl.gz'),lines(maps[1].pop(extra[0]))))
        assert maps[0].keys()==maps[1].keys(),(d,'比較するファイルの種類が違う',set(maps[0])^set(maps[1]))
        for key in sorted(maps[0]):
            values=[]
            for side in range(2):
                p=maps[side][key]
                if d=='ledgers' and p.name.endswith('.gz'):
                    stream=lines(p);next(stream);values.append(stream)
                elif p.name.endswith('.done'):
                    values.append([encode(checked_done(read(p),outs[side],commits[side],side==1 if mode=='receive-replay' else None))])
                elif mode.startswith('on1') and side==1 and p.name.endswith('.sme.states.jsonl.gz'):
                    # no-tags/q0の追加の二段は、既に記録されたpostの同じ状態の写しだけ。
                    data=list(lines(p));post={json.loads(v)['trial']:json.loads(v)['state'] for v in data if json.loads(v).get('kind')=='post'}
                    phases=Counter()
                    for v in data:
                        row=json.loads(v)
                        if row.get('kind')=='collective_phase':
                            assert row['state']==post[row['trial']]
                            assert row['deliveries']=={'tag':'tuple','items':[]}
                            phases[row['phase']]+=1
                    assert phases=={'world':200,'received':200}
                    values.append(v for v in data if json.loads(v).get('kind')!='collective_phase')
                else:values.append(normalized(p))
            checks.append(byte_check(key,*values))
    if not mode.startswith('on1'):
        def events(out):
            for line in lines(out/'comm/run001.jsonl'):
                if json.loads(line).get('kind')!='summary':yield line
        checks.append(byte_check('通信の全事象',*(events(o) for o in outs)))
        summaries=[]
        for i,out in enumerate(outs):
            s=read(out/'comm/run001.summary.json')
            s['agents']=[checked_done(v,out,commits[i],i==1 if mode=='receive-replay' else None) for v in s['agents']]
            summaries.append([encode(s)])
        checks.append(byte_check('通信の全終了集計（検査したメタデータと時計以外）',*summaries))
        for filename in ('run001.jsonl.state.jsonl','run001.lineage.jsonl'):
            checks.append(byte_check(filename,*(lines(o/'comm'/filename) for o in outs)))
    for i in range(a['models']):
        for suffix in ('final-sme.jsonl.gz','model-rng.jsonl','rng.jsonl','cstar-final.json'):
            paths=[root/'evidence'/n/f'agent{i}.{suffix}' for n in names]
            assert paths[0].exists()==paths[1].exists(),suffix
            assert all(p.exists() for p in paths) or suffix in ('rng.jsonl','cstar-final.json')
            if paths[0].exists():checks.append(byte_check(f'個体{i}:{suffix}',*(lines(p) for p in paths)))
        rng=list(rows(root/'evidence'/names[1]/f'agent{i}.model-rng.jsonl'))
        assert len(rng)==200 and all(x['python_global_unchanged'] for x in rng)
    if mode=='receive-replay':
        for i in range(a['models']):
            files=list((outs[0]/'side').glob(f'*/seed{1+1000*i:03d}.sme.states.jsonl.gz'))
            assert len(files)==1
            phases=Counter(x['phase'] for x in rows(files[0]) if x.get('kind')=='collective_phase')
            assert phases=={'world':200,'received':200},phases
        initials=[x for p in (outs[0]/'stage2').glob('*/*.initial.jsonl.gz') for x in rows(p)]
        assert initials,'実走行の誕生の記録が無い'
        assert any(x.get('source')=='報告' for x in initials),'報告誕生が未発生'
        assert any(x.get('source')!='報告' for x in initials),'世界誕生が未発生'
        assert all(x.get('measure_birth_hu') is True for x in initials),'誕生HUの実記録が無い'
    return dict(passed=all(x['passed'] for x in checks),candidate=C,host=a['host'],mode=mode,
        names=names,checks=checks,mandatory_metadata=metadata,negative_examples_rejected=negative,
        rule='同じ機械の固定した二本。新しい不一致で停止。',
        exclusions=['検査済みcode_commit/ledger_bytes','doneと終了集計elapsed_sec/finished_at/peak_rss_mb',
        'cfvalue.sec_trial','stage2.seconds/wrapper_secondsとsummary.seconds',
        '一体q0/no-tagsの重複collective_phaseは全stateがpostと同一・空のdeliveries・世界/受信各200を検査後、独立にない写しだけを除く',
        '再生時はreplayedを実検査。flag/manifestはargv・固定spec・開始版の証拠で別検査'])

def main():
    root=Path(sys.argv[1]).resolve();mode=sys.argv[2]
    root.joinpath('gates').mkdir(exist_ok=True)
    result_path=root/'gates'/f'gate-{mode}.json'
    assert not result_path.exists(),'保存済みの比較を上書きしない'
    try:
        result=compare(root,mode)
    except Exception as error:
        result=dict(passed=False,candidate=C,mode=mode,error=repr(error),host=None)
    save(result_path,result)
    if not result['passed']:
        if not (root/'STOP.json').exists():save(root/'STOP.json',dict(reason='新しい不一致又は必須検査の失敗',gate=str(result_path)))
        raise SystemExit(1)
    print(json.dumps(dict(passed=True,gate=str(result_path),checks=len(result['checks'])),ensure_ascii=False))

if __name__=='__main__':main()

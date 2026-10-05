"""受付表の枠内で関門・本走行・各腕の分類を順に実行する。"""
from pathlib import Path
import subprocess,sys,os,json,gzip,hashlib,time,shutil
from datetime import datetime
HERE=Path(__file__).resolve().parents[2]
SOURCE=HERE/'source'
BASE=HERE.parent/'codex_attn_2026-10-03/run3380344'
PYTHON='/opt/homebrew/bin/python3.12'
CONFIG='config/sweep_shop_hide1_s1_2026-10-01.json'
COMMON='--nohash --vt 0.3842 --extend-rule none --charge1 d32 --fast --no-public-history --dump-slot-history --fix2-full --fix-order2 --proj-first --fill-norestate --no-charge2 --own-evidence --v39 --v39-budget inf --v39-decay actr --v310-be --hist-role --score-role --u-struct --relearn-init --tie-struct --amb-local --nsim 0.7 --ident-rho 0.5 --ident-argmax --ident-commons --dump-answers --dump-routing --answer-gap --strict-pc --cf-value --probe-world --e-price 0.01873710622997919 --no-compare --cells f0.5000_th2.1000_first_order'.split()
state={'phase':'preparing','completed':[],'seeds':list(range(1,21))}

def save(**changes):
    state.update(changes);state['time']=datetime.now().astimezone().isoformat()
    (HERE/'status.json').write_text(json.dumps(state,ensure_ascii=False,indent=2)+'\n')

def run(cmd,cwd,folder):
    folder.mkdir(parents=True,exist_ok=True)
    (folder/'command.json').write_text(json.dumps(cmd,ensure_ascii=False,indent=2)+'\n')
    env=dict(os.environ)
    env['EXPLORE3_MEM_GB']='1.6'
    env.pop('V38_FROM',None)
    for key in ('LC_ALL','LANG','LC_CTYPE'):env.pop(key,None)
    t0=time.monotonic()
    with (folder/'run.log').open('a') as stream:
        p=subprocess.Popen(['/usr/bin/time','-l',*cmd],cwd=cwd,env=env,stdout=stream,stderr=subprocess.STDOUT)
        save(pid=p.pid,command=cmd)
        rc=p.wait()
    (folder/'result.json').write_text(json.dumps({'rc':rc,'seconds':time.monotonic()-t0},indent=2)+'\n')
    if rc:raise RuntimeError(str(folder)+'：終了符号'+str(rc))

def check_done(root,seeds):
    records=[json.loads(line) for line in (root/'manifest.jsonl').read_text().splitlines()]
    assert sorted({r['seed'] for r in records})==sorted(seeds),records
    assert not any(r.get('error') for r in records),records
    paths=list(root.glob('ledgers/cells/*/seed*.done'))
    assert sorted(int(p.name[4:7]) for p in paths)==sorted(seeds)

def body(root):
    paths=list(root.glob('ledgers/cells/*/seed001.jsonl.gz'));assert len(paths)==1
    with gzip.open(paths[0],'rb') as stream:next(stream);return stream.read()

def gates():
    run([PYTHON,'tools/test_explore3.py'],SOURCE,HERE/'gates/component')
    checks=[]
    cfg=json.loads((SOURCE/CONFIG).read_text());cfg['trial_count']=80
    cfgpath=HERE/'gates/config80.json';cfgpath.write_text(json.dumps(cfg,ensure_ascii=False,indent=2)+'\n')
    for world in (1,2):
        for mode in ('A','C'):
            name=f'w{world}_{mode}'
            pair=[]
            for repo,kind in ((BASE,'baseline'),(SOURCE,'changed')):
                folder=HERE/'gates'/name/kind
                cmd=[PYTHON,'tools/v3_run.py',str(cfgpath),str(folder/'output'),*COMMON,'--workers','1','--seeds','1','--shop-world',str(world),'--v39-price','0.01873710622997919']
                if mode=='C':cmd.append('--cf-learn')
                run(cmd,repo,folder);check_done(folder/'output',[1]);pair.append(folder/'output')
            a,b=map(body,pair);assert a==b,name
            checks.append({'world':world,'mode':mode,'trials':80,'body_equal':True,'sha256':hashlib.sha256(a).hexdigest()})
    (HERE/'gates/flag_off.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2)+'\n')
    run([PYTHON,str(SOURCE/'tools/explore3_full_gate.py')],HERE,HERE/'logs/full_gate')
    run([PYTHON,str(SOURCE/'tools/explore3_connection_gates.py')],HERE,HERE/'logs/connection_gates')
    save(phase='gates_passed',gates=checks)

def main():
    try:
        if '--resume' in sys.argv:
            state.update(json.loads((HERE/'status.json').read_text()))
            state.pop('error',None)
            assert (HERE/'gates/flag_off.json').is_file()
        else:
            gates()
        plans=[]
        for world in (1,2):
            for mode in ('A','C'):
                for lam in ('0.01873710622997919','0.065'):
                    plans.append((f'L-B_w{world}_{mode}_lam{lam}',world,mode,lam,['--score-logp']))
        for lam in ('0.01873710622997919','0.03','0.065'):
            plans.append((f'T_w2_A_lam{lam}',2,'A',lam,['--tie-random']))
        for name,world,mode,lam,flags in plans:
            if name in state['completed']:continue
            if shutil.disk_usage(HERE).free<20*2**30:raise RuntimeError('出力を保存する空き容量が20 GiB未満')
            save(phase='running',arm=name)
            folder=HERE/'runs'/name
            cmd=[PYTHON,'tools/v3_run.py',CONFIG,str(folder),*COMMON,'--workers','8','--seeds',','.join(str(s) for s in range(1,21)),'--shop-world',str(world),'--v39-price',lam,*flags]
            if mode=='C':cmd.append('--cf-learn')
            run(cmd,SOURCE,HERE/'logs'/name);check_done(folder,list(range(1,21)))
            save(phase='classifying',arm=name)
            run([PYTHON,'tools/explore3_classify.py',str(folder),str(HERE/'classification'/name)],SOURCE,HERE/'logs'/(name+'_classification'))
            state['completed'].append(name);save()
        # L-BE は L-B・T の後、同じ関門を通した固定の解釈で走る。
        for world in (1,2):
            for mode in ('A','C'):
                for lam in ('0.01873710622997919','0.065'):
                    name=f'L-BE_w{world}_{mode}_lam{lam}'
                    if name in state['completed']:continue
                    if shutil.disk_usage(HERE).free<20*2**30:raise RuntimeError('出力を保存する空き容量が20 GiB未満')
                    save(phase='running',arm=name)
                    folder=HERE/'runs'/name
                    cmd=[PYTHON,'tools/v3_run.py',CONFIG,str(folder),*COMMON,'--workers','8','--seeds',','.join(str(s) for s in range(1,21)),'--shop-world',str(world),'--v39-price',lam,'--score-logp','--score-logp-e']
                    if mode=='C':cmd.append('--cf-learn')
                    run(cmd,SOURCE,HERE/'logs'/name);check_done(folder,list(range(1,21)))
                    save(phase='classifying',arm=name)
                    run([PYTHON,'tools/explore3_classify.py',str(folder),str(HERE/'classification'/name)],SOURCE,HERE/'logs'/(name+'_classification'))
                    state['completed'].append(name);save()
        save(phase='complete_L_T',R_status='指定三腕の全種の記憶台帳は未発見')
        subprocess.run([PYTHON,str(SOURCE/'tools/explore3_report.py')],check=True)
    except Exception as exc:
        save(phase='failed',error=repr(exc));raise

if __name__=='__main__':main()

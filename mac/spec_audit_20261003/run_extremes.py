from pathlib import Path
import subprocess,json,shlex,time,datetime,sys,shutil
R=Path(__file__).parent; S=R/'source'; PY='/opt/homebrew/opt/python@3.12/bin/python3.12'
base=next(x for x in (S/'tools/mac_c_chain.sh').read_text().splitlines() if x.startswith('FL="'))[4:-1]
base=shlex.split(base.replace('$L50','0.01873710622997919').replace('$WK','2'))
for mode in ['lambda0','f0','exc0']:
    if shutil.disk_usage(R).free < 17*2**30: raise SystemExit('空きが停止の値に達した')
    pm=subprocess.run(['pmset','-g','therm'],capture_output=True,text=True)
    if any('CPU_' in line and line.rstrip().split('=')[-1].strip() not in ['100','8','10'] for line in pm.stdout.splitlines()):
        raise SystemExit('熱の状態の追加確認が必要: '+pm.stdout)
    args=list(base)
    if mode=='f0':args[args.index('--cells')+1]='f0.0000_th2.1000_first_order'
    args += ['--seeds','1,2','--shop-world','2','--v39-price','0' if mode=='lambda0' else '0.01873710622997919']
    if mode=='exc0':args+=['--shop-exc','0']
    cmd=[PY,'tools/v3_run.py',str(R/(mode+'.json')),str(R/'runs'/mode)]+args
    t=time.time(); print('開始',mode,datetime.datetime.now().astimezone().isoformat(),flush=True)
    (R/(mode+'_command.json')).write_text(json.dumps(cmd,ensure_ascii=False,indent=2)+'\n')
    with (R/(mode+'.log')).open('w') as f:
        proc=subprocess.run(cmd,cwd=S,stdout=f,stderr=subprocess.STDOUT)
    rec={'mode':mode,'returncode':proc.returncode,'elapsed_s':time.time()-t,'thermal':pm.stdout}
    (R/(mode+'_completion.json')).write_text(json.dumps(rec,ensure_ascii=False,indent=2)+'\n');print(rec,flush=True)
    if proc.returncode:raise SystemExit(proc.returncode)

"""指示7の未着手二本を別々のjobs.pyへ送る。既存四本は再起動しない。"""
from pathlib import Path
import json, os, subprocess, sys, time
ROOT=Path(__file__).resolve().parent
WORK=ROOT/'native_full_01'
PAR=ROOT/'parallel_instruction7_01'
PY='/opt/homebrew/opt/python@3.12/bin/python3.12'
JOBS='/Users/tatsu-admin/jobs/jobs.py'
sys.path.insert(0,str(ROOT.parent/'codex_logp_main_2026-10-06'))
from common_01 import now, save

assert PAR.is_dir() and not (PAR/'coordinator_started.json').exists(), '監督を二重起動しない'
save(PAR/'coordinator_started.json',{'at':now(),'pid':os.getpid(),'cases':['on_own','on_keep']})
active={}
try:
    for name in ('on_own','on_keep'):
        assert not (PAR/'STOP.json').exists()
        command=[PY,JOBS,'run','--wait','--owner','SME_Cstar_instruction7_'+name,'--mem','8','--disk-path',str(WORK/name),'--',PY,str(ROOT/'run_full_case_instruction7_01.py'),name]
        log=(PAR/(name+'_jobs.log')).open('x')
        proc=subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
        active[name]=(proc,log)
        save(PAR/(name+'_claim.json'),{'at':now(),'claim_pid':proc.pid,'command':command})
    while active:
        for name,(proc,log) in list(active.items()):
            code=proc.poll()
            if code is None: continue
            log.close()
            save(PAR/(name+'_job_done.json'),{'at':now(),'exit':code,'claim_pid':proc.pid})
            del active[name]
            if code: raise RuntimeError('受付の関門の不通：'+name+'、'+(PAR/(name+'_jobs.log')).read_text()[-2500:])
        time.sleep(2)
    # 既存の四本と比較を待つ。最後の直列監督の停止は予約したディレクトリによる重複防止。
    while not (WORK/'off_L_comparison.json').exists():
        if (WORK/'STOP.json').exists(): raise RuntimeError('log Pの既存の比較が通る前に直列監督が停止')
        time.sleep(2)
    assert json.loads((WORK/'off_L_comparison.json').read_text())['passed']
    command=[PY,JOBS,'run','--wait','--owner','SME_Cstar_instruction7_full_compare','--mem','8','--disk-path',str(PAR),'--',PY,str(ROOT/'finish_full_comparison_instruction7_01.py')]
    with (PAR/'comparison_jobs.log').open('x') as log:
        proc=subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
        save(PAR/'comparison_claim.json',{'at':now(),'claim_pid':proc.pid,'command':command})
        code=proc.wait()
    if code: raise RuntimeError('全長の比較の不通：'+(PAR/'comparison_jobs.log').read_text()[-3500:])
    save(PAR/'complete.json',{'at':now(),'passed':True,'cases':['on_own','on_keep'],'existing_cases_preserved':['base_A','off_A','base_L','off_L']})
except Exception as e:
    if not (PAR/'STOP.json').exists(): save(PAR/'STOP.json',{'at':now(),'reason':str(e)})
    raise

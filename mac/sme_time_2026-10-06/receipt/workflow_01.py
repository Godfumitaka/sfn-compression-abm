"""20番・22番の報告が終わるまで待ち、受付を通して25番だけ測る。"""
from pathlib import Path
from datetime import datetime
import json
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parent
PRIOR=ROOT.parent/'codex_sme_evict_2026-10-06'
READ=ROOT.parent/'codex_sme_read22_2026-10-06'
SOURCE=ROOT.parent/'codex_sme_amemory_2026-10-05/source_a_opt'
BASELINE=ROOT.parent/'codex_sme_amemory_2026-10-05/vanilla_01/A'
COMMIT='374e3524a9e310c8295f87ac12506bba0b236696'


def registered(args,folder,memory,owner):
    command=[sys.executable,'/Users/tatsu-admin/jobs/jobs.py','run','--wait','--owner',owner,
             '--mem',str(memory),'--disk-path',str(folder),'--',*args]
    with (folder/'claim.log').open('x') as stream:
        code=subprocess.run(command,stdout=stream,stderr=subprocess.STDOUT).returncode
    assert code==0,(owner,'測定または読み取りの不通')


try:
    assert not (ROOT/'workflow_started.json').exists(),'二重の開始をしない'
    (ROOT/'workflow_started.json').write_text(json.dumps({'at':datetime.now().astimezone().isoformat(),
        'pid':__import__('os').getpid(),'priority_after':[20,22],'measurement_model_started':False},indent=2)+'\n')
    while not ((PRIOR/'all_complete.json').exists() and (READ/'reported_complete.json').exists()):
        assert not list(PRIOR.glob('*stop*.json')),'20番が停止。25番を始めない'
        assert not list(PRIOR.glob('*/*/resource_stop.json')),'20番の資源停止。25番を始めない'
        time.sleep(30)
    assert json.loads((PRIOR/'all_complete.json').read_text())['passed']
    assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=SOURCE,text=True).strip()==COMMIT
    assert not subprocess.check_output(['git','status','--porcelain'],cwd=SOURCE,text=True).strip()
    case=ROOT/'profile1740_01';case.mkdir(exist_ok=False)
    command=json.loads((BASELINE/'command.json').read_text())
    command[3]=str(case/'output')
    (case/'native_command.json').write_text(json.dumps(command,indent=2)+'\n')
    (case/'command.json').write_text(json.dumps([sys.executable,str(ROOT/'observe_01.py'),str(case/'native_command.json')],indent=2)+'\n')
    (case/'run_spec.json').write_text(json.dumps({'source':str(SOURCE),'commit':COMMIT,
        'output':str(case/'output'),'validation_command':str(case/'native_command.json'),'memory_diag':False},indent=2)+'\n')
    registered([sys.executable,str(ROOT/'run_case_01.py'),str(case)],case,8.5,'SME25 時間の全内訳 A種1')
    comparison=ROOT/'compare_01';comparison.mkdir(exist_ok=False)
    registered([sys.executable,str(ROOT/'compare_native_01.py'),str(BASELINE/'output'),str(case)],comparison,2.5,'SME25 観測の全バイト一致')
    analysis=ROOT/'analysis_job_01';analysis.mkdir(exist_ok=False)
    registered([sys.executable,str(ROOT/'analyze_01.py'),str(case)],analysis,2.5,'SME25 時間の読み取り')
    subprocess.run([sys.executable,str(ROOT/'finish_01.py')],check=True)
    subprocess.run([sys.executable,str(ROOT/'report_01.py'),'complete'],check=True)
    (ROOT/'all_complete.json').write_text(json.dumps({'passed':True,'at':datetime.now().astimezone().isoformat(),
        'reported':json.loads((ROOT/'reported_complete.json').read_text()),'model_changes':False},ensure_ascii=False,indent=2)+'\n')
except Exception as error:
    (ROOT/'workflow_stop.json').write_text(json.dumps({'at':datetime.now().astimezone().isoformat(),
        'reason':str(error),'model_changes':False},ensure_ascii=False,indent=2)+'\n')
    raise

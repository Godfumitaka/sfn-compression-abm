"""2026-10-05承認：Dのτ20本と質問確率30本。各本を共有受付へ出す。"""
from __future__ import annotations
import argparse
import fcntl
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import time

SOURCE=Path(__file__).resolve().parents[2]
ROOT=SOURCE.parent
BASE=ROOT/'axes_2026-10-05'
sys.path[:0]=[str(SOURCE),str(SOURCE/'tools'),str(Path(__file__).parent)]
import night
from axes_summary import summarize, existing_novel_table
STOP=False
EVIDENCE='control/2026-10-04_動詞の世界_Codex_二軸下見'


def write_json(path,data):
    night.write_json(path,data)


def source_guard(commit=None):
    if night.git(SOURCE,'branch','--show-current')!=night.WORK_BRANCH or night.git(SOURCE,'status','--porcelain'):
        raise RuntimeError('動詞の作業枝が違うか未コミットの変更がある')
    if commit is not None and night.git(SOURCE,'rev-parse','HEAD')!=commit:
        raise RuntimeError('事前に固定したコードが変わった')


def prepare():
    source_guard()
    gate=json.loads((BASE/'gate.json').read_text())
    if not gate['flag_off_equal_trial_bytes'] or gate['trial_rows']!=5000:
        raise RuntimeError('旗オフの関門が未完了')
    if (BASE/'plan.json').exists():
        raise RuntimeError('二重の計画作成はしない')
    old=json.loads((ROOT/'stage3_night/plan.json').read_text())
    original={(r['arm'],r['seed']):r for r in old['runs'] if r['U']=='global'}
    runs=[]
    reuse=[]
    for axis in ('tau','question'):
        (BASE/axis).mkdir(exist_ok=True)
    for tau in (.1,.25,.6,1.0):
        for seed in range(1,6):
            group=f'D_tau{tau:g}'
            label=f'{group}_s{seed:02d}'
            command=list(original[('D',seed)]['command'])
            command[3]=str(BASE/'tau'/label/'run')
            command[command.index('--use-forget')+1]=str(tau)
            runs.append({'axis':'tau','group':group,'label':label,'arm':'D','U':'global','seed':seed,'tau':tau,'p':'default','command':command})
    for p in (.25,.5):
        for arm in ('A','C','D'):
            for seed in range(1,6):
                group=f'{arm}_p{p:g}'
                label=f'{group}_s{seed:02d}'
                command=list(original[(arm,seed)]['command'])
                command[3]=str(BASE/'question'/label/'run')
                command+=['--shop-door-p',str(p)]
                runs.append({'axis':'question','group':group,'label':label,'arm':arm,'U':'global','seed':seed,'tau':.4 if arm=='D' else None,'p':p,'command':command})
    for axis, arms in (('tau',('D',)),('question',('A','C','D'))):
        for arm in arms:
            for seed in range(1,6):
                entry=original[(arm,seed)]
                group='D_tau0.4' if axis=='tau' else f'{arm}_default'
                label=f'{group}_s{seed:02d}'
                reuse.append({'axis':axis,'group':group,'label':label,'arm':arm,'U':'global','seed':seed,'tau':.4 if arm=='D' else None,'p':'default','existing_label':entry['label']})
                (BASE/axis/label).symlink_to(ROOT/'stage3_night'/entry['label'],target_is_directory=True)
    assert len(runs)==50 and len(reuse)==20
    assert all(1<=r['seed']<=5 and r['U']=='global' for r in runs+reuse)
    sizes=[json.loads((ROOT/'stage3_night'/r['label']/'resources.json').read_text())['output_bytes'] for r in old['runs'] if r['U']=='global']
    mean_size=sum(sizes)/len(sizes)
    plan={'prepared':night.now(),'commit':night.git(SOURCE,'rev-parse','HEAD'),'model_base':'3380344',
          'bin_width':500,'concurrency_cap':3,'mem_gb_per_run':.4,'estimated_output_bytes':round(mean_size*50),
          'runs':runs,'reuse':reuse}
    write_json(BASE/'plan.json',plan)
    public={**plan,'runs':[{**r,'command':[c.replace(str(ROOT),'.') for c in r['command']]} for r in runs]}
    write_json(BASE/'public_plan.json',public)
    print(json.dumps({'planned':50,'reuse':20,'estimated_output_bytes':plan['estimated_output_bytes'],'commit':plan['commit']},ensure_ascii=False),flush=True)


def read_plan():
    plan=json.loads((BASE/'plan.json').read_text())
    source_guard(plan['commit'])
    keys={(r['axis'],r['arm'],r['tau'],r['p'],r['seed']) for r in plan['runs']}
    wanted={('tau','D',t,'default',s) for t in (.1,.25,.6,1.0) for s in range(1,6)}|{('question',a,.4 if a=='D' else None,p,s) for p in (.25,.5) for a in ('A','C','D') for s in range(1,6)}
    if keys!=wanted or len(plan['runs'])!=50 or any(r['U']!='global' for r in plan['runs']):
        raise RuntimeError('承認された50本と違う')
    return plan


def publish(message, axis=None, existing=False):
    """指定の報告枝だけへ、最新をmergeしてから検査・pushする。"""
    night.fetch_report()
    target=night.REPORT_REPO/EVIDENCE
    target.mkdir(exist_ok=True)
    for filename in ('gate.json','public_plan.json','existing_checks.json'):
        p=BASE/filename
        if p.exists():
            shutil.copy2(p,target/filename)
    if axis:
        shutil.copytree(BASE/axis/'aggregate',target/axis,dirs_exist_ok=True)
    if existing and (BASE/'existing_checks.json').exists():
        old=json.loads((ROOT/'stage3_night/plan.json').read_text())
        existing_novel_table(BASE,old)
        shutil.copytree(BASE/'existing_aggregate',target/'existing',dirs_exist_ok=True)
        # 選択定義の個別例も公開。模型の生台帳と状態は送らない。
        for r in old['runs']:
            d=target/'existing'/r['label']
            d.mkdir(exist_ok=True)
            for filename in ('novel_IRR_cases.jsonl.gz','novel_IRR_selected.csv'):
                shutil.copy2(BASE/'existing'/r['label']/filename,d/filename)
    report=night.REPORT_REPO/night.REPORT_PATH
    report.write_text(report.read_text()+f'\n{night.now()} {message}\n')
    night.checked_git(night.REPORT_REPO,'add','--',night.REPORT_PATH,EVIDENCE)
    night.checked_git(night.REPORT_REPO,'commit','-m','動詞の二軸下見の関門・集計・進行を追記')
    for attempt in range(3):
        night.fetch_report()
        night.scan_range(night.REPORT_REPO,night.REPORT_BRANCH,'origin/'+night.REPORT_BRANCH)
        push=subprocess.run(['git','-c','core.commitGraph=false','push','--no-follow-tags','origin',f'refs/heads/{night.REPORT_BRANCH}:refs/heads/{night.REPORT_BRANCH}'],cwd=night.REPORT_REPO)
        if push.returncode==0:
            sha=night.git(night.REPORT_REPO,'rev-parse','HEAD')
            write_json(BASE/'last_push.json',{'time':night.now(),'branch':night.REPORT_BRANCH,'commit':sha})
            return sha
        if attempt<2:
            time.sleep(2)
    raise RuntimeError('報告のpushが3回通らない')


def one(label):
    plan=read_plan()
    found=[r for r in plan['runs'] if r['label']==label]
    if len(found)!=1:
        raise RuntimeError('計画に無い本')
    run=found[0]
    output=BASE/run['axis']/label
    output.mkdir(exist_ok=False)
    write_json(output/'admitted.json',{'time':night.now(),'pid':os.getpid(),'label':label})
    write_json(output/'command.json',{'commit':plan['commit'],'command':run['command']})
    started=time.monotonic()
    peak=0.0
    with (output/'run.log').open('w') as log:
        proc=subprocess.Popen(['/usr/bin/time','-l','-o',str(output/'time.txt'),*run['command']],cwd=SOURCE,stdout=log,stderr=subprocess.STDOUT)
        while proc.poll() is None:
            table={}
            for line in subprocess.check_output(['/bin/ps','-axo','pid=,ppid=,rss='],text=True).splitlines():
                pid,ppid,rss=map(int,line.split())
                table[pid]=(ppid,rss)
            descendants={proc.pid}
            while True:
                more={pid for pid,(ppid,_) in table.items() if ppid in descendants}
                if more<=descendants: break
                descendants|=more
            peak=max(peak,sum(table.get(pid,(0,0))[1] for pid in descendants)/1024)
            time.sleep(1)
    res={'label':label,'commit':plan['commit'],'returncode':proc.returncode,'model_seconds':round(time.monotonic()-started,3),
         'max_aggregate_rss_mib_sampled_1s':round(peak,3)}
    maximum=re.search(r'(\d+)\s+maximum resident set size',(output/'time.txt').read_text())
    res['process_peak_rss_bytes_time']=int(maximum.group(1)) if maximum else None
    write_json(output/'resources.json',res)
    if proc.returncode: return proc.returncode
    at=time.monotonic()
    with (output/'analysis.log').open('w') as log:
        result=subprocess.run([sys.executable,'tools/verb/analyze.py',str(output/'run'),str(run['seed']),str(output/'analysis')],cwd=SOURCE,stdout=log,stderr=subprocess.STDOUT)
    res['analysis_seconds']=round(time.monotonic()-at,3)
    res['analysis_returncode']=result.returncode
    write_json(output/'resources.json',res)
    if result.returncode: return result.returncode
    at=time.monotonic()
    with (output/'record.log').open('w') as log:
        result=subprocess.run([sys.executable,'tools/verb/record_axes.py',str(output/'run'),str(run['seed']),str(output/'record')],cwd=SOURCE,stdout=log,stderr=subprocess.STDOUT)
    res.update(record_seconds=round(time.monotonic()-at,3),record_returncode=result.returncode,supervised_wall_seconds=round(time.monotonic()-started,3))
    res['output_bytes']=sum(p.stat().st_size for p in output.rglob('*') if p.is_file())
    write_json(output/'resources.json',res)
    if result.returncode: return result.returncode
    write_json(output/'complete.json',{'time':night.now(),'label':label})
    return 0


def run_all():
    global STOP
    plan=read_plan()
    lock=(BASE/'pipeline.lock').open('w')
    fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    def stop(_sig,_frame):
        global STOP
        STOP=True
    signal.signal(signal.SIGTERM,stop)
    signal.signal(signal.SIGINT,stop)
    active={}
    done={r['label'] for r in plan['runs'] if (BASE/r['axis']/r['label']/'complete.json').exists()}
    pending=[r for r in plan['runs'] if r['label'] not in done]
    published=set(json.loads((BASE/'axes_published.json').read_text()) if (BASE/'axes_published.json').exists() else [])
    try:
        publish(f"\n## 2026-10-05 二軸の下見の開始時記録\n\n旧い照合の作業枝 `{night.WORK_BRANCH}` = `{plan['commit']}`。Uはglobal、N3、λ=0.01873710622997919、5000試行。新規はτ軸20本・質問p軸30本、種1〜5のみ。τ=0.4のD5本と従来質問割合のA/C/D15本は段3を使う。\n\n--shop-door-pは旧入口でverb-worldとの併用を拒んでいた。動詞名を足す前に既存shopworld.rehideを呼ぶ最小配線を追加。別乱数shopdoor、確率pで経路0.0.0、それ以外は元の一階の候補（役割ユナリーとドア以外）から一様。名前・attachは候補に入らない。abm/・照合・選択・保持・Uの答えは変更していない。\n\n旗オフ関門はD/global/τ=0.4/種1の5000試行を再生成し、段3の台帳本体（試行行）を全バイト照合して一致。ヘッダはcode_commit以外が一致し、コミットの欄の相違だけを別記した。[関門](./{Path(EVIDENCE).name}/gate.json)。構造検査22件と読取の席検査2件を確認。\n\n50本の出力見込みは段3global15本の実測平均×50で {plan['estimated_output_bytes']:,} bytes。各本はjobs.py run --wait、mem0.4、disk-pathつき。最大3本の受付要求を置き、受付が通った本だけ走る。[全50本の事前計画](./{Path(EVIDENCE).name}/public_plan.json)。SchulerはSfNまでは走らせず、出典不一致を残す。種6〜20の本走行と種21〜40の読取・走行は行わない。結果の良し悪しは判定しない。")
        while pending or active:
            if STOP: raise InterruptedError('停止指示')
            while pending and len(active)<plan['concurrency_cap']:
                r=pending.pop(0)
                label=r['label']
                output=BASE/r['axis']/label
                if output.exists(): raise RuntimeError(label+'の途中出力を上書きせず停止')
                cmd=[sys.executable,str(night.JOBS),'run','--wait','--owner','Codex-動詞二軸-'+label,'--mem','0.4','--disk-path',str(output),'--',sys.executable,str(Path(__file__).resolve()),'one',label]
                log=(BASE/(label+'.jobs.log')).open('w')
                proc=subprocess.Popen(cmd,cwd=SOURCE,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
                active[label]=(r,proc,log)
            for label,(r,proc,log) in list(active.items()):
                if proc.poll() is None: continue
                log.close()
                if proc.returncode or not (BASE/r['axis']/label/'complete.json').exists():
                    raise RuntimeError(label+f'の走行・照合・読取が終了コード{proc.returncode}で停止')
                done.add(label)
                del active[label]
                print('完了',len(done),'/50',label,flush=True)
            for axis in ('tau','question'):
                if axis in published: continue
                if all(r['label'] in done for r in plan['runs'] if r['axis']==axis):
                    if not (BASE/'existing_checks.json').exists():
                        continue
                    output,checks=summarize(BASE,plan,axis)
                    assert checks.get('appearance_and_question_checks')
                    assert checks['record_reads']==checks['new_completed']+checks['reused_completed']
                    old=json.loads((ROOT/'stage3_night/plan.json').read_text())
                    existing_novel_table(BASE,old)
                    extra=(BASE/'existing_aggregate/tables.md').read_text() if not published else ''
                    sha=publish(f"\n## 二軸下見：{axis}軸の終了\n\n新規{checks['new_completed']}本完了、既存{checks['reused_completed']}本を集計。出現の並びと、同じpの質問の並びを種ごとに照合して一致。\n\n"+(output/'axis_tables.md').read_text()+'\n'+extra+f"\n[表と照合記録](./{Path(EVIDENCE).name}/{axis}/axis_checks.json)。各CSVに区間・語・種別、頻度の重みと欠測、回復時点と語別質問数、黙り理由、記憶量を保存。",axis=axis,existing=True)
                    published.add(axis)
                    write_json(BASE/'axes_published.json',sorted(published))
                    print('報告push',axis,sha,flush=True)
            write_json(BASE/'status.json',{'time':night.now(),'state':'running','complete':len(done),'planned':50,'active':list(active),'pending':len(pending),'axes_published':sorted(published)})
            time.sleep(2)
        if len(published)!=2:
            raise RuntimeError('既存記録の読取又は軸の報告が未完了')
        sha=publish(f"二軸の下見は新規50/50本と既存20本分の参照を集計し、二軸の報告をpush済み。作業枝 `{night.WORK_BRANCH}` = `{plan['commit']}`、直前の報告枝 `{night.REPORT_BRANCH}` = `{night.git(night.REPORT_REPO,'rev-parse','HEAD')}`。種1〜5のみ。",existing=True)
        write_json(BASE/'status.json',{'time':night.now(),'state':'complete','complete':50,'planned':50,'report_commit':sha})
    except BaseException as exc:
        for r,proc,log in active.values():
            if proc.poll() is None:
                os.killpg(proc.pid,signal.SIGTERM)
                proc.wait(timeout=30)
                subprocess.run([sys.executable,str(night.JOBS),'release','--pid',str(proc.pid)])
            log.close()
        reason=re.sub(r'/(?:Users|home)/[^\s\'\"]+','<ローカルパス>',f'{type(exc).__name__}: {exc}')
        write_json(BASE/'status.json',{'time':night.now(),'state':'stopped','complete':len(done),'reason':reason})
        try:
            for axis in ('tau','question'):
                output,checks=summarize(BASE,plan,axis)
                publish(f"二軸下見停止：{reason}。{axis}軸は新規{checks['new_completed']}/{checks['new_planned']}本が完走。途中出力を保存し、完走・照合済みのみの表を添付。",axis=axis,existing=True)
        except BaseException as report_exc:
            write_json(BASE/'unpublished_stop.json',{'reason':reason,'publish_error_type':type(report_exc).__name__})
        raise


if __name__=='__main__':
    ap=argparse.ArgumentParser()
    ap.add_argument('mode',choices=('prepare','run','one'))
    ap.add_argument('label',nargs='?')
    a=ap.parse_args()
    if a.mode=='prepare': prepare()
    elif a.mode=='run': run_all()
    else: raise SystemExit(one(a.label))

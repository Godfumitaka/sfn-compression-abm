"""指示12の先頭200試行の関門だけ。模型への停止・削除・自動再試行はしない。"""
from pathlib import Path
from datetime import datetime
import gzip, hashlib, importlib.util, json, os, shutil, subprocess, sys, time

ROOT = Path(__file__).resolve().parent
BASE = ROOT.parents[1]
SOURCE = BASE/'cstar_stage2_reuse_source'
CODE = '87d32af8ea2291e6e0267d12e2f8e7adb62c3925'
PY = '/opt/homebrew/bin/python3.12'
JOBS = '/Users/tatsu-admin/jobs/jobs.py'
TRIALS = 200
MEM_GB = 4
spec = importlib.util.spec_from_file_location('readonly_guard', BASE/'sme_attention_2026-10-07/priority25_reserve6_2026-10-06/hold_dispatchers.py')
G = importlib.util.module_from_spec(spec)
spec.loader.exec_module(G)


def stamp():
    return datetime.now().astimezone().isoformat()


def write(name, data):
    p = ROOT/name
    tmp = Path(str(p)+'.tmp')
    tmp.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
    tmp.replace(p)


def deadline():
    if stamp()[:19] >= '2026-10-09T09:00:00':
        raise RuntimeError('期限後の新規投入は行わない')


def source_ok():
    head = subprocess.check_output(['git','rev-parse','HEAD'],cwd=SOURCE,text=True).strip()
    dirty = subprocess.check_output(['git','status','--porcelain','--untracked-files=all'],cwd=SOURCE,text=True).strip()
    if head != CODE or dirty:
        raise RuntimeError(('固定した自分のソースが変わった',head,dirty))


def machine():
    ps = G.processes(); models = G.models(ps); reg = G.J.read_reg()
    warnings, _, thermal = G.J.therm(); swap_ok, note = G.J.swap_ok()
    return dict(at=stamp(),models={str(p):dict(ppid=v[0],state=v[1],rss_kb=v[3]) for p,v in models.items()},
        model_children=len(models),paused=sum('T' in v[1] for v in models.values()),
        registered=[dict(pid=r['pid'],owner=r['owner'],mem_gb=r['mem_gb']) for r in reg],
        disk_free_bytes=shutil.disk_usage(ROOT).free,swap_used_mb=G.J.swap_used_mb(),swap_ok=swap_ok,
        swap_note=note,thermal_warnings=warnings,thermal=thermal,
        unregistered_heavy=[dict(pid=p,rss_mb=r) for p,r,_ in G.J.unregistered_heavy(reg,G.J.procs())])


def start_ok(m):
    return (m['model_children'] < 8 and m['disk_free_bytes'] >= 20*2**30
        and m['swap_ok'] and not m['thermal_warnings'] and not m['unregistered_heavy'])


def entry(kind):
    while True:
        deadline(); m = machine()
        if start_ok(m): break
        write(kind+'_entry_waiting.json',dict(at=stamp(),machine=m,model_started=False))
        time.sleep(30)
    source_ok()
    if (ROOT/kind/'output').exists() or (ROOT/(kind+'_entry_started.json')).exists():
        raise RuntimeError('同じ関門の既存出力・開始記録がある。再投入しない')
    write(kind+'_entry_started.json',dict(at=stamp(),machine=m,code=CODE))
    os.execv(PY,[PY,str(ROOT/'observe.py'),str(ROOT/kind/'native_command.json')])


def one(kind):
    if any((ROOT/p).exists() for p in (kind+'/run.log',kind+'_entry_started.json',kind+'_completed.json',kind+'/output')):
        raise RuntimeError(('開始済みの関門は再投入しない',kind))
    while True:
        deadline(); m = machine()
        total = sum(r['mem_gb'] for r in m['registered'])
        if start_ok(m) and total+MEM_GB <= 24: break
        write('status.json',dict(phase='waiting_before_receipt',kind=kind,pid=os.getpid(),at=stamp(),
            requested_mem_gb=MEM_GB,registered_mem_gb=total,machine=m))
        time.sleep(30)
    source_ok()
    command = [PY,JOBS,'run','--wait','--owner','Codex2 指示12 使い回し関門 '+kind,
               '--mem',str(MEM_GB),'--disk-path',str(ROOT/kind),'--',PY,str(ROOT/'gate.py'),'entry',kind]
    (ROOT/kind/'receipt_command.json').write_text(json.dumps(command,ensure_ascii=False,indent=2)+'\n')
    env = dict(os.environ,PYTHONHASHSEED='0',SME_EXACT_SOURCE=str(SOURCE))
    for key in ('LANG','LC_ALL','LC_CTYPE'): env.pop(key,None)
    warned = False
    with (ROOT/kind/'run.log').open('x') as log:
        proc = subprocess.Popen(command,cwd=SOURCE,env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
        write('status.json',dict(phase='receipt_wait_or_running',kind=kind,at=stamp(),pid=os.getpid(),
            receipt_pid=proc.pid,code=CODE,requested_mem_gb=MEM_GB))
        while proc.poll() is None:
            m = machine()
            if (m['disk_free_bytes'] < 18.5*2**30 or not m['swap_ok'] or m['thermal_warnings']
                or m['unregistered_heavy'] or m['model_children'] > 8):
                if not warned: write('warning.json',dict(kind=kind,machine=m,models_not_signaled=True))
                warned = True
                write('status.json',dict(phase='no_new_submission_waiting_natural_end',kind=kind,
                    at=stamp(),pid=os.getpid(),receipt_pid=proc.pid,models_not_signaled=True))
            time.sleep(30)
    if proc.returncode: raise RuntimeError(('模型の終了コード',kind,proc.returncode))
    if warned: raise RuntimeError('資源条件の確認不足。新規投入・合格宣言を止める')
    write(kind+'_completed.json',dict(at=stamp(),code=CODE,exit_code=0))


def byte_compare(a, b, ledger=False):
    digest_a, digest_b = hashlib.sha256(), hashlib.sha256()
    size_a = size_b = 0
    opener = gzip.open if ledger else open
    with opener(a,'rb') as x, opener(b,'rb') as y:
        if ledger: x.readline(); y.readline()
        while True:
            aa, bb = x.read(1024*1024), y.read(1024*1024)
            digest_a.update(aa); digest_b.update(bb); size_a += len(aa); size_b += len(bb)
            if aa != bb: raise RuntimeError(('全バイト不一致',str(a),str(b),size_a,size_b))
            if not aa: break
    return dict(equal=True,bytes=size_a,off_sha256=digest_a.hexdigest(),on_sha256=digest_b.hexdigest())


def compare():
    def files(kind):
        folder = ROOT/kind/'output'
        return {str(p.relative_to(folder)):p for pattern in ('ledgers/**/*.jsonl.gz','side/**/*')
                for p in folder.glob(pattern) if p.is_file()}
    left, right = files('reuse_off_200'),files('reuse_on_200')
    if left.keys()!=right.keys(): raise RuntimeError('模型のファイル集合の不一致')
    records=[]
    for name in sorted(left):
        records.append(dict(file=name,**byte_compare(left[name],right[name],name.startswith('ledgers/'))))
    for name in ('tie_state.jsonl','saved_matcher.jsonl.gz'):
        records.append(dict(file=name,**byte_compare(ROOT/'reuse_off_200'/name,ROOT/'reuse_on_200'/name)))
    if len(records)!=9: raise RuntimeError(('所定のファイル数でない',len(records)))
    for kind in ('reuse_off_200','reuse_on_200'):
        folder=ROOT/kind/'output'
        with gzip.open(next(folder.glob('ledgers/**/*.jsonl.gz')),'rb') as stream:
            if sum(1 for _ in stream)-1 != TRIALS: raise RuntimeError('台帳の試行数不足')
        summary=json.loads(next(folder.glob('attention/**/*.summary.json')).read_text())
        if summary['trials']!=TRIALS or summary['all_trials_leakage_checked']!=TRIALS:
            raise RuntimeError('注意の情報境界の全試行の記録不足')
    # 時間は別の診断。模型の9ファイルでは見出し以外の行・値を除かない。
    write('required_gate.json',dict(at=stamp(),passed=True,code=CODE,trials=TRIALS,records=records,
        excluded=['台帳の見出し一行だけ'],production_started=False,
        timing_diagnostics_separate=True,full_length_gate_complete=False))



def cpu_compare():
    readings={kind:json.loads((ROOT/kind/'measurement.json').read_text())
              for kind in ('reuse_off_200','reuse_on_200')}
    off,on=readings['reuse_off_200'],readings['reuse_on_200']
    if any(r['trials']!=TRIALS for r in readings.values()):
        raise RuntimeError('CPU比較の試行数不足')
    write('cpu_comparison.json',dict(at=stamp(),code=CODE,trials=TRIALS,
        off=off,on=on,off_cpu_seconds=off['cpu_seconds'],on_cpu_seconds=on['cpu_seconds'],
        on_over_off=on['cpu_seconds']/off['cpu_seconds'],
        reduction_fraction=1-on['cpu_seconds']/off['cpu_seconds'],
        includes_observer_and_state_save=True,full_length_estimate=False))


def main():
    if len(sys.argv)>1 and sys.argv[1]=='entry': return entry(sys.argv[2])
    try:
        with (ROOT/'supervisor.lock').open('x') as f: f.write(str(os.getpid())+'\n')
        write('launch.json',dict(at=stamp(),pid=os.getpid(),code=CODE,sequence=['reuse_off_200','reuse_on_200'],mem_gb=MEM_GB))
        for kind in ('reuse_off_200','reuse_on_200'): one(kind)
        compare()
        cpu_compare()
        write('status.json',dict(phase='small_gate_completed_review_pending',at=stamp(),pid=os.getpid(),code=CODE))
    except Exception as exc:
        write('failure.json',dict(at=stamp(),error=repr(exc),automatic_retry=False,models_not_signaled=True))
        write('status.json',dict(phase='stopped_no_automatic_retry',at=stamp(),pid=os.getpid(),error=repr(exc)))
        raise


if __name__=='__main__': main()

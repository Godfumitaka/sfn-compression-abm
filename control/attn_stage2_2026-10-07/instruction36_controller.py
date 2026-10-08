"""指示36のP5・P7r。受付と一模型ずつの実関門。停止・削除・再試行無し。"""
from pathlib import Path
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import time
from compare_records import tree

ROOT = Path(__file__).resolve().parent
BASE = ROOT.parents[1]
SOURCE = BASE / 'cstar_stage2_memo_source'
CODE = '8ed8cf2b2920787e55b6f5134300fc350dffe5e7'
spec = importlib.util.spec_from_file_location('readonly_resource', ROOT.parent / 'instruction19_speed_gate/gate.py')
G = importlib.util.module_from_spec(spec); spec.loader.exec_module(G)


def deadline():
    if G.stamp()[:19] >= '2026-10-11T09:00:00':
        raise RuntimeError('期限後の新規投入は行わない')


def write(name, data):
    path = ROOT / name; temporary = Path(str(path)+'.tmp')
    temporary.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n'); temporary.replace(path)


def plan(): return json.loads((ROOT / 'preparation_manifest.json').read_text())


def source_ok():
    if subprocess.check_output(['git','rev-parse','HEAD'],cwd=SOURCE,text=True).strip() != CODE:
        raise RuntimeError('固定版の変更')
    if subprocess.check_output(['git','status','--porcelain','--untracked-files=all'],cwd=SOURCE,text=True).strip():
        raise RuntimeError('検査中の固定ソースが変更された')
    for name,digest in plan()['immutable_sha256'].items():
        if hashlib.sha256(Path(name).read_bytes()).hexdigest() != digest:
            raise RuntimeError(('固定した道具又は命令の変更',name))


def warning(m):
    return (m['model_children'] > 8 or m['disk_free_bytes'] < 18.5*2**30
            or not m['swap_ok'] or m['thermal_warnings'] or m['unregistered_heavy']
            or sum(r['mem_gb'] for r in m['registered']) > 24)


def start_ok(m, mem, models):
    return (G.start_ok(m) if models else m['disk_free_bytes'] >= 20*2**30
            and m['swap_ok'] and not m['thermal_warnings'] and not m['unregistered_heavy']) \
        and m['model_children']+models <= 8 and sum(r['mem_gb'] for r in m['registered'])+mem <= 24


def alive(pid):
    rows=G.G.processes(); return pid in rows and 'Z' not in rows[pid][1]


def wait_for(mem, models, phase):
    while True:
        deadline(); source_ok()
        if any((ROOT/n).exists() for n in ('warning.json','failure.json')):
            raise RuntimeError('既に警告・停止済み。新規投入無し')
        m=G.machine()
        if start_ok(m,mem,models): return m
        write('status.json',dict(at=G.stamp(),pid=os.getpid(),code=CODE,phase=phase,machine=m))
        time.sleep(20)


def entry(kind):
    case=plan()['cases'][kind]; folder=ROOT/kind
    if (folder/'output').exists() or (ROOT/(kind+'_entry_started.json')).exists():
        raise RuntimeError('既存成果・開始記録の再投入をしない')
    # この受付は登録済みのため、その予約を二重に足さない。jobsのCPU判定は保つ。
    m=wait_for(0,1,'entry_waiting_'+kind)
    write(kind+'_entry_started.json',dict(at=G.stamp(),code=CODE,world=case['world'],seed=case['seed'],
          trials=case['trials'],mem_gb=case['mem_gb'],machine=m,
          actual_native_command=json.loads((folder/'native_command.json').read_text()),
          implemented=['P5','P7r'],previous_five_and_P10_flags_unchanged=True,production_started=False))
    os.execv(G.PY,[G.PY,str(ROOT/case['observer']),str(folder/'native_command.json')])


def completed(kind, proc):
    case=plan()['cases'][kind]; folder=ROOT/kind
    if proc.returncode != 0: raise RuntimeError(('実受付終了コード',kind,proc.returncode))
    measure=json.loads((folder/'measurement.json').read_text()); worker=json.loads((folder/'worker_pid.json').read_text())
    if measure['trials'] != case['trials'] or measure['pid'] != worker['pid'] or alive(worker['pid']):
        raise RuntimeError('原計測・実模型終了の確認不足')
    if case['observer']=='observe_light.py':
        if not measure.get('native_loop_returned') or not (folder/'worker_finished.json').exists():
            raise RuntimeError('原native_loop_returned又は最後のcloseが無い')
    with (folder/'run.log').open('rb') as stream:
        stream.seek(max(0,(folder/'run.log').stat().st_size-65536))
        if b'ALLDONE' not in stream.read(): raise RuntimeError('原ALLDONE無し')
    write(kind+'_completed.json',dict(at=G.stamp(),code=CODE,trials=case['trials'],
          receipt_pid=proc.pid,receipt_exit_code=proc.returncode,receipt_exit_code_observable=True,
          measurement=measure,native_all_done=True))


def first_100(left,right):
    rows={}
    for label,folder in [('off',left),('on',right)]:
        with (folder/'performance.jsonl').open() as stream:
            row=next(json.loads(line) for line in stream if json.loads(line)['trial']==99)
        rows[label]=dict(wall_seconds=row['elapsed_seconds'],cpu_seconds=row['cpu_seconds'],
                         peak_rss_bytes=row['peak_rss_bytes'],memo_diagnostics=row['memo_diagnostics'])
    return dict(readings=rows,cpu_ratio=rows['on']['cpu_seconds']/rows['off']['cpu_seconds'],
                wall_ratio=rows['on']['wall_seconds']/rows['off']['wall_seconds'],
                scope='sweep.run_one直前から第100台帳の原呼出し後・当該試行の追加控え保存前まで')


def comparison(kind):
    deadline(); source_ok(); case=plan()['cases'][kind]
    if not (ROOT/(kind+'_completed.json')).exists(): raise RuntimeError('実完走前に比較しない')
    if (ROOT/(kind+'_required_gate.json')).exists(): raise RuntimeError('合格を再生成しない')
    left=Path(case['reference']); right=ROOT/kind
    reference_done=json.loads((ROOT/(left.name+'_completed.json')).read_text())
    if reference_done['receipt_exit_code'] != 0 or reference_done['trials'] != 200:
        raise RuntimeError('参考側の実完走の確認不足')
    for folder in (left,right):
        guard=json.loads((folder/'p10_cache_guard.jsonl.gz.summary.json').read_text())
        if not (guard['enabled'] and guard['native_loop_returned'] and guard['boundaries']==200 and guard['forbidden_reads']==0):
            raise RuntimeError('P10の見張り又は試行数が不合格')
    write(kind+'_comparison_entry.json',dict(at=G.stamp(),mem_gb=1,reference=str(left)))
    result=tree(left,right,case['trials'],case['compare_observer'])
    result.update(at=G.stamp(),code=CODE,world=case['world'],seed=case['seed'],
                  implemented=['P5','P7r'],previous_five_and_P10_flags_unchanged=True)
    if (left/'measurement.json').exists():
        off=json.loads((left/'measurement.json').read_text()); on=json.loads((right/'measurement.json').read_text())
        write(kind+'_cpu_comparison.json',dict(at=G.stamp(),reference=off,current=on,
              cpu_ratio=on['cpu_seconds']/off['cpu_seconds'],wall_ratio=on['wall_seconds']/off['wall_seconds'],
              scope='worker_model_observer_state_save',pure_model_seconds=False,full_length_estimate=False,
              starts_are_different=True,individual_P5_or_P7r_effect=False,
              first_100=first_100(left,right)))
    write(kind+'_required_gate.json',result)


def monitored(command, kind, models):
    mem=plan()['cases'][kind]['mem_gb'] if models else 1
    wait_for(mem,models,'waiting_before_receipt_'+kind+('' if models else '_comparison'))
    suffix='' if models else '_comparison'
    log=((ROOT/kind/'run.log') if models else (ROOT/(kind+'_comparison.log'))).open('x')
    with log:
        proc=subprocess.Popen(command,cwd=SOURCE,env=dict(os.environ,PYTHONHASHSEED='0',SME_EXACT_SOURCE=str(SOURCE)),
                              stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
        write(kind+suffix+'_receipt_submitted.json',dict(at=G.stamp(),pid=proc.pid,mem_gb=mem,command=command))
        halted=False
        while proc.poll() is None:
            try:
                source_ok(); m=G.machine()
                if warning(m):
                    if not halted: write('warning.json',dict(at=G.stamp(),machine=m,models_not_signaled=True))
                    halted=True
                write('status.json',dict(at=G.stamp(),pid=os.getpid(),code=CODE,receipt_pid=proc.pid,machine=m,
                      phase='no_new_submission_waiting_natural_end' if halted else 'running_'+kind+suffix))
            except Exception as exc:
                if not halted: write('failure.json',dict(at=G.stamp(),error=repr(exc),automatic_retry=False,models_not_signaled=True))
                halted=True
            time.sleep(20)
        write(kind+suffix+'_receipt_ended.json',dict(at=G.stamp(),pid=proc.pid,exit_code=proc.returncode))
        if halted or proc.returncode != 0: raise RuntimeError(('停止又は実終了コード',halted,proc.returncode))
        return proc


def main():
    if len(sys.argv)>1:
        if sys.argv[1]=='entry': return entry(sys.argv[2])
        if sys.argv[1]=='compare': return comparison(sys.argv[2])
        raise RuntimeError('未知の入口')
    with (ROOT/'supervisor.lock').open('x') as out: out.write(str(os.getpid())+'\n')
    try:
        source_ok()
        for kind,case in plan()['cases'].items():
            if (ROOT/kind/'output').exists() or (ROOT/(kind+'_receipt_submitted.json')).exists():
                raise RuntimeError('原開始・成果を繰り返さない')
            folder=ROOT/kind
            cmd=[G.PY,G.JOBS,'run','--wait','--owner','Codex2 指示36 模型 '+kind,
                 '--mem',str(case['mem_gb']),'--disk-path',str(folder),'--',G.PY,str(ROOT/'controller.py'),'entry',kind]
            proc=monitored(cmd,kind,1); completed(kind,proc)
            if case['reference'] is None:
                continue
            cmd=[G.PY,G.JOBS,'run','--wait','--owner','Codex2 指示36 読取り '+kind,
                 '--mem','1','--disk-path',str(ROOT),'--',G.PY,str(ROOT/'controller.py'),'compare',kind]
            monitored(cmd,kind,0)
        write('status.json',dict(at=G.stamp(),pid=os.getpid(),code=CODE,
              phase='two_200_trial_gates_completed_full_cloud_gate_pending',
              full_length_gate_complete=False,adoption_decided=False))
    except Exception as exc:
        write('failure.json',dict(at=G.stamp(),error=repr(exc),automatic_retry=False,models_not_signaled=True))
        write('status.json',dict(at=G.stamp(),pid=os.getpid(),phase='stopped_no_automatic_retry',error=repr(exc)))
        raise


if __name__=='__main__': main()

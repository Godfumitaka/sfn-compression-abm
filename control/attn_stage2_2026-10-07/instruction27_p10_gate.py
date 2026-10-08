"""指示27のP10。五つの200試行合格後に全長と並行、同じ受付条件で一件ずつ。"""
from pathlib import Path
import importlib.util
import json
import os
import sys
import time
from reference_observation import convert

ROOT=Path(__file__).resolve().parent
BASE=ROOT.parents[1]
FIVE=ROOT.parent/'instruction26_basic_gate_7294389d'
sys.path.insert(0,str(FIVE))
from compare_records import compare
spec=importlib.util.spec_from_file_location('readonly_admission',FIVE/'controller.py')
H=importlib.util.module_from_spec(spec);spec.loader.exec_module(H)
H.ROOT=ROOT
H.SOURCE=BASE/'cstar_stage2_cache_prune_source'
H.CODE=json.loads((ROOT/'preparation_manifest.json').read_text())['code']
G=H.G


def dependency():
    for name in ('warning.json','failure.json'):
        if (FIVE/name).exists():raise RuntimeError(('五つの世界2関門が停止',name))
    for kind in ('w2_default_off_200','w2_basic_on_200'):
        path=FIVE/(kind+'_required_gate.json')
        complete=FIVE/(kind+'_completed.json')
        if not path.exists() or not complete.exists():return False
        row=json.loads(path.read_text());done=json.loads(complete.read_text())
        if (not row['passed'] or row['code']!='7294389d70795c847790472aa836b93dc1ca7fd5'
                or row['world']!=2 or row['seed']!=41 or row['trials']!=200
                or not row['strictpc_counter']['passed']
                or any(not record['passed'] for record in row['records'])
                or done['receipt_exit_code']!=0 or not done['receipt_exit_code_observable']
                or not done['native_all_done'] or done['trials']!=200):
            raise RuntimeError('五つの200試行の実合格・実完走の版又は結果が違う')
    return True


def entry(kind):
    case=H.plan()['cases'][kind];folder=ROOT/kind
    if (folder/'output').exists() or (ROOT/(kind+'_entry_started.json')).exists():
        raise RuntimeError('既存の模型・成果の再投入無し')
    if not dependency():raise RuntimeError('五つの世界2の200試行実合格前')
    machine=H.wait_for(0,1,'entry_waiting_'+kind)
    H.write(kind+'_entry_started.json',dict(at=G.stamp(),code=H.CODE,world=2,seed=41,
            trials=case['trials'],mem_gb=case['mem_gb'],machine=machine,
            actual_native_command=json.loads((folder/'native_command.json').read_text()),
            P10=case['prune'],speed_five=case['prune'],no_forget_exec=case['no_forget_exec']))
    os.execv(G.PY,[G.PY,str(ROOT/case['observer']),str(folder/'native_command.json')])


def comparison(kind):
    G.deadline();H.source_ok();case=H.plan()['cases'][kind]
    if not (ROOT/(kind+'_completed.json')).exists():raise RuntimeError('実完走前')
    if (ROOT/(kind+'_required_gate.json')).exists():raise RuntimeError('同じ合格を生成しない')
    left=Path(case['reference']);right=ROOT/kind
    H.write(kind+'_comparison_entry.json',dict(at=G.stamp(),mem_gb=1,reference=str(left),P10=case['prune']))
    result=H.tree(left,right,case['trials'],not case['prune'] and case['compare_observer'])
    b=dict(reference_observation_files_exist=case['compare_observer'],order_preserved=True)
    if case['prune']:
        guard=json.loads((right/'p10_cache_guard.jsonl.gz.summary.json').read_text())
        if (not guard['enabled'] or not guard['native_loop_returned'] or guard['forbidden_reads']!=0
                or guard['boundaries']!=case['trials']):
            raise RuntimeError(('見張りの原完了・0回・全試行境界の確認不足',guard))
        if case['compare_observer']:
            filtered=Path(case['filtered']) if case['filtered'] else ROOT/(kind+'_independent_reference')
            if case['filtered'] is None:convert(left,filtered)
            transform=json.loads((filtered/'transformation.json').read_text())
            if not transform['passed'] or not transform['original_rng_digest_reconstructed']:
                raise RuntimeError('独立した後処理が未合格')
            b.update(transformation=transform,records=[dict(file=n,**compare(filtered/n,right/n))
                                                      for n in ('tie_state.jsonl','saved_matcher.jsonl.gz')])
        else:
            # 原全長と同じ軽い観測。両側に控えの追加観測ファイルがないことを確認する。
            if any((root/name).exists() for root in (left,right) for name in ('tie_state.jsonl','saved_matcher.jsonl.gz')):
                raise RuntimeError('原全長と追加控えの観測が異なる')
            b.update(records=[],both_original_cache_observation_sets_empty=True)
        result.update(cache_observation=b,guard=guard,P10=True)
    else:result.update(P10=False)
    result.update(at=G.stamp(),code=H.CODE,world=2,seed=41,world1_gate_complete=False,
                  full_first_bundle_complete=False,adoption_decided=False)
    original=json.loads((left/'measurement.json').read_text());current=json.loads((right/'measurement.json').read_text())
    H.write(kind+'_cpu_comparison.json',dict(at=G.stamp(),reference=original,current=current,
            cpu_ratio=current['cpu_seconds']/original['cpu_seconds'],wall_ratio=current['wall_seconds']/original['wall_seconds'],
            observer=case['observer'],pure_model_seconds=False,full_length_estimate=False))
    H.write(kind+'_required_gate.json',result)


def main():
    if len(sys.argv)>1:
        if sys.argv[1]=='entry':return entry(sys.argv[2])
        if sys.argv[1]=='compare':return comparison(sys.argv[2])
        raise RuntimeError('未知の入口')
    with (ROOT/'supervisor.lock').open('x') as stream:stream.write(str(os.getpid())+'\n')
    try:
        while not dependency():
            G.deadline();H.source_ok()
            H.write('status.json',dict(at=G.stamp(),pid=os.getpid(),code=H.CODE,
                                      phase='waiting_five_world2_200_gates',models_started=False))
            time.sleep(20)
        for kind,case in H.plan()['cases'].items():
            if (ROOT/kind/'output').exists() or (ROOT/(kind+'_receipt_submitted.json')).exists():
                raise RuntimeError('同じ処理を投入しない')
            command=[G.PY,G.JOBS,'run','--wait','--owner','Codex2 指示27 P10 '+kind,
                     '--mem',str(case['mem_gb']),'--disk-path',str(ROOT/kind),'--',G.PY,str(ROOT/'gate.py'),'entry',kind]
            proc=H.monitored(command,kind,1);H.completed(kind,proc)
            if case['reference'] is None:continue
            command=[G.PY,G.JOBS,'run','--wait','--owner','Codex2 指示27 P10 三関門 '+kind,
                     '--mem','1','--disk-path',str(ROOT),'--',G.PY,str(ROOT/'gate.py'),'compare',kind]
            H.monitored(command,kind,0)
        H.write('status.json',dict(at=G.stamp(),pid=os.getpid(),code=H.CODE,
                phase='world2_P10_gates_completed_world1_pending',world1_gate_complete=False,adoption_decided=False))
    except Exception as exc:
        H.write('failure.json',dict(at=G.stamp(),error=repr(exc),automatic_retry=False,models_not_signaled=True))
        H.write('status.json',dict(at=G.stamp(),pid=os.getpid(),phase='stopped_no_automatic_retry',error=repr(exc)))
        raise


if __name__=='__main__':main()

"""段B2用：固定した候補の回答で、ドア課題だけ注意を使い学ぶ。

既定は注意なし。--attn-select --attn-door-only で腕1、さらに
--attn-fix-door-names を付けると腕2。段①の --attn-fix-answer-names
とは別で、世界のドア名 hold・hold_b を全試行で固定する。
この道具は非ドアの回答の一致だけを検査し、成績を集計しない。
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from pathlib import Path
import sys
import time

W=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(W/'tools'),str(W)]

import attndoor as D
import attnsel as A

ANSWER_FIELDS=('prediction_kind','predicted_edge','abstain_reason')


def response_bytes(payload):
    return json.dumps({k:payload[k] for k in ANSWER_FIELDS},ensure_ascii=False,
                      sort_keys=True,separators=(',',':')).encode('utf-8')


def replay(frozen,seed,output,*,arm,beta,eta):
    if seed not in range(1,21):
        raise ValueError('種は1〜20のみ')
    check_path=frozen/f'seed{seed:03d}.freeze.check.json'
    check=json.loads(check_path.read_text())
    assert check['full_census'] and check['trials_compared']==1740
    assert check['unit_weights_answers_match'] and check['unit_weights_scores_match']
    input_path=frozen/f'seed{seed:03d}.frozen.jsonl.gz'
    folder=output/frozen.name
    folder.mkdir(parents=True,exist_ok=True)
    stem=f'seed{seed:03d}.arm{arm}.b{beta:g}_e{eta:g}'
    output_path=folder/f'{stem}.attn.jsonl.gz'
    summary_path=folder/f'{stem}.check.json'
    if output_path.exists() or summary_path.exists():
        raise RuntimeError('既存の注意の控えを上書きしない')
    learner=D.DoorAttention(arm,beta=beta,eta=eta)
    count=non_door=0
    started=time.monotonic()
    result={'stage':'B2','world':check['world'],'seed':seed,'arm':arm,'beta':beta,'eta':eta,
            'trials_compared':0,'non_door_trials_compared':0,'non_door_answers_match':True,
            'tolerance':None,'mismatch':None,'model_updated':False,
            'attention_rng':'none','existing_rng_consumed':False,
            'task_instruction_assumption':'課題の指示として本人にドアを問うことが伝えられているとみなし、held_out_is_doorを使う',
            'phaseC_started':False,'phase3_started':False}
    try:
        with gzip.open(input_path,'rt',encoding='utf-8') as frames, gzip.open(output_path,'wt',encoding='utf-8') as answers:
            for line in frames:
                frame=json.loads(line)
                assert frame['seed']==seed and frame['world']==check['world'] and frame['trial']==count
                cs=tuple(D.decode_candidate(c) for c in frame['candidates'])
                prepared=learner.prepare(frame['agent_id'],count,frame['public_names'],
                    frame['door_task'],frame['baseline'],cs)
                # 今の回答を先に控える。finish の後に選び直さない。
                response=dict(prepared.payload)
                if not frame['door_task']:
                    non_door+=1
                    if response_bytes(response)!=response_bytes(frame['baseline']):
                        result['non_door_answers_match']=False
                        result['mismatch']={'trial':count,'actual':response,'expected':frame['baseline']}
                        raise RuntimeError('ドア以外の課題で元N3の回答と違う')
                record=learner.finish(prepared,frame['feedback'])
                record.update(world=frame['world'],seed=seed,answer_before_update=response,
                              fixed_memory=True,existing_rng_consumed=False)
                # L・重み・候補の控えだけ。世界の正誤・店・日別の集計はしない。
                A.write_record(answers,record)
                count+=1
                result.update(trials_compared=count,non_door_trials_compared=non_door)
    except BaseException as error:
        if result['mismatch'] is None:
            result['mismatch']={'trial':count,'error':repr(error)}
        raise
    finally:
        result['elapsed_seconds']=time.monotonic()-started
        result['full_census']=count==1740
        result['weights_final']=dict(learner.weights)
        if output_path.exists():
            result['output_bytes']=output_path.stat().st_size
            result['output_sha256']=hashlib.sha256(output_path.read_bytes()).hexdigest()
        summary_path.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    assert count==1740
    return result


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--frozen',type=Path,required=True,help='その腕の候補の控えのフォルダ')
    ap.add_argument('--seed',type=int,choices=range(1,21),required=True)
    ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--attn-select',action='store_true')
    ap.add_argument('--attn-door-only',action='store_true')
    ap.add_argument('--attn-fix-door-names',action='store_true')
    ap.add_argument('--attn-beta',type=float,default=5.)
    ap.add_argument('--attn-eta',type=float,default=.05)
    args=ap.parse_args()
    if args.attn_fix_door_names and not args.attn_select:
        ap.error('--attn-fix-door-names は --attn-select と一緒に使う')
    if args.attn_select and not args.attn_door_only:
        ap.error('段②は --attn-door-only を必須にする')
    arm=2 if args.attn_fix_door_names else 1 if args.attn_select else 0
    result=replay(args.frozen,args.seed,args.output,arm=arm,beta=args.attn_beta,eta=args.attn_eta)
    print(json.dumps(result,ensure_ascii=False),flush=True)


if __name__=='__main__':
    main()

"""既存二段階と今回の二段階を数え、同じ表に置く。解釈は加えない。"""
from collections import Counter
from datetime import datetime
from zoneinfo import ZoneInfo
from decimal import Decimal
from pathlib import Path
import gzip, hashlib, json, shutil, subprocess, sys

ROOT=Path(__file__).resolve().parent
RESULTS=ROOT.parent/'codex_worldv4_2026-10-01/results'
REPORT=RESULTS/'control/2026-10-03_LLMのドアの割合_Codex.md'
DEST=RESULTS/'mac/llm_door_20261003'
MARKER='<!-- llm-door-results -->'
PREFIX='Codex ドア割合 2026-10-03'
LEDGER=Path('/Users/tatsu-admin/llm_trial_out/費用.jsonl')
sys.path.insert(0,str(ROOT/'source/llm_trial'))
import fullhist_report as existing
import world

def now():return datetime.now(ZoneInfo('Asia/Tokyo')).isoformat(timespec='seconds')
def save(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,ensure_ascii=False,indent=1)+'\n')
def costs(rows):
    tries=[t for r in rows for t in r['試み']]
    thinking=[t['使用量'].get('output_tokens_details',{}).get('thinking_tokens') for t in tries]
    known=[n for n in thinking if n is not None]
    return {'calls':len(tries),'input':sum(t['使用量']['input_tokens'] for t in tries),
            'output':sum(t['使用量']['output_tokens'] for t in tries),
            'thinking':sum(known),'thinking_missing':len(thinking)-len(known),
            'thinking_zero':sum(n==0 for n in known),'thinking_max':max(known,default=None),
            'thinking_mean':sum(known)/len(known) if known else None,
            'dollars':str(sum((Decimal(str(t['費用'])) for t in tries),Decimal(0))),
            'models':dict(Counter(t.get('応答の model') for t in tries))}
def collect(fraction,path,provenance):
    rows=[json.loads(line) for line in path.read_text().splitlines()]
    learn=[r for r in rows if r['段']=='学習'];fin=[r for r in rows if r['段']=='最後の試験']
    assert len(learn)==40 and len(fin)==16
    assert {r['i'] for r in learn}==set(range(40)) and {r['i'] for r in fin}==set(range(16))
    assert sum(r['ドアを伏せた'] for r in learn)==int(40*fraction)
    truth={f'{t}・{c}':world.vocab(1)[world.door_pred(2,t,c)] for t,c in world.CASES}
    per={c:[r for r in fin if r['場合']==c] for c in existing.CASES}
    assert all(len(rs)==4 and all(r['正解']==truth[c] for r in rs) for c,rs in per.items())
    modal={c:(sorted(Counter(r.get('answer') for r in rs if r.get('answer')).items(),key=lambda x:(-x[1],x[0])) or [(None,0)])[0][0] for c,rs in per.items()}
    learning_doors={c:sum(r['ドアを伏せた'] and r['場合']==c for r in learn) for c in existing.CASES}
    groups={name:[r for r in fin if r['場合'].endswith(cue)] for name,cue in [('通常','n'),('例外','e')]}
    errors=Counter()
    for r in fin:
        if r['判定']!='誤答':continue
        typ,cue=r['場合'].split('・')
        if cue=='e' and r.get('answer')==truth[typ+'・n']:errors['例外で通常の答え']+=1
        elif cue=='n' and r.get('answer')==truth[typ+'・e']:errors['通常で例外の答え']+=1
        else:errors['その他の記号']+=1
    confidence={k:[r.get('confidence') for r in fin if r['判定']==k] for k in ('正解','誤答','黙り')}
    stat={'fraction':fraction,'provenance':provenance,'source_log':str(path),
          'source_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
          'learning_door_questions':learning_doors,'pattern':existing.pattern(modal,truth),'modal':modal,
          'best_correct':sum(r.get('最もありそうな答えが正しい',False) for r in fin),
          'best_correct_by_case':{c:sum(r.get('最もありそうな答えが正しい',False) for r in rs) for c,rs in per.items()},
          'best_correct_by_day':{c:sum(r.get('最もありそうな答えが正しい',False) for r in rs) for c,rs in groups.items()},
          'actual':dict(Counter(r['判定'] for r in fin)),
          'actual_by_day':{c:dict(Counter(r['判定'] for r in rs)) for c,rs in groups.items()},
          'errors':dict(errors),'confidence':confidence,
          'confidence_by_case':{c:[r.get('confidence') for r in rs] for c,rs in per.items()},
          'answers_by_case':{c:[r.get('answer') for r in rs] for c,rs in per.items()},
          'learning':costs(learn),'final_test':costs(fin),'all':costs(rows)}
    assert stat['all']['models']=={'claude-sonnet-5-5':stat['all']['calls']}
    summ=json.loads(path.with_name(path.stem+'_要約.json').read_text())
    assert summ['組']==1 and summ['世界']==2 and summ['effort']=='medium' and summ['model']=='claude-sonnet-5-5'
    assert summ['最もありそうな答えが正しい（16 問）']==stat['best_correct']
    assert summ['判定']=={k:stat['actual'].get(k,0) for k in summ['判定']}
    if provenance=='今回':assert summ['door_fraction']==fraction
    return stat,rows

def main():
    records=[];all_rows={}
    files=[(0.25,ROOT/'outputs/f025/段階S基準_w2.jsonl','今回'),
           (0.5,ROOT/'baselines/段階S基準_w2.jsonl','既存'),
           (0.75,ROOT/'outputs/f075/段階S基準_w2.jsonl','今回'),
           (1.0,ROOT/'baselines/段階S全部ドア_w2.jsonl','既存')]
    for fraction,path,provenance in files:
        if provenance=='今回' and not (path.parent/'finished.json').exists():continue
        stat,rows=collect(fraction,path,provenance)
        records.append(stat);all_rows[fraction]=rows
    raw=LEDGER.read_bytes();before=json.loads((ROOT/'ledger_before.json').read_text())
    assert hashlib.sha256(raw[:before['bytes']]).hexdigest()==before['sha256']
    ledger_rows=[json.loads(line) for line in raw.splitlines()]
    own=[r for r in ledger_rows if r['what'].startswith(PREFIX)]
    known=sum((Decimal(str(r['cost'])) for r in own),Decimal(0));assert known<=Decimal('10')
    for s in records:
        if s['provenance']!='今回':continue
        label=f"f{round(s['fraction']*100):03d}"
        booked=[r for r in own if r['what'].startswith(PREFIX+' '+label+' ')]
        assert len(booked)==s['all']['calls']
        assert sum(r['in'] for r in booked)==s['all']['input'] and sum(r['out'] for r in booked)==s['all']['output']
        assert sum((Decimal(str(r['cost'])) for r in booked),Decimal(0))==Decimal(s['all']['dollars'])
    complete=len(records)==4
    save(DEST/'aggregate.json',{'time':now(),'complete':complete,'stages':records,'known_task_dollars':str(known),
                              'preflight_dollars':json.loads((ROOT/'preflight.json').read_text())['cost'],'ledger_prefix_unchanged':True})
    (DEST/'費用_今回.jsonl').write_text('\n'.join(json.dumps(r,ensure_ascii=False) for r in own)+'\n')
    for filename in ('preflight.json','preflight_response.json','ledger_before.json','baselines_manifest.json','gate_before.json','gate_after.json','fraction_checks.json'):
        shutil.copyfile(ROOT/filename,DEST/filename)
    for folder in ('baselines','gate_before','gate_after'):
        dest=DEST/folder;dest.mkdir(exist_ok=True)
        for p in (ROOT/folder).iterdir():
            if p.is_file():shutil.copyfile(p,dest/p.name)
    for s in records:
        if s['provenance']!='今回':continue
        label=f"f{round(s['fraction']*100):03d}";dest=DEST/label;dest.mkdir(exist_ok=True)
        for p in (ROOT/'outputs'/label).iterdir():
            if p.suffix=='.jsonl':(dest/(p.name+'.gz')).write_bytes(gzip.compress(p.read_bytes(),mtime=0))
            elif p.is_file():shutil.copyfile(p,dest/p.name)
        shutil.copyfile(ROOT/('outputs_'+label+'.log'),dest/'run.log')
    scripts=DEST/'scripts';scripts.mkdir(exist_ok=True)
    for name in ('preflight.py','capture_requests.py','run_stage.py','report.py'):
        shutil.copyfile(ROOT/name,scripts/name)
    source=ROOT/'source'
    sha=subprocess.check_output(['git','rev-parse','HEAD'],cwd=source,text=True).strip()
    changed=subprocess.check_output(['git','diff','--name-only','9e4ba04',sha],cwd=source,text=True).splitlines()
    assert changed==['llm_trial/fullhist_stages.py','llm_trial/world.py']
    assert not subprocess.check_output(['git','diff','--name-only'],cwd=source,text=True).strip()
    (DEST/'source.patch').write_text(subprocess.check_output(['git','diff','9e4ba04',sha],cwd=source,text=True))
    save(DEST/'source_and_scope.json',{'base':'9e4ba043e7a1160d87270230a96e267bacce2fc8','source':sha,
        'branch':'codex/llm-door-fraction-2026-10-03','changed_files':changed,'python':'3.12.13',
        'model':'claude-sonnet-5-5','thinking':'adaptive','effort':'medium','display':'summarized','max_tokens':32000,
        'world':2,'set_seed':1,'new_fractions':[0.75,0.25],'task_limit_dollars':10,'existing_ledger':str(LEDGER)})
    prefix=REPORT.read_text().split(MARKER)[0].rstrip()
    lines=[prefix,'',MARKER,'',f'集計時刻：{now()}。'+('二つの新しい段階を終了。' if complete else '完了した段階のみ記載。'),'',
           '0.5と1.0は10月2日の既存記録を読むだけで再利用。今回の新しいAPI走行は0.75と0.25のみ。全履歴、40場面、最後の試験16問（通常8・例外8、甲／乙×通常／例外は各4）。出力上限32000、推論の要約summarized、試験の正解は履歴に加えない。',
           f'コード：{sha}。変更はllm_trial/world.pyとllm_trial/fullhist_stages.pyの割合の引数のみ。abm/・指示・答えの形・模型・推論設定は変更なし。','',
           '最有力の答えが正しい数は、黙った場合の答えも数える既存の基準。実際の正解・外れ・黙りは別表。答え方の型は、四つの場合の最頻の記号の並びによる既存の分類（同数なら名前の順）。','',
           '| ドア割合 | 記録 | ドアを問う学習場面/40 | 最有力が正しい/16 | 通常/8 | 例外/8 | 答え方の型 |','|---:|---|---:|---:|---:|---:|---|']
    for s in records:
        lines.append(f"| {s['fraction']:.2f} | {s['provenance']} | {sum(s['learning_door_questions'].values())} | {s['best_correct']} | {s['best_correct_by_day']['通常']} | {s['best_correct_by_day']['例外']} | {s['pattern']} |")
    lines+=['','| ドア割合 | 甲・通常/4 | 甲・例外/4 | 乙・通常/4 | 乙・例外/4 |','|---:|---:|---:|---:|---:|']
    for s in records:lines.append('| '+f"{s['fraction']:.2f}"+' | '+' | '.join(str(s['best_correct_by_case'][c]) for c in existing.CASES)+' |')
    lines+=['','| ドア割合 | 日 | 実際の正解 | 外れ | 黙り | 形の崩れ | 上限で切れた |','|---:|---|---:|---:|---:|---:|---:|']
    for s in records:
        for day,v in s['actual_by_day'].items():lines.append('| '+f"{s['fraction']:.2f}"+' | '+day+' | '+' | '.join(str(v.get(k,0)) for k in ('正解','誤答','黙り','形の崩れ','上限で切れた'))+' |')
    lines+=['','ドアを問う学習場面の内訳（学習全体では甲・通常16、甲・例外4、乙・通常16、乙・例外4。割合の変更で、この場面数と順番は変わらない）：','',
            '| ドア割合 | 甲・通常 | 甲・例外 | 乙・通常 | 乙・例外 |','|---:|---:|---:|---:|---:|']
    for s in records:lines.append('| '+f"{s['fraction']:.2f}"+' | '+' | '.join(str(s['learning_door_questions'][c]) for c in existing.CASES)+' |')
    lines+=['','外れの型と確信：','',
            '| ドア割合 | 例外で通常の答え | 通常で例外の答え | その他の記号 | 外れの確信（全件） | 確信0.9以上の外れ |','|---:|---:|---:|---:|---|---:|']
    for s in records:
        wrong=s['confidence']['誤答']
        lines.append('| '+f"{s['fraction']:.2f}"+' | '+' | '.join(str(s['errors'].get(k,0)) for k in ('例外で通常の答え','通常で例外の答え','その他の記号'))+' | '+('・'.join(str(v) for v in wrong) or '対象なし')+' | '+str(sum(v is not None and v>=0.9 for v in wrong))+' |')
    lines+=['','| ドア割合 | 場合 | 答え（4問） | 確信（4問） |','|---:|---|---|---|']
    for s in records:
        for c in existing.CASES:lines.append(f"| {s['fraction']:.2f} | {c.replace('n','通常').replace('e','例外')} | {'・'.join(str(v) for v in s['answers_by_case'][c])} | {'・'.join(str(v) for v in s['confidence_by_case'][c])} |")
    lines+=['','推論のトークンは応答のusage.output_tokens_details.thinking_tokens。出力のトークンに含まれ、二重に費用へ足さない。','',
            '| ドア割合 | 部分 | 問い合わせ | 入力 | 出力 | 推論 | 推論0の問い | 推論の平均 | 推論の最大 | 費用（ドル） |','|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|']
    for s in records:
        for key,part in [('learning','学習'),('final_test','最後の試験')]:
            c=s[key];thinking=str(c['thinking']) if not c['thinking_missing'] else f"{c['thinking']}（欠け{c['thinking_missing']}件）"
            lines.append(f"| {s['fraction']:.2f} | {part} | {c['calls']} | {c['input']} | {c['output']} | {thinking} | {c['thinking_zero']} | {c['thinking_mean']:.2f} | {c['thinking_max']} | {Decimal(c['dollars']):.6f} |")
    lines+=['','| ドア割合 | 学習＋最後の試験の費用（ドル） |','|---:|---:|']
    for s in records:lines.append(f"| {s['fraction']:.2f} | {Decimal(s['all']['dollars']):.6f} |")
    lines+=['','費用は既存の帳簿と同じく、応答の入力・出力の使用量に単価を掛けた値。入力は100万トークンあたり2ドル、出力は10ドル。トークン確認の要求は無料として記録している。',
           f'今回の帳簿の費用：{known:.6f}ドル（接続確認0.000070ドルを含む）。上限10ドル。既存の0.5・1.0の費用は当時の費用であり、今回の上限には足していない。',
           '今回の段階ごとに、帳簿の問い合わせ数・入力・出力・費用の和を問いごとの記録と照合、一致。既存帳簿の開始前の全バイトが残っていることを照合、一致。応答のmodelは全問い合わせでclaude-sonnet-5-5。',
           f'記録：mac/llm_door_20261003/。問いごとの応答・確信・推論の要約、要求本体、今回の費用行、既存二段階の写しと指紋、APIなしの照合結果、変更差分、数え上げの道具を保存。元の新しい記録は{ROOT}/outputs/に保持。','']
    REPORT.write_text('\n'.join(lines)+'\n')
    return {'complete':complete,'known_task_dollars':str(known),'stages':[{k:s[k] for k in ('fraction','provenance','best_correct','best_correct_by_day','pattern')} for s in records]}

if __name__=='__main__':print(json.dumps(main(),ensure_ascii=False))

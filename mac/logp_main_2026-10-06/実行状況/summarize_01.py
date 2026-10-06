"""保存した台帳・SME候補・状態を読み、指定した数だけを表にする。"""
from pathlib import Path
from collections import Counter, defaultdict
import gzip
import hashlib
import json
import sys
import csv

ROOT=Path(__file__).resolve().parent
folder=Path(sys.argv[1]).resolve()
spec=json.loads((folder/'analysis_spec.json').read_text())
output=Path(spec['original_output'])
analysis=Path(spec['analysis_output'])
command=json.loads((folder/'command.json').read_text())
seed=int(command[command.index('--seeds')+1])
trials=int(command[command.index('--trial-count')+1])
assert 1 <= seed <= 20
assert trials in (200,1740)


def plain(value):
    if not isinstance(value,dict) or 'tag' not in value:return value
    tag=value['tag']
    if tag=='mapping':return {plain(k):plain(v) for k,v in value['items']}
    if tag in ('tuple','list','set','frozenset'):
        return tuple(plain(x) for x in value['items'])
    if tag=='dataclass':return {k:plain(v) for k,v in value['fields'].items()}
    if tag=='enum':return value['value']
    raise ValueError(tag)


def rawhash(path):
    h=hashlib.sha256()
    with path.open('rb') as stream:
        while data:=stream.read(1024*1024):h.update(data)
    return h.hexdigest()


ledger=next(output.glob('ledgers/**/*.jsonl.gz'))
meta={}
counts={cue:Counter() for cue in ('e','n')}
allcounts={cue:Counter() for cue in ('e','n')}
with gzip.open(ledger,'rt') as stream:
    header=json.loads(next(stream));assert header['run_seed']==seed
    for line in stream:
        row=json.loads(line)
        if row.get('record_type')!='trial':continue
        t=row['prediction_order']
        assert t not in meta
        meta[t]={k:row.get(k) for k in ('shop_cue','shop_type','held_out_is_door','hit','prediction_kind','predicted_edge','R_used','abstain_reason','registration_event')}
        cue=row['shop_cue'];assert cue in ('e','n')
        outcome='黙り' if row['prediction_kind']=='Abstain' else ('正解' if row['hit']==1 else '外れ')
        allcounts[cue][outcome]+=1
        if row['held_out_is_door']:counts[cue][outcome]+=1
assert len(meta)==trials
candidates=next(analysis.glob('side/**/*.sme.candidates.jsonl.gz'))
pertrial={}
seen=set();classes={cue:Counter() for cue in ('e','n')};allclasses={cue:Counter() for cue in ('e','n')}
with gzip.open(candidates,'rt') as stream:
    for line in stream:
        value=json.loads(line);t=value['trial'];assert t not in seen;seen.add(t)
        row=meta[t]
        expected=row['predicted_edge'] if row['prediction_kind']!='Abstain' else {'abstain_reason':row['abstain_reason']}
        assert value['prediction']==expected,(t,'再解析の予測が本物と違う')
        # chosen_Rは門の前の一位、R_usedは実際に回答へ使われた定義。
        # below_tauの棄権では前者が存在しても後者はnull。列の意味を混ぜない。
        if row['prediction_kind']!='Abstain' or row['R_used'] is not None:
            assert value['chosen_R']==row['R_used'],(t,'再解析の回答に使った定義が本物と違う')
        assert value['original_hit']==bool(row['hit'])
        pertrial[t]={'trial':t,'seed':seed,'shop_cue':row['shop_cue'],'shop_type':row['shop_type'],'held_out_is_door':row['held_out_is_door'],'hit':row['hit'],'prediction_kind':row['prediction_kind'],'R_used':row['R_used'],'abstain_reason':row['abstain_reason'],'classification':''}
        if row['prediction_kind']!='Abstain' and row['hit']!=1:
            category='選び間違い' if value['correct_gate_passed'] else '区別の喪失'
            pertrial[t]['classification']=category
            allclasses[row['shop_cue']][category]+=1
            if row['held_out_is_door']:classes[row['shop_cue']][category]+=1
assert seen==meta.keys()
for cue in ('e','n'):assert sum(classes[cue].values())==counts[cue]['外れ']
for cue in ('e','n'):assert sum(allclasses[cue].values())==allcounts[cue]['外れ']

# 初回の登録の瞬間と、同じ試行のBの後は、別の表にする。
births=[];birth_by_trial={}
groups=defaultdict(Counter)
for t,row in meta.items():
    event=row['registration_event']
    if not event or event.get('was_extension'):continue
    base=event.get('base_written_at')
    key=(meta[base]['shop_cue'] if base in meta else '不明',row['shop_cue'])
    signals=[c for c in event['constituents'] if c['predicate'] in ('sig_n','sig_e')]
    group=groups[key];group['誕生数']+=1;group['シール席ありの定義数']+=bool(signals)
    value={'trial':t,'R':event['R'],'base_trial':base,'base_day':key[0],'current_day':key[1],
           'signals':[],'after_B':[]}
    for c in signals:
        # 生まれた登録でのaliveを実際の記録から確認。H/UをFへ推測しない。
        assert c['alive'],(t,c,'登録時にFでない席の履歴はこの登録記録に無い')
        group['登録直後_F']+=1
        value['signals'].append({'slot':c['slot_index'],'name':c['predicate'],'state':'F'})
    births.append(value);birth_by_trial[t]=value
states=next(output.glob('side/**/*.sme.states.jsonl.gz'))
post_count=0
with gzip.open(states,'rt') as stream:
    for line in stream:
        encoded=json.loads(line)
        if encoded['kind']!='post':continue
        post_count+=1;t=encoded['trial']
        if t not in birth_by_trial:continue
        value=birth_by_trial[t];state=plain(encoded['state']);d=state['definitions'].get(value['R'])
        group=groups[(value['base_day'],value['current_day'])]
        for signal in value['signals']:
            if d is None:status='定義が同じ試行に退役'
            else:
                row=next(r for r in d['constituents'] if r['slot_index']==signal['slot'])
                status='F' if row['alive'] else ('H' if (value['R'],signal['slot']) in state['slot_history'] else 'U')
            value['after_B'].append({'slot':signal['slot'],'name_at_registration':signal['name'],'state':status})
            group['同試行の忘却後_'+status]+=1
assert post_count==trials
(folder/'births.json').write_text(json.dumps({'births':births,'groups':[{'base_day':k[0],'current_day':k[1],**v} for k,v in sorted(groups.items())]},ensure_ascii=False,indent=2)+'\n')
side=next(output.glob(f'side/**/seed{seed:03d}.jsonl'))
bits=[];defs=[]
for line in side.open():
    value=json.loads(line)
    if value.get('kind')=='v39':bits.append(value['bits_after']);defs.append(value['defs'])
assert len(bits)==len(defs)==trials
assert sorted(meta)==list(range(trials)), '台帳のprediction_orderは0起点'
for i,t in enumerate(sorted(meta)):
    pertrial[t]['trial_number']=t+1
    pertrial[t]['memory_bits']=bits[i];pertrial[t]['definitions']=defs[i]
with (folder/'trials.csv').open('w',newline='') as out:
    writer=csv.DictWriter(out,fieldnames=list(pertrial[min(pertrial)]));writer.writeheader();writer.writerows(pertrial[t] for t in sorted(meta))
manifest=json.loads(next((output/'manifest.jsonl').open()))
actual=json.loads((folder/'run_complete.json').read_text())
rows=['全課題を分母とした数。ドア課題の数は続く別表に示す。','',
      '|日|全課題数|正解|外れ|黙り|選び間違い|区別の喪失|','|---|---:|---:|---:|---:|---:|---:|']
for cue,day in [('e','例外'),('n','通常')]:
    c=allcounts[cue]
    rows.append('|'+day+'|'+str(sum(c.values()))+'|'+'|'.join(str(c[k]) for k in ('正解','外れ','黙り'))+'|'+str(allclasses[cue]['選び間違い'])+'|'+str(allclasses[cue]['区別の喪失'])+'|')
rows+=['','|日|ドア課題数|正解|外れ|黙り|選び間違い|区別の喪失|','|---|---:|---:|---:|---:|---:|---:|']
for cue,day in [('e','例外'),('n','通常')]:
    values=[sum(counts[cue].values()),counts[cue]['正解'],counts[cue]['外れ'],counts[cue]['黙り'],classes[cue]['選び間違い'],classes[cue]['区別の喪失']]
    rows.append('|'+day+'|'+'|'.join(str(x) for x in values)+'|')
rows+=['','|基の材料の日|今の材料の日|誕生数|シール席あり定義数|登録直後F/H/U|同試行の忘却後F/H/U|同試行に退役|',
       '|---|---|---:|---:|---|---|---:|']
for key,c in sorted(groups.items()):
    before='/'.join(str(c['登録直後_'+s]) for s in ('F','H','U'))
    after='/'.join(str(c['同試行の忘却後_'+s]) for s in ('F','H','U'))
    rows.append('|'+key[0]+'|'+key[1]+'|'+str(c['誕生数'])+'|'+str(c['シール席ありの定義数'])+'|'+before+'|'+after+'|'+str(c['同試行の忘却後_定義が同じ試行に退役'])+'|')
rows+=['','材料の日のeは例外、nは通常。登録直後はregistration_event、忘却後は同じ試行のsme.statesのpostを使用。',
       f"全{trials}試行の記憶総ビット（v39のbits_after）の平均{sum(bits)/len(bits):.6f}、最後{bits[-1]}。定義数の平均{sum(defs)/len(defs):.6f}、最後{defs[-1]}。"]
result={'seed':seed,'trials':trials,'days':{cue:{**counts[cue],**classes[cue]} for cue in ('e','n')},
        'all_task_days':{cue:{**allcounts[cue],**allclasses[cue]} for cue in ('e','n')},'birth_groups':[{'base_day':k[0],'current_day':k[1],**v} for k,v in sorted(groups.items())],
        'memory_bits_mean':sum(bits)/len(bits),'memory_bits_final':bits[-1],'definitions_mean':sum(defs)/len(defs),'definitions_final':defs[-1],
        'wall_seconds':actual['run']['wall_seconds'],'peak_rss_mb':actual['peak_rss_mb'],'table':'\n'.join(rows),
        'prediction_and_selection_mismatches':0,'classification_tool':'tools/selcands_sme.py',
        'replay':json.loads(next((analysis/'manifest.jsonl').open()))['smereplay']}
assert result['replay']['replayed'] and result['replay']['predictions']==trials and result['replay']['updates']==trials
(folder/'summary.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
files=sorted(p for p in output.rglob('*') if p.is_file())
ah=sorted(p for p in analysis.rglob('*') if p.is_file())
hashes={'original_output':str(output),'analysis_output':str(analysis),'files':{str(p.relative_to(output)):rawhash(p) for p in files},
        'analysis_files':{str(p.relative_to(analysis)):rawhash(p) for p in ah}}
body=hashlib.sha256()
with gzip.open(ledger,'rb') as stream:
    next(stream)
    while data:=stream.read(1024*1024):body.update(data)
hashes['ledger_body_sha256']=body.hexdigest()
(folder/'artifacts_sha256.json').write_text(json.dumps(hashes,ensure_ascii=False,indent=2)+'\n')
print(folder.name,'集計完了。再生の不一致0、種',seed,flush=True)

(folder/'table.md').write_text(result['table']+'\n')
(folder/'analysis_complete.json').write_text(json.dumps({'passed':True,'trials':trials,'seed':seed,'classification_tool_sha256':rawhash(Path(json.loads((folder/'run_spec.json').read_text())['source'])/'tools/selcands_sme.py'),'native_ledger_body_sha256':hashes['ledger_body_sha256']},indent=2)+'\n')

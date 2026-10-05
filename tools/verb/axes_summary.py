"""承認された二軸を、段3と同じ区間・分類で集計する。模型への書戻しはしない。"""
from __future__ import annotations
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from aggregate import aggregate, fmt, ratio, write_csv
from followup import REASONS
from verbworld import training_items


def read_csv(path):
    if not path.exists() or not path.stat().st_size:
        return []
    return list(csv.DictReader(path.open()))


def record_path(base, run):
    return base/'existing'/run['existing_label'] if run.get('existing_label') else base/run['axis']/run['label']/'record'


def summarize(base, plan, axis):
    base=Path(base)
    runs=[r for r in plan['runs']+plan['reuse'] if r['axis']==axis]
    ap={'runs':[{**r,'arm':r['group']} for r in runs],'baseline':'not_requested_for_axes'}
    output=aggregate(base/axis,ap)
    complete=[r for r in runs if (base/axis/r['label']/'complete.json').exists()]
    extras=[r for r in complete if (record_path(base,r)/'record_checks.json').exists()]
    silence=defaultdict(Counter)
    recover=defaultdict(Counter)
    per_seed, positions, records, novel=[],[],[],[]
    for run in complete:
        analysis=json.loads((base/axis/run['label']/'analysis/summary.json').read_text())
        group=run['group']
        recroot=record_path(base,run)
        qtimes={}
        if (recroot/'record_checks.json').exists():
            rec=json.loads((recroot/'record_checks.json').read_text())
            qtimes=rec['query_times']
            records.append({'condition':group,'seed':run['seed'],'arm':run['arm'],'tau':run['tau'],'past_p':run['p'],
                            **{k:v for k,v in rec.items() if k not in ('seed','query_times')}})
            for row in read_csv(recroot/'silence.csv'):
                silence[(group,row['phase'],row['class'])].update({k:int(v) for k,v in row.items() if k not in ('phase','class') and v})
            novel += [{'condition':group,'seed':run['seed'],**r} for r in read_csv(recroot/'novel_IRR_selected.csv')]
        events=Counter(e['verb'] for e in analysis['recovery'])
        for k in range(33,41):
            v=f'V{k:02d}'
            questions=sum(row['queries'] for row in analysis['overregularization'] if row['verb']==v)
            if qtimes:
                assert questions == len(qtimes.get(v,[]))
            row={'condition':group,'seed':run['seed'],'verb':v,'past_queries':questions,'recovery_events':events[v],
                 'events_per_past_query':ratio(events[v],questions)}
            per_seed.append(row)
            recover[(group,v)].update({'past_queries':questions,'recovery_events':events[v]})
        for e in analysis['recovery']:
            times=qtimes.get(e['verb'],[])
            positions.append({'condition':group,'seed':run['seed'],**e,
                              **{k+'_query':times.index(e[k])+1 if times else None for k in ('correct_before','REG_start','correct_after')}})
    perverb=[]
    for (g,v),c in sorted(recover.items()):
        perverb.append({'condition':g,'verb':v,**dict(c),'events_per_past_query':ratio(c['recovery_events'],c['past_queries'])})
    write_csv(output/'recovery_per_seed_verb.csv',per_seed)
    write_csv(output/'recovery_per_verb.csv',perverb)
    write_csv(output/'recovery_query_positions.csv',positions)
    rows=[]
    for (g,phase,cls),c in sorted(silence.items()):
        rows.append({'condition':g,'phase':phase,'class':cls,**dict(c),'abstain_rate':ratio(c['abstain'],c['queries'])})
    write_csv(output/'silence.csv',rows)
    write_csv(output/'sequence_checks.csv',records)
    write_csv(output/'novel_IRR_selected_per_seed.csv',novel)
    ng=Counter()
    for row in novel:
        ng[(row['condition'],row['name_state'],row['past_state'],row['past_stored_answer'],row['probe_answer'],row['source'])]+=int(row['count'])
    write_csv(output/'novel_IRR_selected.csv',[{'condition':g,'name_state':n,'past_state':p,'past_stored_answer':a,
                'probe_answer':b,'source':s,'count':c} for (g,n,p,a,b,s),c in sorted(ng.items())])
    freq=defaultdict(Counter)
    for row in read_csv(output/'overregularization_per_verb.csv'):
        freq[(row['arm'],row['verb'])].update({k:int(row[k]) for k in ('exposure','queries','correct','REG','abstain','other')})
    probs={v.name:v.probability for v in training_items()}
    write_csv(output/'frequency_effect.csv',[{'condition':g,'verb':v,'design_probability':probs[v],**dict(c),
            'marcus_rate':ratio(c['REG'],c['correct']+c['REG']),'REG_all_queries_rate':ratio(c['REG'],c['queries'])} for (g,v),c in sorted(freq.items())])
    checks={'axis':axis,'new_completed':sum(not r.get('existing_label') for r in complete),
            'reused_completed':sum(bool(r.get('existing_label')) for r in complete),'record_reads':len(extras),
            'new_planned':sum(not r.get('existing_label') for r in runs)}
    if len(records)==len(runs):
        for seed in range(1,6):
            sr=[r for r in records if r['seed']==seed]
            assert len({r['appearance_sha256'] for r in sr})==1
            for p in {r['past_p'] for r in sr}:
                assert len({r['past_question_sha256'] for r in sr if r['past_p']==p})==1
        checks['appearance_and_question_checks']=True
    (output/'axis_checks.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2)+'\n')
    legend=[{'condition':r['group'],'arm':r['arm'],'U':r['U'],'tau':r['tau'],'past_p':r['p'],'existing':bool(r.get('existing_label'))} for r in runs if r['seed']==1]
    write_csv(output/'conditions.csv',legend)
    md=['', '|条件名|保持|U|τ|過去形の質問p|既存の走行|','|---|---|---|---:|---|---|']
    for r in legend:
        md.append(f"|{r['condition']}|{r['arm']}|{r['U']}|{r['tau']}|{r['past_p']}|{'使用' if r['existing'] else '新規'}|")
    md+=['', (output/'tables.md').read_text(), '### 崩れと回復を、語ごとの過去形質問数で割った値','',
         '|条件|語|完了回数|過去形質問数|回数／質問数|','|---|---|---:|---:|---:|']
    for r in perverb:
        md.append(f"|{r['condition']}|{r['verb']}|{r['recovery_events']}|{r['past_queries']}|{fmt(r['events_per_past_query'])}|")
    md+=['','語別の正答→REG→再正答は段3の正答/REG部分列の定義のまま。質問数は黙り・その他を含む、その語の全過去形質問。種別の比率と、三時点をその語の質問番号（1始まり）に置き換えた表も保存。', '',
         '### 黙りの理由（記録にある区分）','', '|条件|対象|動詞群|質問|黙り|原型無し|定義無し|構造の門|発話の門|投影・穴埋め無し|欠けた席の候補無し|同点・曖昧|','|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|']
    for r in rows:
        vals=[r.get('reason:'+reason,0) for reason in REASONS]
        md.append(f"|{r['condition']}|{r['phase']}|{r['class']}|{r['queries']}|{r.get('abstain',0)}|"+'|'.join(map(str,vals))+'|')
    md+=['','U/H同点と発話の門の補助記録はsilence.csvのdetail欄。試験に細分の記録が無い件は未記録のまま。新語は学習に出ない（学習中の質問・黙りはいずれも0）。', '',
         '### 新語の不規則回答で選ばれた定義','', '|条件|名前の席|過去形の席|その席の保存された答え|試験の答え|答えの出所|件数|','|---|---|---|---|---|---|---:|']
    for (g,n,p,a,b,s),c in sorted(ng.items()):
        md.append(f'|{g}|{n}|{p}|{a}|{b}|{s}|{c}|')
    md+=['','名前と過去形の席は誕生した場面の関係IDで同定。Fは生きた述語、Hは保存された履歴の一意の最多、U又は履歴同点はnone_or_tie。実際の試験回答・出所と別欄で残し、予測をやり直していない。', '']
    (output/'axis_tables.md').write_text('\n'.join(md))
    return output, checks


def existing_novel_table(base, plan):
    base=Path(base)
    groups=Counter()
    for run in plan['runs']:
        root=base/'existing'/run['label']
        for row in read_csv(root/'novel_IRR_selected.csv'):
            groups[(run['arm'],run['U'],row['name_state'],row['past_state'],row['past_stored_answer'],row['probe_answer'],row['source'])]+=int(row['count'])
    output=base/'existing_aggregate'
    output.mkdir(exist_ok=True)
    write_csv(output/'novel_IRR_selected.csv',[{'arm':a,'U':u,'name_state':n,'past_state':p,'past_stored_answer':s,'probe_answer':b,'source':src,'count':c} for (a,u,n,p,s,b,src),c in sorted(groups.items())])
    md=['### 段3既存30本：新語の不規則回答の選択定義','', '|保持|U|名前の席|過去形の席|その席の保存された答え|試験の答え|出所|件数|','|---|---|---|---|---|---|---|---:|']
    for (a,u,n,p,s,b,src),c in sorted(groups.items()):
        md.append(f'|{a}|{u}|{n}|{p}|{s}|{b}|{src}|{c}|')
    md+=['','試験tはt試行を終えた直後の保存状態。Rの名前と誕生時点を状態と照合した。名前・過去形の席を誕生場面の関係IDから同定し、F/H/Uと履歴を読むだけ。保存された答え（Fの述語又はHの一意最多）と、実際に記録された回答・出所を分ける。予測・学習は再実行していない。個別の記録は各本のnovel_IRR_cases.jsonl.gz。', '']
    (output/'tables.md').write_text('\n'.join(md))
    return output

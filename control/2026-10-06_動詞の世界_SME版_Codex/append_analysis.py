"""移した分類道具の読取検査と、記録だけから作った数の表を報告する。"""
from pathlib import Path
from collections import Counter,defaultdict
import csv
import hashlib
import json
import sys

root=Path(__file__).resolve().parent
repo=root.parent/'report-results';name='2026-10-06_動詞の世界_SME版_Codex'
dest=repo/'control'/name
reader=root/'pilot_analysis'
status=json.loads((reader/'reader_status.json').read_text())
report=repo/'control'/f'{name}.md'
if status['exit_code']:
    text=(reader/'run.log').read_text().replace(str(root.parents[1]),'$WORKSPACE').replace(str(Path.home()),'$USER_HOME')
    (dest/'analysis_stop.txt').write_text(text)
    report.write_text(report.read_text()+f'\n完走記録を使う分類道具の読取検査は停止した。模型の測定一本は完走済み。未完の分類や率は確定しない。[停止の記録]({name}/analysis_stop.txt)。模型の追加走行は行っていない。\n')
    raise SystemExit(0)
summary=json.loads((reader/'output/summary.json').read_text())
assert summary['checks']['ledger_rows']==5000 and summary['checks']['world_rows']==5000 and summary['checks']['state_hashes']==5000
(dest/'analysis_checks.json').write_text(json.dumps(summary['checks'],indent=2)+'\n')

def table(filename,rows):
    if not rows:
        (dest/filename).write_text('');return
    with (dest/filename).open('w',newline='') as f:
        keys=list(dict.fromkeys(k for r in rows for k in r));w=csv.DictWriter(f,keys);w.writeheader();w.writerows(rows)

table('overregularization_per_verb.csv',summary['overregularization'])
table('recovery_events.csv',summary['recovery'])
table('answering.csv',summary['answering'])
table('memory.csv',summary['memory'])
table('novel_per_time.csv',summary['novel'])
table('classification.csv',[{'classification':k,'count':v} for k,v in summary['classification'].items()])
derived=[]
for path in sorted((reader/'output').iterdir()):
    if not path.is_file():continue
    digest=hashlib.sha256()
    with path.open('rb') as stream:
        while chunk:=stream.read(1024*1024):digest.update(chunk)
    derived.append({'path':str(path.relative_to(root.parents[1])),'bytes':path.stat().st_size,'sha256':digest.hexdigest()})
table('analysis_outputs_sha256.csv',derived)
bins=defaultdict(Counter)
for r in summary['overregularization']:
    bins[r['bin']].update({k:r[k] for k in ('queries','correct','REG','abstain','other')})
rows=[]
for b,c in sorted(bins.items()):
    den=c['correct']+c['REG'];n=c['queries']
    rows.append({'start':b*500,'end':(b+1)*500,**dict(c),'marcus_denominator':den,
                 'marcus_rate':c['REG']/den if den else None,'REG_all_queries_rate':c['REG']/n if n else None})
table('overregularization_bins.csv',rows)
lines=['','## 分類道具の既存記録での検査','',
       f"5,000試行の世界・真値・提示、研究者の四欄、予測後状態のsha256を全件再現した。学習中のREG回答{summary['checks']['candidate_replays']}件では、予測前の記憶を記録から復元し、SMEの予測と選ばれた定義・答え・引数を再現した上で、各候補のSMEのN3と門を数え直した。これは保存した記録の読取検査で、模型の学習走行をもう一本追加したものではない。[全件数の検査]({name}/analysis_checks.json)。", '',
       '|学習試行の区間（0始まり・右端を含まない）|不規則の過去形質問|正解|REG|黙り|他の誤答|REG/(正解+REG)|REG/全質問|',
       '|---|---:|---:|---:|---:|---:|---:|---:|']
for r in rows:
    rates=[('—' if r[k] is None else f'{r[k]:.6f}') for k in ('marcus_rate','REG_all_queries_rate')]
    lines.append(f"|{r['start']}–{r['end']}|{r['queries']}|{r['correct']}|{r['REG']}|{r['abstain']}|{r['other']}|{rates[0]}|{rates[1]}|")
novel=Counter()
for r in summary['novel']:
    novel.update({k:r.get(k,0) for k in ('REG','IRR','abstain','other')})
answer=Counter()
for r in summary['answering']:answer.update({k:r.get(k,0) for k in ('trials','answered','abstain')})
lines += ['',f"全5,000問の回答{answer['answered']}、黙り{answer['abstain']}。新語8個×50時点の400問はREG {novel['REG']}、不規則形 {novel['IRR']}、黙り {novel['abstain']}、その他 {novel['other']}。崩れと回復の完了は{len(summary['recovery'])}件。過剰な規則化の分類は{json.dumps(summary['classification'],ensure_ascii=False)}。", '',
          f'[語ごとの率と分母]({name}/overregularization_per_verb.csv)、[区間の率]({name}/overregularization_bins.csv)、[回復の三時点]({name}/recovery_events.csv)、[記憶量]({name}/memory.csv)、[新語の時点別回答]({name}/novel_per_time.csv)。新語には正誤の基準を置いていない。', '']
report.write_text(report.read_text()+'\n'.join(lines))
print(json.dumps({'checks':summary['checks'],'classes':summary['classification'],'novel':dict(novel),'answer':dict(answer)},ensure_ascii=False))

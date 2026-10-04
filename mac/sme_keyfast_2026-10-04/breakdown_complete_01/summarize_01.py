"""診断の秒と、本番相当の実時間を混ぜず、数だけの表を作る。"""
from pathlib import Path
from collections import Counter, defaultdict
import csv
import json
import pstats

ROOT = Path(__file__).resolve().parent
assert json.loads((ROOT / 'early_complete_01.json').read_text())['passed']
assert json.loads((ROOT / 'late_replay_result_01.json').read_text())['passed']
components = json.loads((ROOT / 'canonical_components_result_01.json').read_text())
assert components['passed']
callers, intervals, states = defaultdict(Counter), defaultdict(Counter), Counter()
for label in ('A', 'C'):
    path = ROOT / ('early_' + label + '_02') / 'trials.jsonl'
    for line in path.read_text().splitlines():
        row = json.loads(line)
        block = f"{row['trial']//50*50+1}〜{row['trial']//50*50+50}"
        intervals[label, block]['trial_count'] += 1
        intervals[label, block]['seconds_diagnostic'] += row['seconds_diagnostic']
        for caller, data in row['callers'].items():
            for field in ('matches', 'key_calls', 'seconds', 'key_seconds'):
                callers[label, 'early', caller][field] += data[field]
                intervals[label, block][field] += data[field]
            callers[label, 'early', caller]['equal_score_groups'] += sum(data['equal_score_groups'].values())
            callers[label, 'early', caller]['draw_groups'] += sum(data['draw_groups'].values())
            intervals[label, block]['equal_score_groups'] += sum(data['equal_score_groups'].values())
            intervals[label, block]['draw_groups'] += sum(data['draw_groups'].values())
            for scope in ('all', 'varying'):
                for category, count in data['equal_score_states_' + scope].items():
                    states[label, 'early', caller, scope, category] += count
for line in (ROOT / 'late_match_rows_01.jsonl').read_text().splitlines():
    row = json.loads(line)
    caller = row['caller']
    block = '1500〜1509' if row['trial'] < 1509 else '1731〜1740'
    for field in ('matches', 'key_calls', 'seconds', 'key_seconds'):
        callers['A', 'late', caller][field] += row[field]
        intervals['A', block][field] += row[field]
    for name in ('equal_score_groups', 'draw_groups'):
        callers['A', 'late', caller][name] += sum(row[name].values())
        intervals['A', block][name] += sum(row[name].values())
    for scope in ('all', 'varying'):
        for category, count in row['equal_score_states_' + scope].items():
            states['A', 'late', caller, scope, category] += count
for block in ('1500〜1509', '1731〜1740'):
    intervals['A', block]['trial_count'] = 10


def csvfile(name, header, rows):
    with (ROOT / name).open('w', newline='') as output:
        writer = csv.writer(output)
        writer.writerow(header)
        writer.writerows(rows)


caller_rows = []
for (label, period, caller), data in sorted(callers.items()):
    n = data['matches']
    caller_rows.append([label, period, caller, n, data['equal_score_groups'], data['draw_groups'],
                        data['key_calls'], data['key_calls']/n, data['seconds']/n, data['key_seconds']/n])
csvfile('caller_counts_01.csv', ['arm','period','caller','matches','equal_score_groups','draw_groups','key_calls',
                               'keys_per_match','diagnostic_seconds_per_match','key_diagnostic_seconds_per_match'], caller_rows)
interval_rows = []
for (label, block), data in intervals.items():
    n = data['matches']
    interval_rows.append([label, block, data['trial_count'], n, n/data['trial_count'], data['equal_score_groups'],
                          data['draw_groups'], data['key_calls'], data['key_calls']/n if n else 0,
                          data['seconds']/n if n else 0])
csvfile('interval_counts_01.csv', ['arm','trial_interval','trials','matches','matches_per_trial','equal_score_groups',
                                 'draw_groups','key_calls','keys_per_match','diagnostic_seconds_per_match'], interval_rows)
csvfile('tie_states_01.csv', ['arm','period','caller','state_scope','phase_and_states','groups'],
        [[*key, value] for key, value in sorted(states.items())])

text = ['\n## 遅さの内訳：追加の小計測完了\n',
    '元の6e93e0bを変更せずA・C各200試行。外部の計測台本だけで照合の実計算・キー・同点を数えた。'
    '両方の台帳本体は既存200試行と全バイト一致。cProfile付きの秒は診断用で、速さの比較には使わない。\n',
    '後半の既存Aの共有cacheの増分12039件が、cProfileの実計算12039件と一致。'
    '1500〜1509・1731〜1740の20試行分985照合を抽出。977件は保存された対応・点・抽選と一致。'
    '自己照合の元の直前乱数が無く抽選を含む8件は除いた。後半の秒は照合だけの再計測であり、試行全体の秒ではない。\n',
    '同点組は一回の並べ替えで点が等しい候補が二つ以上あった組。'
    'draw_groupsは構造の鍵でも区別できず、元の規則で実際に抽選した組。両方を分けて数えた。\n',
    '|腕|試行の区間|試行数|照合の実計算|一試行の照合|点が同じ組|実際の抽選の組|_key|照合一回の_key|診断の秒/照合|',
    '|---|---|---:|---:|---:|---:|---:|---:|---:|---:|']
for row in interval_rows:
    text.append('|'+ '|'.join(str(x) if not isinstance(x,float) else f'{x:.6f}' for x in row) +'|')
text += ['\n|腕|区間|呼び出し元|照合の実計算|点が同じ組|抽選の組|_key|照合一回の_key|診断の秒/照合|_keyの診断秒/照合|',
         '|---|---|---|---:|---:|---:|---:|---:|---:|---:|']
for row in caller_rows:
    text.append('|'+ '|'.join(str(x) if not isinstance(x,float) else f'{x:.6f}' for x in row) +'|')
text += ['\nFは固定名、Hは名前の履歴、Uは名前を忘れた席。'
    '席の内訳は、同点組の候補の全部に現れる関係の席（all）と、候補間で対応が違う部分に現れる席（varying）の二表。'
    '一組でF/H/Uが混在するものも別に数える。原因の断定には使わない。全表はtie_states_01.csv。\n',
    '色の細分は、つながりで区別できる頂点を分ける処理。個別化は、それでも同じ形の頂点を一つずつ分けて探索する処理。'
    '保存した正準形の入力と、対称な小例をsys.setprofileで観測し、元の返り値と全件一致。'
    'refineの包含秒とsearchの子の処理を除いた秒を分け、時間を重ねて足さない。観測の負担を含む診断の秒。\n',
    '|入力の組|入力数|細分の回数|細分の包含秒|個別化の節点|試した子の数|searchの子を除いた秒|最大の再帰の深さ|',
    '|---|---:|---:|---:|---:|---:|---:|---:|']
for name, data in components['summary'].items():
    text.append(f"|{name}|{data.get('inputs',1)}|{data.get('refine_entries',0)}|{data.get('refine_inclusive_seconds',0):.6f}|"
                f"{data.get('individualization_nodes',0)}|{data.get('branch_attempts',0)}|{data.get('search_exclusive_seconds',0):.6f}|{data.get('max_search_depth',0)}|")
text += ['\n初回の外部台本は子プロセスのargvから出力先を取ったためNotADirectoryErrorで予測前に終了（0試行）。'
         '失敗した記録を保持し、出力先の受け渡しだけを環境変数に直し、別の出力先で計測した。模型のコードは変更していない。\n']
(ROOT / 'report_addendum2_01.md').write_text('\n'.join(text)+'\n')
(ROOT / 'summary_01.json').write_text(json.dumps({'passed':True,'caller_rows':len(caller_rows),
    'interval_rows':len(interval_rows),'state_rows':len(states),'canonical_components':components},ensure_ascii=False,indent=2)+'\n')
print('内訳の表を保存', len(caller_rows), len(interval_rows), len(states), flush=True)

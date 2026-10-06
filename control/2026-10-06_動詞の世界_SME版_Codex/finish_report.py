"""完走済みの一本の記録から、時間・容量・仮定した所要を表にする。"""
from pathlib import Path
from collections import Counter, defaultdict
import csv
import hashlib
import json
import re
import shutil
import subprocess
import sys

root=Path(__file__).resolve().parent
ws=root.parents[1]
repo=root.parent/'report-results'
name='2026-10-06_動詞の世界_SME版_Codex'
dest=repo/'control'/name
pilot=root/'pilot_A_global_s01';out=pilot/'output'
assert json.loads((root/'status.json').read_text())['state']=='pilot_complete'
manifest=[json.loads(x) for x in (out/'manifest.jsonl').read_text().splitlines()]
assert len(manifest)==1 and manifest[0]['trial_count']==5000 and not manifest[0].get('error')
manifest=manifest[0]
points=[json.loads(x) for x in (out/'timing/seed001.jsonl').read_text().splitlines()]
assert [p['completed_trials'] for p in points]==[1000,2000,3000,4000,5000]
log=(pilot/'run.log').read_text()
m=re.search(r'^\s*([0-9.]+) real\s+([0-9.]+) user\s+([0-9.]+) sys',log,re.M)
rss=re.search(r'^\s*(\d+)\s+maximum resident set size',log,re.M)
assert m and rss
time_l_real,user,system=map(float,m.groups())
worker_max=manifest['peak_rss_mb']
supervised=json.loads((pilot/'result.json').read_text())
real=supervised['wall_seconds']
resources=[json.loads(x) for x in (pilot/'resources.jsonl').read_text().splitlines()]
paused=supervised['paused_seconds']
active_A=real-paused
assert active_A>0
assert real >= points[-1]['elapsed_seconds'] and user <= real

# 自分の待機を除いた時間は、記録した停止・再開の範囲だけを差し引く。
intervals=[]
start=None
for r in resources:
    if r['event']=='paused':start=r['epoch_seconds']
    elif r['event']=='resumed':
        assert start is not None
        intervals.append((start,r['epoch_seconds']));start=None
assert start is None
began=supervised['started_epoch']
for p in points:
    overlap=sum(max(0,min(b,p['epoch_seconds'])-max(a,began)) for a,b in intervals)
    p['own_pause_seconds_through_checkpoint']=overlap
    p['elapsed_minus_own_pause_seconds']=p['elapsed_seconds']-overlap
    p['cumulative_max_rss_MB']=p['cumulative_max_rss_bytes']/1e6

def csv_write(path, rows):
    if not rows:
        path.write_text('');return
    keys=list(dict.fromkeys(k for r in rows for k in r))
    with path.open('w',newline='') as f:
        writer=csv.DictWriter(f,keys);writer.writeheader();writer.writerows(rows)

def public(s):
    return s.replace(str(ws),'$WORKSPACE').replace(str(Path.home()),'$USER_HOME')

sizes=Counter();file_rows=[]
reuse_hashes='--reuse-raw-hashes' in sys.argv
for p in sorted(out.rglob('*')):
    if not p.is_file():continue
    rel=p.relative_to(out)
    n=p.stat().st_size;sizes[rel.parts[0]]+=n
    if reuse_hashes:continue
    h=hashlib.sha256()
    with p.open('rb') as f:
        while x:=f.read(1024*1024):h.update(x)
    file_rows.append({'path':str(p.relative_to(ws)),'bytes':n,'sha256':h.hexdigest()})
# 関門の原本のファイルも圧縮された実ファイルのsha256を残す。
for p in sorted((root/'gates').rglob('*')):
    if not p.is_file() or 'output' not in p.parts:continue
    if reuse_hashes:continue
    h=hashlib.sha256()
    with p.open('rb') as f:
        while x:=f.read(1024*1024):h.update(x)
    file_rows.append({'path':str(p.relative_to(ws)),'bytes':p.stat().st_size,'sha256':h.hexdigest()})
if reuse_hashes:
    with (dest/'raw_files_sha256.csv').open(newline='') as stream:
        file_rows=list(csv.DictReader(stream))
    for row in file_rows:
        assert (ws/row['path']).stat().st_size==int(row['bytes'])
else:
    csv_write(dest/'raw_files_sha256.csv',file_rows)
csv_write(dest/'timing_1000.csv',points)
csv_write(dest/'output_sizes.csv',[{'category':k,'bytes':v,'MB':v/1e6,'GiB':v/2**30} for k,v in sorted(sizes.items())])
for f in ('result.json','resources.jsonl','spec.json'):
    (dest/('pilot_'+f)).write_text(public((pilot/f).read_text()))
(dest/'pilot_manifest.json').write_text(public(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n'))
(dest/'pilot_flag.json').write_text(public((out/'flag.json').read_text()))
(dest/'pilot_time_l.txt').write_text( '\n'.join(line for line in log.splitlines() if re.match(r'^\s+[0-9]',line))+'\n')

# 段階に分けた推測：C/Dの動詞版は未測定。Aの一本を全条件に当てはめた値を示す。
forecasts=[]
for nparallel in (1,2,4,8):
    forecasts.append({'scenario':'全120本が今回のAの自分の一時停止を差し引いた秒と同じ。追加の受付待機なしという仮定',
                      'parallel':nparallel,'runs':120,'A_seconds_wall_measured':real,'A_seconds_minus_own_pause_derived':active_A,
                      'total_hours_estimated':(120+nparallel-1)//nparallel*active_A/3600,
                      'hours_if_same_pause_and_wall_time_repeats_estimated':(120+nparallel-1)//nparallel*real/3600,
                      'output_GiB_estimated':sum(sizes.values())*120/2**30,
                      'C_D_verb_world_measured':False,'other_seeds_measured':False})
csv_write(dest/'forecast120.csv',forecasts)
summary={'supervised_total_wall_seconds_measured':real,'worker_seconds_through5000_measured':points[-1]['elapsed_seconds'],
         'time_l_reported_real_seconds_rejected':time_l_real,'time_l_real_seconds_used':False,
         'user_seconds_time_l':user,'system_seconds_time_l':system,
         'worker_peak_rss_MB':worker_max,'command_max_process_rss_bytes_time_l':int(rss.group(1)),
         'supervised_wall_seconds':supervised['wall_seconds'],'own_paused_seconds':paused,'wall_minus_own_pause_seconds_derived':active_A,
         'output_bytes':sum(sizes.values()),'output_GiB':sum(sizes.values())/2**30,
         'checkpoints':points,'forecast120_A_only_assumption':forecasts}
(dest/'measurement.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')

report=repo/'control'/f'{name}.md'
lines=['','## 一本の測定の完了','',
       f'種1の5,000試行が終了コード0で完走。workerの5,000試行までの実測は**{points[-1]["elapsed_seconds"]:.3f}秒（{points[-1]["elapsed_seconds"]/60:.2f}分）**、起動と終了検出を含む監督の単調時計では**{real:.3f}秒**。個体workerの最大常駐は**{worker_max:.1f}MB**。/usr/bin/time -lの最大常駐も{int(rss.group(1))/1e6:.3f}MB。模型の出力先output/は**{sum(sizes.values()):,}バイト（{sum(sizes.values())/2**30:.3f}GiB）**。追加の120本は走らせていない。', '',
       f'/usr/bin/time -lのreal欄は{time_l_real:.2f}秒で、同じ出力のuser {user:.2f}秒を下回り、開始12:49:37・終了15:28:58の日時、workerの経過秒、監督の単調時計とも合わない。原因は未特定。このreal欄は総時間や見込みへ採用しない。原本は残した。見込みは終了検出を含む監督の{real:.3f}秒から記録した一時停止だけを差し引く。', '',
       '|完了した試行数|直前の1,000試行の秒|開始からの秒|その時点までの累積最大常駐MB|自分のCPU枠の待機累計秒|',
       '|---:|---:|---:|---:|---:|']
for p in points:
    lines.append(f"|{p['completed_trials']}|{p['interval_seconds']:.3f}|{p['elapsed_seconds']:.3f}|{p['cumulative_max_rss_MB']:.3f}|{p['own_pause_seconds_through_checkpoint']:.3f}|")
lines += ['',f'1,000試行ごとの時間は世界の生成・学習・試験・台帳の追記を含むworkerの計測。外のプロセス実時間には起動・終了処理も含む。監督の終了検出を含む時間は{supervised["wall_seconds"]:.3f}秒、自分の一時停止の合計は{paused:.3f}秒。自分の待機を差し引いた計算値をCSVにも置いた。共有機械のCPU取り合いはその値から除いていない。最大常駐は累積ピークで、各区間だけのピークではない。MBは10進、GiBは2の30乗バイト。', '',
          f'[時間CSV]({name}/timing_1000.csv)、[容量の内訳]({name}/output_sizes.csv)、[全原本のパスとsha256]({name}/raw_files_sha256.csv)、[native manifest]({name}/pilot_manifest.json)、[time -lの実測]({name}/pilot_time_l.txt)。', '',
          '確認値はA・global・種1の一本だけ。120本の内訳は、A/C/DそれぞれU二つ×20種で40本ずつ。一般の所要は40×(t_A+t_C+t_D)。Uと種を同じ所要と仮定した形であり、C/DとU abstain、種2〜20の動詞SME版の時間は未測定。', '',
          '|仮定した同時本数|全120本をAの自分の一時停止を除いた時間と同じに置いた見込み|今回と同じ実時間・一時停止が毎本で起きると置いた見込み|', '|---:|---:|---:|']
for f in forecasts:lines.append(f"|{f['parallel']}|{f['total_hours_estimated']:.3f}時間|{f['hours_if_same_pause_and_wall_time_repeats_estimated']:.3f}時間|")
lines += ['',f'この表は追加の受付待機や並列実行による一本の速度の変化を含まない推測。8本は共有CPUの上限であり、自分に常時8枠が空く見込みではない。容量も全本が今回と同じ記録量と仮定すると{sum(sizes.values())*120/2**30:.3f}GiB。Cの追加診断やDの保持で容量も変わり得る。[推測のCSV]({name}/forecast120.csv)。', '']
previous=report.read_text()
if '## 一本の測定の完了' in previous:
    previous=previous.split('## 一本の測定の完了',1)[0].rstrip()+'\n'
report.write_text(previous+'\n'.join(lines))
print(json.dumps(summary,ensure_ascii=False),flush=True)

"""受付表による再開の結果・試走・見込みを報告へ追記する。模型を呼ばない。"""
from pathlib import Path
import hashlib
import json
import shlex
import shutil
import subprocess

root = Path(__file__).resolve().parent
ev = root/'evidence/resume-jobs-20261004'
out = root/'outputs/resume-jobs-20261004'
report = root/'report/control/2026-10-03_集団化_8体二集団_Codex3.md'
published = root/'report/control/coll8_2026-10-03/resume-jobs-20261004'
published.mkdir(exist_ok=True)
gates = json.loads((ev/'gates.json').read_text())
previous = json.loads((root/'evidence/restart-20261004/gates.json').read_text())
source = gates['source_commit']
assert subprocess.check_output(['git','rev-parse','HEAD'], cwd=root/'source', text=True).strip() == source
status = {'running':'受付表で関門を再開中', 'passed':'全関門合格・cProfileの試走一本を完了して停止',
          'stopped':'不成立で停止'}[gates['status']]
if gates['status'] == 'stopped' and gates.get('gates_status') == 'passed':
    status = '全関門326件合格・cProfile測定器の起動失敗で停止'
recovery_note = ''
if gates.get('supervisor_recovery'):
    recovery = gates['supervisor_recovery']
    recovery_note = f"日付更新後の{recovery['time']}に監督の復旧を行った。旧監督プロセスと自分の模型プロセスが存在せず、個別の受付{recovery['restored_completed_jobs']}件は全て合格・解除済みだったため、その記録から集計を復元した。模型の関門不成立による再試行ではない。模型や価格を変えず、残り11件だけを続け、監督を実行セッションの寿命から独立させた。旧監督の集計は `interrupted-master-20261005.json`、その後の受付と復旧命令は個別の記録に保存した。"
all_specs = []
for file in sorted(ev.glob('*/spec.json')):
    spec = json.loads(file.read_text())
    receipt_file = file.parent/'receipt-command.json'
    if receipt_file.exists():
        spec['receipt_command'] = json.loads(receipt_file.read_text())
    all_specs.append(spec)
for file in ev.iterdir():
    if file.is_file():
        shutil.copy2(file, published/file.name)
    elif file.is_dir():
        shutil.copytree(file, published/file.name, dirs_exist_ok=True)
for name in ('resume_registered_gates_20261004.py','resume_registered_worker_20261004.py',
             'profile_collective_20261004.py','monitor_registered_20261004.py','build_registered_report_20261004.py'):
    shutil.copy2(root/name, published/name)
if (out/'profile_r1_m0.1/profiles').exists():
    shutil.copytree(out/'profile_r1_m0.1/profiles', published/'profiles', dirs_exist_ok=True)

checks = '\n'.join(f"|{c['name']}|{'合格' if c['passed'] else '**不成立**'}|" for c in gates['checks'])
resources = '\n'.join(f"|{r['name']}|{r['elapsed_seconds']:.3f}|{r['rss_sum_peak_bytes']}|{r.get('agent_peak_rss_mb_decimal','午前の証拠を参照')}|{r.get('output_bytes','午前の証拠を参照')}|{r['swap_end_mib']-r['swap_start_mib']:.2f}|"
                      for r in gates['runs'] if r['name'] in gates['completed_new_jobs'])
receipts = []
for spec in all_specs:
    file = ev/spec['name']/'argv.json'
    if not file.exists():
        receipts.append(f"|{spec['name']}|受付待ち|—|—|—|")
        continue
    data = json.loads(file.read_text())
    receipt = data['receipt']
    initial = data['initial']
    receipts.append(f"|{spec['name']}|{receipt['time']}|{sum(r['mem_gb'] for r in receipt['rows']):.1f}|{initial['disk_free_bytes']/2**30:.3f}|{initial['swap_mib']}|")
arguments = '\n\n'.join(f"{s['name']}\n\n```text\ncwd: {root/'source'}\n{shlex.join(s['argv'])}\nextra_env: {json.dumps(s.get('extra_env',{}),ensure_ascii=False)}\n受付: {shlex.join(s['receipt_command']['argv'])}\n```"
                            for s in all_specs if 'receipt_command' in s)
count_rows = []
full = []
for run in (1,2,3):
    for label, m in [('no_comm',0),('comm_m0',0),('comm_m0.1',0.1),('comm_m0.3',0.3)]:
        name = f'{label}_r{run}'
        old = name == 'no_comm_r1'
        directory = root/'evidence/restart-20261004' if old else ev/name
        counts_file = directory/(name+'.counts.json')
        if not counts_file.exists():
            count_rows.append(f'|{name}|未完|—|—|—|—|—|')
            continue
        data = json.loads(counts_file.read_text())
        checks_local = previous['checks'] if old else json.loads((directory/'gates.json').read_text())['checks']
        binomial = next((c for c in checks_local if c['name']==name+' mの二項範囲'),None)
        detail = 'm=0・組間0件' if m == 0 else (str(binomial['central_999_range']) if binomial else '該当する配送なし')
        count_rows.append(f"|{name}|完走|{data['sent']}|{data['within']}|{data['cross']}|{dict(data['receive_results'])}|{detail}|")
        measurement = next(r for r in gates['runs'] if r['name']==name)
        path = root/'outputs/restart-20261004'/name if old else out/name
        sizes = {}
        allocated = 0
        for file in path.rglob('*'):
            if file.is_file():
                key = file.relative_to(path).parts[0]
                sizes[key] = sizes.get(key,0)+file.stat().st_size
                allocated += file.stat().st_blocks*512
        full.append({**measurement, 'q':data['q'], 'm':data['m'], 'run':run,
                     'output_bytes':sum(sizes.values()), 'allocated_bytes':allocated, 'output_parts':sizes})
guards = []
for name in gates['completed_new_jobs']:
    path = out/name
    summary = next((path/'comm').glob('*.summary.json'),None)
    records = (json.loads(summary.read_text())['agents'] if summary is not None else
               [json.loads(line) for line in (path/'manifest.jsonl').read_text().splitlines()])
    guards.append({'name':name,
                   'not_in_dictionary':[r['v39'].get('not_in_dictionary',0) for r in records],
                   'dictionary_checks':[r['v311c'].get('dictionary_checks') for r in records],
                   'manifest_or_summary':str(summary or path/'manifest.jsonl')})
derived = {'full_world2_runs':full, 'world1_measured':False, 'main_run_started':False,
           'completed_new_dictionary_guards':guards}
profile = next((r for r in gates['runs'] if r['name']=='profile_r1_m0.1'),None)
profile_text = '関門が全て揃うまで、cProfileの試走は実施しない。'
forecast = '関門とcProfileの一本が終わるまでは、種1〜20の見込みを確定しない。'
failure_file = ev/'profile_r1_m0.1/failure-analysis.json'
gate_note = ''
if failure_file.exists():
    failure = json.loads(failure_file.read_text())
    resource = json.loads((failure_file.parent/'resource.json').read_text())
    derived['profile_failure'] = {**failure, 'resource':resource}
    gate_note = '模型の関門326件は全て合格。不成立はその後のcProfile測定器の正常終了1件で、起動エラーのため停止した。'
    profile_text = f'''全関門326件は{gates['gates_finished']}に合格した。その後、世界2・種1・8体二集団・q=0.2・m=0.1・1740試行の測定を一件だけ受付したが、8個体すべてが模型入口の前で起動エラーになった。

```text
profile_collective_20261004.py:20 profiler.enable()
ValueError: Another profiling tool is already active
```

確認値：この例外は{failure['error_occurrences']}件、世界の台帳ファイル{failure['world_ledger_files']}件、世界試行の状態記録{failure['world_state_rows']}行、プロファイル原ファイル{failure['profile_files']}本。通信には固定試験の問いを準備した `probe_items` が1行あるだけ。学習の試行は始まっていない。子の終了後も親が待っていたため、自分の測定用プロセス群だけへSIGTERMを送り、受付解除を確認した。終了コード-15はこの停止操作の結果で、最初の原因は上記のcProfile起動エラーである。終了コードの検査1件は不成立として保存し、合格へ変更しない。

失敗した起動処理の診断値は{resource['elapsed_seconds']:.3f}秒、RSS合計の1秒観測最大{resource['rss_sum_peak_bytes']} bytes、出力{failure['output_logical_bytes']} bytes、swap増減{resource['swap_end_mib']-resource['swap_start_mib']:.2f}MiB。待ち時間を含む起動失敗の値であり、8体1740試行の時間・メモリ・出力の測定値には使えない。個体別の完走最大RSSも未取得。

原因の推定：{failure['cause_inference']}

★修正案：{failure['corrective_proposal']} この案は実装していない。模型・集団化のコードは変更せず、追加の走行は行わずに停止した。原文と停止操作は `profile_r1_m0.1/model.time.log`、`profile-stop.json`、`failure-analysis.json` に保存した。
'''
    forecast = 'cProfileの一本が完走していないため、その測定に基づく種1〜20・本番160本の時間・メモリ・ディスク見込みは**未確定**。起動失敗の252秒や35525 bytesを20倍・160倍にはしない。合格した関門12本の確認値は上の資源表と `derived-measurements.json` に保存した。世界1は未測定。本番は開始していない。'
if profile is not None and gates['status']=='passed':
    p = out/'profile_r1_m0.1'
    sizes = {}
    for file in p.rglob('*'):
        if file.is_file():
            key = file.relative_to(p).parts[0]
            sizes[key] = sizes.get(key,0)+file.stat().st_size
    peaks = [json.loads((p/f'profiles/agent{i}.resource.json').read_text())['peak_rss_bytes'] for i in range(8)]
    coordinator = json.loads((p/'profiles/coordinator.resource.json').read_text())['peak_rss_bytes']
    reference = next(r for r in full if r['name']=='comm_m0.1_r1')
    ratio = profile['elapsed_seconds']/reference['elapsed_seconds']
    top = json.loads((ev/'profile_r1_m0.1/profile-top.json').read_text())
    # 個体の関数内計測時間を足す。待機も含むのでCPU時間とは呼ばない。
    cpu = {}
    for file in sorted((p/'profiles').glob('agent*.prof')):
        import pstats
        for key,value in pstats.Stats(str(file)).stats.items():
            row = cpu.setdefault(key,{'calls':0,'self_seconds':0.,'cumulative_seconds':0.})
            row['calls'] += value[1]; row['self_seconds'] += value[2]; row['cumulative_seconds'] += value[3]
    hottest = [{'file':k[0],'line':k[1],'function':k[2],**v}
               for k,v in sorted(cpu.items(),key=lambda x:x[1]['self_seconds'],reverse=True)[:20]]
    derived['profile'] = {**profile,'parts':sizes,'agent_peak_rss_bytes':peaks,
                          'coordinator_peak_rss_bytes':coordinator,'reference_ratio':ratio,
                          'hottest_agent_self_time':hottest}
    profile_text = f'''世界2・種1・8体二集団・q=0.2・m=0.1・1740試行を一本、まとめ役と各個体にcProfileを掛けて測った。時間{profile['elapsed_seconds']:.3f}秒、まとめ役・個体・timeのRSS合計の1秒観測最大{profile['rss_sum_peak_bytes']} bytes、個体別最大RSS bytes={peaks}、まとめ役の最大RSS={coordinator} bytes。出力の論理サイズは{sum(sizes.values())} bytes、内訳={sizes}。各個体の最大RSSはプロファイル保存後に取得した。プロファイル9本と関数上位の集計を保存した。

同じ種・旗の非プロファイル腕との台帳本体・通信事象・新しい状態/RNG指紋は一致した。時間の参考倍率は{ratio:.3f}倍だが、二つの腕で他の同時負荷も異なるため、cProfileだけの増分とは主張しない。個体の関数内時間上位は `derived-measurements.json` に記録した。cProfileの時間はロック・通信の待機を含むため、CPU時間とは呼ばない。ここでは模型の速度を変えない。
'''
    by_arm = {}
    for q,m in [(0,0),(.2,0),(.2,.1),(.2,.3)]:
        arm = [r for r in full if r['q']==q and r['m']==m]
        assert len(arm)==3
        by_arm[(q,m)] = {'mean_seconds':sum(r['elapsed_seconds'] for r in arm)/3,
                        'mean_bytes':sum(r['output_bytes'] for r in arm)/3,
                        'max_rss_bytes':max(r['rss_sum_peak_bytes'] for r in arm)}
    rows = '\n'.join(f"|q={q}, m={m}|{v['mean_seconds']:.3f}|{v['mean_seconds']*20/3600:.3f}|{v['mean_bytes']*20/2**30:.3f}|{v['max_rss_bytes']/2**30:.3f}|"
                     for (q,m),v in by_arm.items())
    hours80 = sum(v['mean_seconds']*20/3600 for v in by_arm.values())
    disk80 = sum(v['mean_bytes']*20/2**30 for v in by_arm.values())
    rss = max(v['max_rss_bytes'] for v in by_arm.values())/2**30
    derived['forecast'] = {'by_arm':{f'q{q}_m{m}':v for (q,m),v in by_arm.items()},
                          'world2_80_hours_serial':hours80,'world2_80_disk_gib':disk80,
                          'world1_equal_time_and_disk_assumption':True,
                          'both_worlds_160_hours_serial':2*hours80,'both_worlds_160_disk_gib':2*disk80,
                          'rss_observed_max_gib':rss,'profile_files_included_in_production_forecast':False,
                          'profile_one_times_20_hours':profile['elapsed_seconds']*20/3600,
                          'profile_one_times_20_output_gib':sum(sizes.values())*20/2**30}
    forecast = f'''cProfileを含む今回の一本をそのまま20本へ換算すると、時間{profile['elapsed_seconds']*20/3600:.3f}時間・出力{sum(sizes.values())*20/2**30:.3f}GiBという計測負荷込みの参考値。逐次なら必要な常駐は一本の最大を基礎に考え、20倍にはしない。この単純換算にはcProfileの原ファイルも含む。

本番の記録条件での見込みは、同じ台帳になることを確かめた非プロファイル腕を基礎にする。関門で確認した世界2・種1〜3の各腕3本の平均（cProfileなし）から、各腕を種1〜20へ増やした場合を示す。種4〜20の本番は走らせていない。

種1の通信なしは午前の一本ずつの条件、夜は独立した腕を最多3件で処理した。観測した一本の経過時間が将来も同じと置いて平均した推測であり、均一な負荷で測った速度比較ではない。

|世界2の腕|一本の平均秒|20本・逐次の時間|20本の出力GiB|観測した一本のRSS合計最大GiB|
|---|---:|---:|---:|---:|
{rows}

世界2の4腕×20種＝80本は、逐次{hours80:.3f}時間・出力{disk80:.3f}GiBという見込み。世界1は今回未測定なので、世界2と同じ時間・出力と置いた**仮定**で、2世界の160本は逐次{2*hours80:.3f}時間・出力{2*disk80:.3f}GiB。独立腕を4本同時に処理でき、一本の速度も変わらない仮定なら{2*hours80/4:.3f}時間。受付待ち、SME優先、同時負荷、凍結後の模型の変更による時間差はこの理想値に含めない。

一本の観測RSS合計最大は{rss:.3f}GiB。同じ最大が4本で同時に出れば{rss*4:.3f}GiBという単純な上限見込み。受付見込みは一件4GB、4件なら16GBで、他の登録処理を含め24GB以下のときだけ受付できる。受付はディスク予約をしないので、実施時には20GiBを残す分と、見込みの出力と、種間のばらつき・作業領域分を別に確保する。出力見込みには台帳・通信・系譜・新指紋・sideを含め、cProfileの9ファイルと研究者の機械監査ログは本番用の出力見込みから除いた。今回のように監査の旗を入れたままの条件に限った見込みである。
'''
g_save = lambda p,d:p.write_text(json.dumps(d,ensure_ascii=False,indent=1)+'\n')
g_save(ev/'derived-measurements.json',derived)
shutil.copy2(ev/'derived-measurements.json',published/'derived-measurements.json')
section = f'''

## 2026-10-04夜の受付表による再開（最新）

状態：**{status}**。開始JST={gates['started']}、終了JST={gates.get('finished','未完')}。理由={gates.get('reason','未完の関門を進行中' if gates['status']=='running' else '関門と一本の測定を終えたため停止')}。

コードは `{source}` のまま。`tools/v39.py`・`abm/`・個体の判断・採点・値段を変更しない。辞書外停止検査は常時オン。集団の種1〜3だけを使用し、種21〜40は読まず、走らせていない。種1〜20の本番160本も開始していない。

午前に新しい `sets-sorted-v1` 指紋で完了した20本・64検査だけを引き継ぎ、未完の33本を別の出力先へ受付した。午前に途中停止した個体2の圧縮台帳を修復・再利用していない。集合整列前の古い監査指紋を作り直さず、合格の証拠にも使わない。初期8行の原文、狭いsource検査の差分、以前の停止報告は履歴として保持した。

{recovery_note}

固定の「全体4本」ではなく、`~/jobs/jobs.py run --wait` のclaim/releaseを利用する。見込み一件4GBは午前の8体RSS約2GBに余裕を足した研究者の指定で、jobs.pyの既知値1.2GBをそのまま使わない。自分が同時に受付へ出す件数は最大3件とし、SME用の余地を残す。8体の内部は全て直列、同じ模型設定の独立した腕だけを並べる。各受付は合計24GB、直近10分のswap、熱・性能、未登録の重いPython、出力先空き20GiBを満たすまで自動で待つ。終了ごとにreleaseする。受付表・jobs.pyを変更しない。

### 関門

関門と測定の検査記録{len(gates['checks'])}件、合格{sum(c['passed'] for c in gates['checks'])}件、不成立{sum(not c['passed'] for c in gates['checks'])}件。{gate_note}夜に完了した新規処理{len(gates['completed_new_jobs'])}件。全関門が揃う前にcProfileを走らせていない。実際の辞書外カウンタと検査回数は各処理のgates.jsonに保存する。fの毎試行値、開示列の腕間一致、source、配送・二項範囲、非干渉は下表と各処理の証拠で確認する。S1/Gはalpha=beta=0、忘却と学習の値段は両方0.01873710622997919、A・世界2・q=0.2（通信なしq=0）・1740試行を継承する。

|検査|結果|
|---|---|
{checks}

### 配送・受信の確認値

|腕|状態|配送数|組内|組間|取り込み・誕生・不成立|組間の99.9%中央二項範囲|
|---|---|---:|---:|---:|---|---|
{chr(10).join(count_rows)}

正解・外れ・一致の数はcountsとgatesに保存した。成績の良し悪しを判断しない。

### 時間・メモリ・出力と受付

|夜の新規処理|所要秒|RSS合計の観測最大bytes|個体ごと最大RSS・十進MB|出力の論理bytes|swap増減MiB|
|---|---:|---:|---|---:|---:|
{resources}

RSS合計は模型のまとめ役・個体・timeの子孫を1秒間隔で測った観測最大で、瞬間的な厳密最大ではない。受付を持つ研究者の検査処理・jobs.pyはこの模型RSS合計に含めないが、受付の4GBには余裕として含める。各処理のhealth.jsonl.gzにメモリ・swap・空き・熱・他の処理を記録し、argv.jsonとfinal-receipt.jsonで自分の登録を確認する。

最終確認JST=2026-10-05 10:54:23：自分の受付は0件。表の合計12.3GB/24GB、出力先と同じ領域の空き383.251GiB、memory_pressureの空き割合77%、free 6.4GB・inactive 9.9GB、swap 348.19MiBで直近10分に増加なし。熱・性能の警告は記録されていない。CPUの速度の制限値も記録なし（受付表では制限なしとして扱う）。動いている他の処理の情報を含む原文は `final-receipt-status.txt` に保存した。

|処理|受付後のJST|受付表の合計GB|開始時の空きGiB|開始時swap MiB|
|---|---|---:|---:|---:|
{chr(10).join(receipts)}

### cProfileの一本

{profile_text}

### 種1〜20の見込み（本番は実施しない）

{forecast}

### 実際に使った全引数

{arguments}

研究者の開始命令：

```text
cwd: {root}
{shlex.join(['/opt/homebrew/opt/python@3.12/bin/python3.12', 'resume_registered_gates_20261004.py'])}
```

全ての受付命令・コード版・機械状態・検査結果・測定器の起動エラーは `coll8_2026-10-03/resume-jobs-20261004/` に保存した。最終の `final-receipt-status.txt` で自分の受付が無いことを確認した。cProfileの原ファイルと、それに基づく見込みは未取得。確認値と推測を分け、ここで止める。
'''
marker = '\n\n## 2026-10-04夜の受付表による再開（最新）'
text = report.read_text().split(marker)[0]
banner = text.split('\n\n')[1]
new_banner = f'2026-10-04夜の受付表による再開。最新状態は「{status}」。模型を変更せず辞書外停止検査を常時オンにして関門を再開した。最新の確認値・cProfile・見込みは末尾に追記。以前の停止と検査修正は履歴として保持。本番160本は開始していない。'
report.write_text(text.replace(banner,new_banner,1)+section)
print(status, len(gates['checks']), len(gates['completed_new_jobs']), report)

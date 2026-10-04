"""再開の途中・最終結果を同じ報告へ保存する。模型を呼ばない。"""
from pathlib import Path
import gzip
import json
import re
import shlex
import shutil
import subprocess

root = Path(__file__).resolve().parent
source = root / 'source'
ev = root / 'evidence/restart-20261004'
report = root / 'report/control/2026-10-03_集団化_8体二集団_Codex3.md'
published = root / 'report/control/coll8_2026-10-03/restart-20261004'
published.mkdir(exist_ok=True)
gates = json.loads((ev / 'gates.json').read_text())
history = json.loads((ev / 'existing-individual-dictionary-counts.json').read_text())
jobs = [json.loads(line) for line in (ev / 'jobs.jsonl').read_text().splitlines()]
head = gates['source_commit']
derived = []
for run in gates['runs']:
    if 'agent_peak_rss_mb_decimal' in run:
        continue
    manifest = root / 'outputs/restart-20261004' / run['name'] / 'manifest.jsonl'
    if manifest.exists():
        records = [json.loads(line) for line in manifest.read_text().splitlines()]
        peaks = [rec['peak_rss_mb'] for rec in records if 'peak_rss_mb' in rec]
        if peaks:
            run['agent_peak_rss_mb_decimal'] = peaks
            derived.append({'job': run['name'], 'source': str(manifest), 'agent_peak_rss_mb_decimal': peaks})
(ev / 'individual-memory-from-manifests.json').write_text(json.dumps(derived, ensure_ascii=False, indent=1) + '\n')
(ev / 'code.diff').write_bytes(subprocess.check_output(['git', 'diff', '909b1e2', head], cwd=source))
for file in ev.iterdir():
    if file.is_file() and file.name != 'run-health.jsonl':
        shutil.copy2(file, published / file.name)
shutil.copy2(root / 'evidence/restart-20261004-initial-machine.json', published / 'restart-20261004-initial-machine.json')
if gates['status'] != 'running' and (ev / 'run-health.jsonl').exists():
    with (ev / 'run-health.jsonl').open('rb') as inp, gzip.open(published / 'run-health.jsonl.gz', 'wb') as out:
        shutil.copyfileobj(inp, out)
for name in ('check_restart_20261004.py', 'restart_gate_20261004.py', 'build_restart_report_20261004.py', 'monitor_restart_20261004.py', 'finalize_restart_evidence_20261004.py'):
    shutil.copy2(root / name, published / name)

status = {'running': '再開中', 'passed': '関門合格・停止', 'stopped': '不成立で停止'}[gates['status']]
if gates['status'] == 'stopped' and '機械の並列上限' in gates.get('reason', ''):
    status = '機械の並列上限で停止・残りの関門は未完'
checks = '\n'.join(f"|{c['name']}|{'合格' if c['passed'] else '**不成立**'}|" for c in gates['checks'])
resources = '\n'.join(f"|{r['name']}|{r['elapsed_seconds']:.3f}|{r['rss_sum_peak_bytes']}|{json.dumps(r.get('agent_peak_rss_mb_decimal'), ensure_ascii=False)}|{r['swap_end_mib']-r['swap_start_mib']:.2f}|" for r in gates['runs'])
arguments = '\n\n'.join(f"{j['name']}（{j['started']}）\n\n```text\ncwd: {j['cwd']}\n{shlex.join(j['argv'])}\nextra_env: {json.dumps(j['extra_env'], ensure_ascii=False)}\n```" for j in jobs)
machine_rows = [('再開作業の初回', json.loads((root / 'evidence/restart-20261004-initial-machine.json').read_text()))]
machine_rows += [(j['name']+'の開始前', json.loads((ev/(j['name']+'.argv.json')).read_text())['initial']) for j in jobs]
for filename, label in [('last-recorded-machine.json', '停止直前の最後の保存サンプル'),
                        ('final-machine.json', '停止後・自分の模型なし'),
                        ('report-before-machine.json', '報告保存の開始前')]:
    if (ev/filename).exists():
        machine_rows.append((label, json.loads((ev/filename).read_text())))
def machine_row(label, h):
    memory = h['memory']['output']
    page_bytes = int(re.search(r'page size of (\d+) bytes', memory)[1])
    free_pages = int(re.search(r'Pages free:\s*(\d+)', memory)[1])
    compressor_pages = int(re.search(r'Pages occupied by compressor:\s*(\d+)', memory)[1])
    return f"|{label}|{h['time']}|{h['disk_free_bytes']}|{free_pages*page_bytes/2**30:.3f}|{compressor_pages*page_bytes/2**30:.3f}|{h['swap_mib']}|{len(h['foreign_heavy'])}|"
machines = '\n'.join(machine_row(label, h) for label, h in machine_rows)
stop_summary = ''
if (ev/'stop-detail.json').exists():
    stop = json.loads((ev/'stop-detail.json').read_text())
    partial = json.loads((ev/'partial-solo-r1-a2.json').read_text())
    stop_summary = f'''種1の通信なし8体は1740試行を完走し、台帳の13920行で割り当てたfの一致を確認した。独立した一体との台帳一致は個体0・1で合格。個体2は途中で停止し、保存したsideの最終試行は{partial['last_side_record']['trial']}（0起点）。この未完の記録は合格の証拠に使わない。

|残りの関門|状態|
|---|---|
|種1・通信なしと単独の個体2〜7の一致|個体2は途中停止、個体3〜7は未実行|
|種1・m=0/0.1/0.3の1740試行と開示列・配送等|3腕とも未実行|
|種2・3・通信なしと各m、単独比較|いずれも未実行|

1740試行の計画のうち{stop['remaining_jobs_count']}本が未完（途中1本、未実行{stop['unstarted_jobs_count']}本）。したがって、全関門合格という結論は出さない。通信なし腕の配送・受信は0件であり、この腕のsource照合だけでは、通信ありで報告から実際に誕生した時の採点を確認したことにはならない。保存した機械サンプル{stop['saved_health_samples']}件に熱・性能の警告は{stop['saved_warning_samples']}件。検出時サンプルの欠落は後述する。
'''
counts = []
for file in sorted(ev.glob('*.counts.json')):
    data = json.loads(file.read_text())
    counts.append(f"|{data['name']}|{data['sent']}|{data['within']}|{data['cross']}|{dict(data['receive_results'])}|")
counts_table = '\n'.join(counts) if counts else '|未実施|—|—|—|—|'
full = [r for r in gates['runs'] if r['name'].startswith(('no_comm_r','comm_m'))]
if full:
    average = sum(r['elapsed_seconds'] for r in full) / len(full)
    estimate = f'今回完走した世界2の1740試行の{len(full)}本の平均は{average:.3f}秒。160本を同じ平均時間と仮定した所要時間は、並列1で{160*average/3600:.3f}時間、並列4で{40*average/3600:.3f}時間。通信ありの1740試行、世界1の時間、並列4での負荷、SME優先の待ち時間は未測定。4腕・2世界を同じ時間と置いた推測の理想値であり、確認値ではない。'
else:
    estimate = '今回の1740試行の腕はまだ完走していないため、今回の測定から160本の見積もりは作らない。前回の1740試行の確認値と仮定による見積もりは履歴に残した。'
reason = gates.get('reason', 'なし（未完の関門は継続中）' if gates['status'] == 'running' else '全関門を終えたため停止')
section = f'''

## 2026-10-04の委任による再開（最新）

状態：**{status}**。理由：{reason}。コード `{head}`、比較前のコード `909b1e2fd70f9124fad512946d5aeae709215ad8`。8体は全て直列1、こちらの重い走行も一本ずつ実施。二体の同時／直列比較だけ同時2とした。集団の種は1〜3のみで、21〜40は読まず、走らせていない。本走行160本は開始していない。

今回、完走した新規走行は{len(gates['runs'])}本、完了した検査は{len(gates['checks'])}件。検査の不成立は{sum(not c['passed'] for c in gates['checks'])}件。停止の理由が機械上限の場合は、模型の辞書外や台帳不一致とは区別する。最新の停止・未完の内訳は `stop-detail.json` に残した。

{stop_summary}

### 段1：常時の辞書外停止検査

`tools/v39.py`、`abm/`、個体の選択・採点・値段の計算は変更していない。`tools/v311c.py:57` で既存の `v39.dict_order` を包み、**元の関数をそのまま呼んで返り値をそのまま返す**。辞書外名だけを研究者側のCTXへ控える。状態や候補へこの控えを渡さず、途中で消えた候補の名前も記録できる。

`v311c.py:72` は `v39.STATS.get('not_in_dictionary', 0)` を読み、1以上なら `kind: v311c_not_in_dictionary` と集団走行番号・個体・試行（0起点）・世界／受信／試験の段階・カウンタ・名前の整列した一覧をsideへ書き、flushして停止する。`v311c.py:570` で集団化に常時入れ、旗で外せない。世界の計算後649行、受信後683行で検査する。一致試験でも539行で検査し、既存のモジュール復元がカウンタを戻す前に止まる。成功時には各個体の研究者用 `dictionary_checks` に検査回数を残す。

終了の知らせには停止診断も付け、まとめ役が世界・受信・試験のどの段階でも診断を残して他の個体を止める。新規の構造検査9件を含む関連16ファイル114件は全て合格。これは人工的な名前を使った停止処理の検査であり、実験の辞書外発生件数には加えない。全引数と結果は `coll8_2026-10-03/restart-20261004/unit-suite.json`、差分は `code.diff`。

既存の個体の終了記録は、`tools/v3_run.py:544`〜545で `v39.STATS` 全体を書き出す。`v39.py:93` の辞書外カウンタは発生した時だけ作られ、初期値として欄を作らない。この作業場所の個体版8本と独立した一個体8本の保存manifest計16本を読み、STATSの書出しを16本で確認した。カウンタ1以上は{history['positive']}本、既存カウンタの欄ありは{sum(r.get('counter_field_present',False) for r in history['records'])}本。全STATSに欄が無い場合は、動的カウンタが一度も作られなかったこととして0と読んだ。他の作業場所・研究全体の全走行について0と主張するものではない。件数と対象一覧は `existing-individual-dictionary-counts.json`。

### 段2：追加前後の台帳一致

保存済みの `outputs/record8_logged`（集団種1・8体・200試行、q=0.2、m=0.1、世界2、A、追加4旗オン）を比較前とした。新しいコードでは `outputs/restart-20261004/guard_equivalence_seed1` へ同じ条件で新規に走らせた。全argvが出力場所を除いて一致することを先に検査した。台帳の実行情報ヘッダを除き、本体の生バイトを各個体ごとにSHA256と行数で比較した。段2の合否は下表を参照する。

**旧い監査の状態指紋は作り直していない。また、合格の証拠に使っていない。** 段2だけは委任の指定どおり保存台帳本体を使い、段3の比較は全て新規走行どうしで行う。

### 段3：新しい指紋による新規の関門

全て別の出力先 `outputs/restart-20261004/` と別の証拠先 `evidence/restart-20261004/` で実行し、旧い完走キャッシュや旧い監査指紋の再使用をしない。指紋は `sets-sorted-v1`。新たな辞書外、台帳不一致、検査不成立、熱・性能の警告、機械の並列上限超過があれば、その時点で停止する。模型の修正をして続行しない。

受入①②は新しい切替オフ腕・通信なし腕と個体版／独立一体との台帳比較、③〜⑧は8体設定の構造検査6件を再実行、⑨⑩⑫は新しい通信と世界の記録・集計照合、⑪は新指紋で試験の前後と記録旗の有無の非干渉を検査する。以下は完了した検査だけであり、全合格はstatus=passedのときだけとする。

|検査|結果|
|---|---|
{checks}

### 配送と受信の確認値

|腕|送信＝配送数|組内|組間|取り込み・誕生・不成立|
|---|---:|---:|---:|---|
{counts_table}

fは各個体・各世界試行の実際の値を台帳と照合する。開示のcoin_t・f_fired・f_realizedの列を通信なしと各mで比較する。世界の採点と報告の誕生の採点は既存のsource欄を狭い検査台本で照合し、未採点の行にも採点欄が無いことを検査する。S1/Gは前回と同じalpha=beta=0で変更しない。忘却・学習の値段は両方0.01873710622997919。受信Aだけ、q=0.2と通信なしq=0、m=0/0.1/0.3、世界2。正解・外れ・一致の数はcountsとgatesに保存し、良し悪しの判断には使わない。

### 時間・メモリ・機械の記録

|走行|所要秒|全プロセスRSSの観測最大bytes|個体ごとの最大RSS・十進MB|swap増減MiB|
|---|---:|---:|---|---:|
{resources}

全体RSSはまとめ役・個体・timeの子孫を1秒間隔で観測した合計の最大で、瞬間的な厳密最大ではない。個体ごとの最大は個体が終了時に取得した値。最初の8体も直列1で走らせて測定した。メモリ・swap・プロセス・熱／性能警告は開始前と走行中に記録する。

|時点|JST日時|空き容量bytes|メモリ空きページGiB|圧縮器の常駐GiB|swap使用MiB|他の重い処理数|
|---|---|---:|---:|---:|---:|---:|
{machines}

機械の原記録は各argv.jsonのinitialとrun-health.jsonl（報告枝ではgzip保存）。開始前の初回記録は `restart-20261004-initial-machine.json`。メモリ表はvm_statの空きページと圧縮器常駐ページから求めた値で、利用可能メモリの推定ではない。警告が無い時だけ実行し、全セッションとClaudeを合わせた上限4を監視して、超過で自分を停止する形でSME優先を継承した。

今回の機械上限による停止は、`coll8_gate.py:135` の `len(foreign_heavy)+active_cap>4` で発生し、走行器は自分のプロセス群だけをSIGTERMで止めた。**上限検出時のサンプルは例外の直前に保存されておらず、検出した他プロセスの完全なPID一覧は確認できない。** 直前まで保存したサンプルと停止後の状態は `stop-detail.json` と `final-machine.json` に分けた。自分の重い処理枠1という前提では、この停止分岐は他の重い処理4以上を検出したことを意味するが、その人数は保存サンプルによる直接確認値と区別する。停止後、自分の模型プロセスは残っていないことを確認した。残りの走行は再開しない。

{estimate}

### 実際に使った全引数

個体の世界の種1+1000×番号（集団の種rではr+1000×番号）と、試験の世界900000+rは、集団の走行番号とは別。集団の種21〜40を読んだり走らせたりしない。各ジョブの全引数、開始前の機械状態、個体指定の環境変数はjobs.jsonl・各argv.jsonにも保存した。

{arguments}

検査と再開の台本：

```text
cwd: {root}
/opt/homebrew/opt/python@3.12/bin/python3.12 check_restart_20261004.py
/opt/homebrew/opt/python@3.12/bin/python3.12 restart_gate_20261004.py
/opt/homebrew/opt/python@3.12/bin/python3.12 build_restart_report_20261004.py
```

確認した数と推測の見積もりを分けた。関門が落ちればそこで停止し、全て通ってもそこで停止して、本走行は始めない。
'''
marker = '\n\n## 2026-10-04の委任による再開（最新）'
text = report.read_text().split(marker)[0]
banner = text.split('\n\n')[1]
new_banner = f'2026-10-04の委任で再開。最新状態は「{status}」。模型を修正せず、集団化の側に常時の辞書外停止検査を追加した。最新の検査と機械記録は末尾の「2026-10-04の委任による再開」。以前の停止報告・未採点行の原文・検査台本の差分は履歴として保持した。本走行160本は開始していない。'
report.write_text(text.replace(banner, new_banner, 1) + section)
print(report, status, len(gates['checks']), len(gates['runs']))

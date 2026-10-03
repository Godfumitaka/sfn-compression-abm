"""今回の承認後の結果を報告へ追記し、旧停止の証拠も残す。"""
from pathlib import Path
from collections import Counter
import gzip, hashlib, json, re, shlex, shutil, subprocess

root = Path(__file__).resolve().parent
ev = root/'evidence'
dest = root/'report/control/coll8_2026-10-03'
report = root/'report/control/2026-10-03_集団化_8体二集団_Codex3.md'
result = json.loads((ev/'gates.json').read_text())
assert result['status'] in ('passed', 'stopped')
code = subprocess.check_output(['git','rev-parse','HEAD'],cwd=root/'source',text=True).strip()
passed = result['status'] == 'passed'
summary = ('関門合格の報告。段Aと段Bの指定関門をすべて確認し、ここで停止した。'
           if passed else '停止報告。終了通知の修正後の当て直しを進め、下記の不成立で停止した。')
summary += ('今回の修正は直列旗の終了通知だけで、模型の計算は変えていない。'
            '最新の結果は末尾の「終了通知の修正後の結果」。途中の停止・未採点行の原文・台本の差分は履歴として残した。本走行160本は開始していない。')
s = report.read_text()
paragraphs = s.split('\n\n')
paragraphs[1] = summary
s = '\n\n'.join(paragraphs)
s = s.replace('## 最終の停止：直列旗の終了通知の相互待ち',
              '## 履歴：承認前の停止・直列旗の終了通知の相互待ち')
s = s.replace('### 最終の関門表', '### 履歴：終了通知修正前の関門表')
marker = '\n\n## 終了通知の修正後の結果\n'
if marker in s:
    s = s[:s.index(marker)]
s += marker
s += f'\nコード枝 `coll8-2026-10-03` のコミット `{code}`。修正前は `93c5dd6a35775c4f2df34c110ed9b222b5794055`。'
s += 'ユーザーの追加承認に従い、_agent_mainで終了通知をロック保持中に準備し、送信前に一度だけロックを解放するようにした。成功・計算例外・通知準備例外・送信例外を検査した。通知のデータ形式は同じ。abm/・tools/v3_run.py・tools/v311c_lineage.py・config/は修正前から変更0件。v311c.pyの_agent_main以外のASTは修正前と一致（terminal-fix-model-proof.json）。\n'
s += '\n通知の修正は、既定オフの既存 --v311c-serial の配管の直し。新しい旗は追加していない。既定オフの4旗（probe-shop/audit/lineage/serial）の既定は変わらない。受信採点・協調報酬・N3選択・保持・学習の計算は変更していない。\n'
s += '\n修正前後の差分：\n\n```diff\n'+(ev/'terminal-fix-code.diff').read_text()+'```\n'
units = json.loads((ev/'terminal-fix-unit-suite.json').read_text())
num = sum(int(re.search(r'(\d+) passed',r['output'])[1]) for r in units)
s += f'\n構造検査はファイル別の別プロセスで {len(units)} ファイル・{num} 件合格。新しい終了処理の5検査には、8体が7→0の逆順に計算を終え、各4MiBの通知を実際のまとめ役と同じ0→7の順で受け取る検査を含む。計算は共通セマフォで一度に1体。残る4検査は成功と3種の例外で、準備中のロック保持・送信時の解放・一度だけの解放を確かめる。模型の答えの方向を合否に使わない（terminal-fix-unit-suite.json）。\n'
if passed:
    s += '\n指定の関門をすべて通過したので停止。本走行は開始しない。\n'
else:
    s += '\n**停止理由：** '+result.get('reason','不明')+'。以降の走行は実施していない。\n'
diagnosis_path = ev/'state-fingerprint-diagnosis.json'
if diagnosis_path.exists():
    d = json.loads(diagnosis_path.read_text())
    s += '''
### 不成立を欄ごとに確認した結果（保存記録の読取りのみ）

exitfix_record8_plainとrecord8_loggedはともに8体・200試行を完走し、台帳本体は全8本・各200行で一字一句一致した。終了通知の相互待ちは再発していない。後者も完走した後、.state.jsonlを丸ごと比べる検査が不成立になった。検査名は「お店試験・系譜の本走行乱数」だが、比較するファイルには学習状態の指紋と乱数の指紋の両方が入っている。**この検査名だけで、乱数が変わったとは言えない。**

|欄・記録|一致|不一致|確認した範囲|
|---|---:|---:|---|
|t・agent|1600|0|8体×200試行、行の対応も同じ|
|state（sha256(repr(state)))|0|1600|最初の不一致もt=0・個体0で、最初の一致試験t=99より前|
|rng（sha256(repr(state.rng_state)))|1600|0|記録された乱数状態の指紋|
|coin_t・f_fired・f_realized|1600|0|台帳にある開示の抽選と実際のf|
|台帳本体|8本|0|ヘッダの測定・コミット情報を除いた本体は完全一致|

乱数指紋は各側200種類であり、一定の空欄だけを比較しているわけではない。ただし記録欄はstate.rng_stateであり、世界生成・用途別のすべての乱数の完全な状態をこの結果だけで保証するものではない。試験前後のrandom.getstate・学習状態の監査は実行中に別途確認され、例外は無かった。比較の原文・各欄の件数・最初の不一致はstate-fingerprint-diagnosis.json、両側の指紋記録もそのまま保存した。

**コードで確認したこと：** 指紋の計算はtools/v311c.pyのapplyでrepr(state)をハッシュする。AgentState.slot_historyとFrequencyTable.alive_vocabにはfrozensetがある。reprは集合を表示する順序をプロセス間で固定する契約を持たない。模型の計算や走行を動かさず、同じAgentState・同じFrequencyTableをPythonのハッシュ初期化だけ0/1/2/3に変えた4個の短いプロセスで作った小例では、4種類のstate指紋になった。これはPythonの文字列ハッシュ用の値で、集団の走行種ではない（repr-fingerprint-counterexample.json、diagnose_state_fingerprint.py）。

**判断の限界：** reprをプロセス間で比べる記録方法は不安定であり、今回の不一致にもその影響が疑われる。しかし保存記録は指紋だけで、学習状態の全値を復元できないため、今回の1600件がすべて集合の表示順だけの差だとは証明していない。台帳と記録された乱数の一致から、隠れた学習状態の完全一致まで合格に格上げしない。指紋の記録・検査のコードはここでは修正せず、関門不成立で停止した。

★次の記録修正案（未実装）：研究者側の監査だけで、dataclassの全フィールドを型付きで直列化する。集合・凍結集合は要素の表現で順を固定し、模型が順に読む可能性のある辞書・列・タプルは元の順を保存する。未対応の型をstrへ落として通さず、明示的に失敗させる。学習状態・state.rng_state・random.getstateを別欄で比較し、どの欄が違うかを検査名と詳細で区別する。模型の計算・f(agent,t)・台帳本体は変えない。同じ値の別プロセスの一致と、値・意味のある順序・乱数の変更を検出する検査を足し、200試行の非干渉比較を当て直す。保存済みの指紋から正準表現を作り直すことはできない。

record8_no_audit、通信ありの1740試行のm=0/0.1/0.3、集団種2・3と対応する単独比較は、この不成立の後には開始していない。全関門合格は未確認。本走行も開始していない。
'''
checks = result['checks']
by_name = {r['name']: r for r in checks}
def state(name):
    r = by_name.get(name)
    return '合格' if r and r['passed'] else '不成立' if r else '未実施'
def all_state(names):
    values = [state(n) for n in names]
    return '不成立' if '不成立' in values else '合格' if all(x=='合格' for x in values) else '一部確認／未完'
s += '\n### 今回の当て直しと関門\n\n|検査|最新状態|範囲|\n|---|---|---|\n'
rows = [
 ('通知：大きな内容・逆順・一度だけ解放', state('大きな終了通知・逆順完了・一度だけ解放の検査'), '8体×4MiB、模型を動かさない終了処理の5検査'),
 ('二体同時と直列を新たに実行', all_state(['終了通知修正後：直列と同時（2体） 台帳本体','終了通知修正後：直列と同時（2体） 通信事象']), '各100試行、台帳2本・通信事象157行'),
 ('追加旗全オフと土台を新たに実行', all_state(['終了通知修正後：追加旗全てオフと土台（2体） 台帳本体','終了通知修正後：追加旗全てオフと土台（2体） 通信事象']), '各200試行、台帳2本・通信事象332行'),
 ('record8_plain完走を残りより先に確認', state('終了通知修正後：record8_plain完走を先に確認'), '8体・200試行、旧出力は上書きせずexitfix_record8_plainに保存'),
 ('①集団化全部オフと固定個体版', all_state([f'集団化全部オフと固定個体版：個体{i}' for i in range(8)]), '8体×100試行の診断、f一様0.5、全8本を比較'),
 ('②通信なしと単独：種1', all_state([f'通信なし8体と単独：個体{i}' for i in range(8)]), '8体×1740試行、割当てf、保存済み完走結果を再利用'),
 ('②通信なしと単独：種2・3', all_state([f'通信なし8体と単独：種{r}個体{i}' for r in (2,3) for i in range(8)]), '8体×1740試行×2種'),
 ('③〜⑧の構造検査', '合格', '今回の92検査に8体設定の小例を含む'),
 ('⑪お店試験・系譜の非干渉', all_state(['お店試験・系譜の非干渉（8体） 台帳本体','お店試験・系譜の本走行乱数']), '8体200試行の台帳本体・各試行の学習状態と乱数指紋を比較'),
 ('⑪状態指紋記録の非干渉', all_state(['状態指紋の非干渉（8体） 台帳本体','状態指紋の非干渉（8体） 通信事象']), '8体200試行の台帳本体・通信事象を比較'),
 ('m=0の組間配送', all_state([f'comm_m0_r{r} m=0の組間配送' for r in (1,2,3)]), 'q=.2、種1〜3、各1740試行'),
 ('m>0の二項範囲', all_state([f'comm_m{m}_r{r} mの二項範囲' for r in (1,2,3) for m in (0.1,0.3)]), '事前固定の99.9%中央二項範囲、下表に件数・割合'),
 ('fの毎試行の値', all_state([f'{name} fの毎試行値' for name in [f'no_comm_r{r}' for r in (1,2,3)]+[f'comm_m{m}_r{r}' for r in (1,2,3) for m in (0,0.1,0.3)]]), '各個体の台帳のf_realizedを割当てと照合'),
 ('開示の抽選の並び', all_state([f'comm_m{m}_r{r} 開示の抽選の並び' for r in (1,2,3) for m in (0,0.1,0.3)]), '同じ個体・種のcoin_t/f_fired/f_realizedを通信なしと全試行比較'),
 ('⑨出どころ・初期採点、⑩時計・配送、⑫分母・対ごと集計', '全指定範囲で合格' if passed else '下記の確認済み記録の範囲、全指定範囲は未完', '採点がある行はsource必須、無い行は採点欄なし。詳細はgates.jsonの全検査'),
 ]
for label,status,detail in rows:
    s += f'|{label}|{status}|{detail}|\n'
failed = [r for r in checks if not r['passed']]
if failed:
    s += '\n不成立の原文：\n\n```json\n'+json.dumps(failed,ensure_ascii=False,indent=1)+'\n```\n'
s += '\n### 完走した関門の時間・常駐メモリ・スワップ\n\n全体RSSは約1秒間隔の合計の観測最大（共有領域を重複計上し、観測間の最大は保証しない）。個体RSSはOSの保持する最大（十進MB）。旧record8_plainの終了待ち914.435秒は完走時間に含めない。\n\n|条件|時間秒|全体RSS観測最大MiB|個体RSS最大・十進MB|スワップ増減MiB|\n|---|---:|---:|---|---:|\n'
for r in result['runs']:
    peaks = r.get('agent_peak_rss_mb_decimal')
    if peaks is None:
        manifest = root/'outputs'/r['name']/'manifest.jsonl'
        if manifest.exists():
            peaks = [j['peak_rss_mb'] for j in map(json.loads,manifest.read_text().splitlines()) if 'peak_rss_mb' in j]
    s += f"|{r['name']}|{r['elapsed_seconds']:.3f}|{r['rss_sum_peak_bytes']/1048576:.3f}|{', '.join(map(str,peaks or []))}|{r['swap_end_mib']-r['swap_start_mib']:.2f}|\n"
s += '\n### 配送・取り込み・誕生の実測\n\n|条件|配送|組内|組間|組間割合|99.9%中央二項範囲|同化|誕生|不成立|\n|---|---:|---:|---:|---:|---|---:|---:|---:|\n'
for r in result['runs']:
    name=r['name']; p=ev/(name+'.counts.json')
    if not p.exists():continue
    j=json.loads(p.read_text()); sent=j['sent']; cross=j['cross']
    interval=by_name.get(name+' mの二項範囲',{}).get('central_999_range')
    c=j['receive_results']
    s += f"|{name}|{sent}|{j['within']}|{cross}|{cross/sent:.6f}" if sent else f"|{name}|0|0|0|—"
    s += f"|{interval or '—'}|{c.get('同化',0)}|{c.get('誕生',0)}|{c.get('不成立',0)}|\n"
full = [r['elapsed_seconds'] for r in result['runs'] if r['name'].startswith(('no_comm_r','comm_m'))]
if full:
    s += f'\n本走行160本の**推測**：世界2・1740試行の8体の完走実測範囲 {min(full):.3f}〜{max(full):.3f}秒をそのまま全160本へ外挿すると、並列1は {min(full)*160/3600:.3f}〜{max(full)*160/3600:.3f}時間、並列4の理想的な均等割りは {min(full)*40/3600:.3f}〜{max(full)*40/3600:.3f}時間。世界1は今回走らせていない。共有資源の競合・世界による費用差・SME優先の待機は未計測で、実際の完了時間を保証しない。160本は走らせていない。\n'
s += '\n### 機械の記録\n\n修正着手前はterminal-fix-initial-machine.json、重い走行の前は各argv.jsonのinitial、走行中はrun-health.jsonl.gz、終了後はterminal-fix-final-machine.jsonに保存。熱・性能の警告が記録されていれば走行は停止する。八体の個体計算・独立走行は直列1、二体の同時比較だけ2、全セッションの重い処理の合計4まで・SME優先の約束を継続した。\n'
observation = ev/'terminal-fix-machine-observations.json'
if observation.exists():
    h=json.loads(observation.read_text())
    s+=f"\n今回の6条件の走行中の観測{h['observations']}件では、他の重い処理は最多{h['max_foreign_heavy']}本、今回の同時計算枠との合計は最多{h['max_global_observed_heavy_capacity']}。スワップ範囲{h['swap_min_mib']}〜{h['swap_max_mib']}MiB、空きの最小{h['disk_min_bytes']}バイト、熱・性能の警告の記録なし（terminal-fix-machine-observations.json）。これは観測した範囲の値で、観測の間に起きた変化は含まない。\n"
for name in ('terminal-fix-initial-machine.json','terminal-fix-final-machine.json'):
    p=ev/name
    if p.exists():
        h=json.loads(p.read_text())
        s += f"\n{name}: {h['time']}、空き{h['disk_free_bytes']}バイト、スワップ{h['swap_mib']}MiB、他の重い処理{len(h['foreign_heavy'])}本。\n\n```text\n{h['memory']['output']}{h['swap']['output']}{h['thermal']['output']}```\n"
s += '\n### 承認後に実際に使った全引数\n\n単独の個体世界の種1+1000×個体番号は、集団の走行番号1〜3と別物。試験の世界は900000+集団走行番号。禁止された集団種21〜40の結果は読まず、走らせていない。\n'
jobs=[json.loads(raw) for raw in (ev/'jobs.jsonl').read_text().splitlines()]
start=next(i for i,j in enumerate(jobs) if j['name']=='exitfix_serial2_simultaneous')
for j in jobs[start:]:
    s += f"\n{j['name']}（{j['started']}）\n\n```text\ncwd: {j['cwd']}\n"
    for k,v in j.get('extra_env',{}).items():s+=f'{k}={v}\n'
    s += shlex.join(j['argv'])+'\n```\n'
s += '\n確認した数はgates.json・counts.json・resource.jsonに保存した。成績の良し悪しの判断や研究上の結論は書かない。ここで停止し、本走行は始めない。\n'
report.write_text('\n'.join(line.rstrip() for line in s.splitlines())+'\n')
for p in ev.iterdir():
    if p.is_file() and p.suffix in ('.json','.jsonl','.txt','.log','.diff') and p.name!='run-health.jsonl':
        shutil.copy2(p,dest/p.name)
def compress(source,target):
    if target.exists():
        with gzip.open(target,'rb') as old:
            if old.read()==source.read_bytes():return
    with source.open('rb') as inp, target.open('wb') as fp, gzip.GzipFile(fileobj=fp,mode='wb',mtime=0) as out:
        shutil.copyfileobj(inp,out,4*1024*1024)
compress(ev/'run-health.jsonl',dest/'run-health.jsonl.gz')
for name in ('check_terminal_fix.py','run_after_terminal_fix.py','finalize_terminal_report.py','diagnose_state_fingerprint.py'):
    shutil.copy2(root/name,dest/name)
proofs=json.loads((dest/'completed-ledger-proofs.json').read_text())
for r in result['runs']:
    name=r['name']; path=root/'outputs'/name
    if name not in proofs:
        pp=[]
        for p in sorted((path/'ledgers/cells').glob('*/*.jsonl.gz')):
            h=hashlib.sha256(); n=0
            with gzip.open(p,'rb') as inp:
                header=json.loads(next(inp))
                for line in inp:h.update(line);n+=1
            pp.append({'path':str(p),'header':header,'body_sha256':h.hexdigest(),'body_rows':n})
        proofs[name]=pp
    for p in (path/'comm').glob('*'):
        if p.suffix=='.json':shutil.copy2(p,dest/(name+'_'+p.name))
        elif p.suffix=='.jsonl':compress(p,dest/(name+'_'+p.name+'.gz'))
(dest/'completed-ledger-proofs.json').write_text(json.dumps(proofs,ensure_ascii=False,indent=2)+'\n')
print('報告・証拠保存:',report)

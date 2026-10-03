"""指紋の承認後の証拠を保存し、停止理由を報告へ追記する。"""
from pathlib import Path
import json
import shutil
import subprocess
import sys

root = Path(__file__).resolve().parent
ev = root / 'evidence'
source = root / 'source'
report = root / 'report/control/2026-10-03_集団化_8体二集団_Codex3.md'
published = root / 'report/control/coll8_2026-10-03'
inventory = json.loads((ev / 'canonical-saved-recheck.json').read_text())
assert inventory['status'] == 'completed_available_records'
comparisons = json.loads((ev / 'canonical-saved-comparisons.json').read_text())
proof = json.loads((ev / 'canonical-model-unchanged-proof.json').read_text())
assert proof['v311c_only_audit_calls_and_import_changed'] and proof['other_model_files_unchanged']
head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=source, text=True).strip()
diff = subprocess.check_output(['git', 'diff', proof['comparison_commit'], head], cwd=source, text=True)
(ev / 'canonical-full-code.diff').write_text(diff)
sys.path.insert(0, str(source / 'tools/v311c_checks'))
import coll8_gate as gate
health, _ = gate.health()
gate.save(ev / 'canonical-final-machine.json', health)
stop = {'status': 'stopped', 'source_commit': head,
        'reason': 'ユーザー条件(3)：辞書外の名の同一鍵が集合順を引き継ぎ、符号長と保持の条件判断を変える',
        'model_issue_fixed': False, 'model_simulations_after_fingerprint_approval': 0,
        'main_run_started': False, 'full_runtime_fingerprint_recheck_complete': False}
gate.save(ev / 'canonical-order-stop.json', stop)
for path in ev.glob('canonical*'):
    if path.is_file(): shutil.copy2(path, published / path.name)
shutil.copytree(ev / 'canonical-saved-v1', published / 'canonical-saved-v1', dirs_exist_ok=True)
for name in ('check_canonical_fix.py', 'check_hash_order_model.py', 'recheck_saved_fingerprints.py',
             'compare_saved_canonical.py', 'build_canonical_report.py'):
    shutil.copy2(root / name, published / name)

files = inventory['files']
jobs = {}
for record in files:
    key = Path(record['path']).relative_to(root / 'outputs').parts[0]
    value = jobs.setdefault(key, [0, 0, 0])
    value[0] += 1
    value[1] += record['rows_checked']
    value[2] += int(not record['compressed_file_complete'])
filetable = '\n'.join(f'|{name}|{n}|{rows}|{bad}|' for name, (n, rows, bad) in jobs.items())
pair_groups = {}
for item in comparisons['comparisons']:
    value = pair_groups.setdefault(item['comparison'], [0, 0, True])
    value[0] += 1
    value[1] += item['rows_per_side']
    value[2] = value[2] and item['recorded_snapshot_fingerprints_equal']
pairtable = '\n'.join(f'|{name}|{n}|{rows}|{"一致" if same else "不一致"}|' for name, (n, rows, same) in pair_groups.items())
incomplete = '\n'.join(f"- `{Path(f['path']).relative_to(root / 'outputs')}`：読めた{f['rows_checked']}行、{f['incomplete_reason']}" for f in files if not f['compressed_file_complete'])
start = json.loads((ev / 'canonical-initial-machine.json').read_text())
readstart = json.loads((ev / 'canonical-recheck-initial-machine.json').read_text())
machinetable = '\n'.join(f"|{label}|{h['time']}|{h['disk_free_bytes']}|{h['swap_mib']}|{len(h['foreign_heavy'])}|" for label, h in [('承認後の開始前', start), ('保存台帳の読取り前', readstart), ('読取り終了後', health)])
foreign = ', '.join(str(p['pid']) for p in start['foreign_heavy'])
section = f'''

## 指紋の修正と模型の集合順依存の調査（最新の停止結果）

ユーザーが指紋の整列を承認した後、検査の指紋だけを修正した。**模型の判断にも集合順が影響する条件分岐を確認したため、条件(3)に従って、その箇所は変更せず、残りの関門の走行を停止した。** お店の保存走行でこの条件が発生したという結論ではない。本走行160本も開始していない。

コードコミットは `{head}`、比較対象は `{proof['comparison_commit']}`。変更は `tools/v311c_fingerprint.py`、その検査、`tools/v311c.py` の監査呼出し3箇所とimportだけ。監査の呼出しを旧式へ戻してASTを比較した結果は一致し、その他の模型・設定の差分は0件。土台からの `abm/` 差分も0件。模型の候補計算、採点、保持、学習、会計S1/Gは変更していない。追加4旗（probe-shop、audit、lineage、serial）の既定は引き続き全てオフ。承認後の新しい模型走行は0本。

証拠：`coll8_2026-10-03/canonical-model-unchanged-proof.json`、`canonical-full-code.diff`。コード枝は通常push済み。報告枝は他セッションの更新をfetch・rebaseしてから通常pushする。衝突があれば解決しない。

### 指紋の変更内容と小例

版 `sets-sorted-v1`。`set` と `frozenset` の要素は、型を残して再帰的に文字にしてから、その文字で整列する。辞書の項目順、list/tupleの並び、型、None、dataclassの全フィールド、浮動小数点の値は残す。模型が読む可能性がある順序まで消す指紋にはしない。未知の型はreprへ戻さずエラーにする。状態を変更せず、乱数を使わず、キャッシュも持たない。rng欄は従来のtupleの指紋を継続する。

新規の指紋検査13件を含め、関連15ファイルの105件は全て合格。集合順だけが違う状態は同じ指紋になり、値・辞書順・列順・None・型の変更は指紋に現れることを確かめた。試験ごとの実引数と出力は `canonical-unit-suite.json` に全て保存した。下の小例では、未変更の実際の候補関数も同時に調べた。

|PYTHONHASHSEED|集合の列挙順|固定席の符号長dC|候補V|V<λの条件判断|修正後の全状態の指紋|
|---:|---|---:|---:|---|---|
|0|acb, abc, bac|3|0.024999999999999998|偽（この候補を変換しない）|d3cadbaf2b6212c2cb8b2f9e0746fb71b8122c60e792a044354c9730cbb915de|
|1|acb, bac, abc|5|0.015|真（この候補を変換対象にする）|同上|
|2|acb, bac, abc|5|0.015|真（この候補を変換対象にする）|同上|

この小例は集団の走行ではない。現設定の種ファイルのmarginalとお店の拡張から作る80語の辞書に、**人工的な辞書外名abc/acb/bac**を与えた。固定席abc、履歴は3名のfrozenset、年齢0、RF=0・RH=0.075、λ=0.01873710622997919。未変更の `v310be.candidates` を呼び、候補Vを実際の保持条件と同じλで比較した。3回の全引数、環境値、状態の作り方、出力は `canonical-model-order-counterexample.json` と `check_hash_order_model.py` に保存した。模型の変換を実行する走行は行っていない。

### 模型側の調査と停止理由

`tools/v39.py:84` の `hist_counts` は、Mappingでない履歴を列挙して辞書を作る。`v39.py:90` の `dict_order` は辞書内には一意の番号を返すが、辞書外には `辞書の長さ + 文字コードの和` を返す。小例の3名は全て374で衝突する。`v39.py:111` の `fixed_spec_bits` はこの鍵だけでstable sortし、固定名の位置jから符号長I(j)を求める。同じ鍵では元の集合列挙順が残るので、上表の3/5ビットに変わる。

その値は `tools/v310be.py:172` のF→H候補のdCへ渡り、198行のV=(RH−RF)/dCに入り、`tools/v39.py:911` のV<λの変換条件へ届く。同点処理を整列している箇所があっても、候補の点そのものがこの前段で変わる。これはコードと人工小例で確認した条件付きの依存であり、今回のお店走行への実際の到達を確認したものではない。

|調べた経路|コード位置|確認した扱い|
|---|---|---|
|穴埋め・候補の確率分布|abm/filling.py:71、92|集合からの候補を整列し、最頻同点は棄権。乱数選択へ渡す分布も整列|
|通常の定義選択と席充填|tools/v39.py:538、548|席番号と選択鍵で整列。辞書の挿入順を読む可能性は指紋でも保持|
|strict-pcと共通構造の候補|tools/strictpc.py:76、tools/ustruct.py:43|関係・写像の組を整列して候補の鍵を作る|
|fix-order2の連結成分|tools/fixorder2.py:180、187、211|集合による探索の後に成分を整列。next(iter(...))は要素1個の条件内|
|構造の同点処理|tools/tiestruct.py:74|構造鍵と定義名・席・種別の補助鍵で整列|
|E候補と受信A・束の作成|tools/v310be.py:365、tools/v311c.py:109、296|定義、名札、席、関係などを明示的に整列|
|保持Bの固定席符号長|tools/v39.py:84、90、111、tools/v310be.py:186|**辞書外の同一鍵で集合順依存を確認。修正せず停止**|

読めた全保存スナップショットのslot_historyについて、現お店辞書の外にある名は{len(inventory['unknown_slot_history_names'])}種だった。この確認の対象は保存された履歴だけであり、全ての到達可能状態に辞書外が無いという証明ではない。実走行で模型の判断が分かれたと推測して成績を論じない。

### 保存済み記録への当て直しと、その限界

条件(1)は、保存された状態を全て読んで当て直せる範囲まで実施した。計{len(files)}圧縮台帳、{inventory['rows_checked']}試行分のfull/deltaを復元して、新しい指紋関数を適用し、旧記録を変更せず別のgzipへ保存した。集団の種21〜40の記録は読んでいない。中断ファイルの読めたprefixも含む。圧縮ファイルが最後まで読めることと、8体のまとめ役が完走したことは分けて扱う。

|保存走行・フォルダ|台帳数|指紋を作った試行数|末尾が欠けた台帳数|
|---|---:|---:|---:|
{filetable}

末尾が欠けた{sum(not f['compressed_file_complete'] for f in files)}ファイルは、完全な台帳として合格扱いにしていない。

{incomplete}

以前比較した腕にも保存スナップショットの新指紋を当て直した。以下は保存JSONの状態の比較であり、生の全型を持つ模型状態と本走行の乱数について、新しい指紋で再走行検査した結果ではない。

|比較|個体対数|比較した試行数（各側）|保存スナップショットの新指紋|
|---|---:|---:|---|
{pairtable}

**旧監査の全状態指紋を当て直す条件(1)は未完。** `.state.jsonl` {len(inventory['legacy_runtime_fingerprint_files'])}ファイル・{inventory['legacy_runtime_rows']}行には旧SHA256の文字しかなく、元の状態は保存されていない。ハッシュから集合順を直して再計算することはできない。既存台帳の `abm/loop.py:652` の保存方式は、集合だけでなくtuple/listも整列し、列内のNoneと一部の空の欄を落とし、辞書の鍵も文字へ変えているため、全ての元の型・列順・乱数状態を復元できない。監査の時点と台帳の時点も異なる。従って、保存JSONの新指紋を、旧監査の生の状態指紋の置換や証明として使わない。

保存JSONの指紋は `coll8_2026-10-03/canonical-saved-v1/`、全ファイルの件数・完備性・旧監査の一覧は `canonical-saved-recheck.json`、比較結果は `canonical-saved-comparisons.json` に保存した。読取り用の台本は同じ証拠フォルダへコピーした。読取り台本の最初の実行ではdeltaの欄名を誤り、1行でKeyErrorとなった。そのログは `canonical-saved-recheck-format-error.log` に残し、模型には触れず、実際の欄 `changes` に合わせて別フォルダへ最初から当て直した。

### 今回の条件と関門の状態

|項目|結果|
|---|---|
|指紋だけを修正し、模型の計算を変えない|差分・AST比較・関連105検査で確認|
|(1) 保存台帳の状態へ新指紋を適用|読めた全{inventory['rows_checked']}試行に実施。中断prefixは別記|
|(1) 旧監査の全状態指紋を再計算|元の状態が未保存のため未完|
|(2) PYTHONHASHSEED=0/1/2の小例で指紋一致|一致。全状態の型と意味のある列順は保持|
|(3) 模型の集合順依存を調査|辞書外名の同一鍵で保持条件に影響する依存を確認|
|(3) 依存があれば直さず停止|該当コードを変更せず停止|
|残りの種1〜3の関門と本走行|再開していない。段Bの全合格は未成立|

### この当て直しの機械記録と全引数

|時点|日時|空き容量bytes|swap使用MiB|他の重い処理数|
|---|---|---:|---:|---:|
{machinetable}

物理メモリは32GiB。開始時の他の重い処理PIDは{foreign}。保存記録の読取りは1プロセスで、機械状態を10秒間隔で確認した。関連検査を実行した時も上限4以内。記録した確認時点の熱・性能の警告は0件、開始から終了までのswapの差は{health['swap_mib'] - start['swap_mib']:.2f}MiB。VM各頁の数とプロセス一覧の原記録は `canonical-initial-machine.json`、`canonical-recheck-initial-machine.json`、`canonical-recheck-latest-machine.json`、`canonical-final-machine.json` に保存した。これは読取り作業の機械記録であり、模型一本の時間・RSSの追加測定ではない。保存状態の読取り所要時間は{inventory['elapsed_seconds']:.3f}秒。元の模型走行の測定値と160本の見積もりは前節の履歴を参照する。

承認後の指紋検査と保存記録の当て直しに使った台本は次のとおり。引数は各JSONにも全て残した。小例の子プロセス `-c` の本文とPYTHONHASHSEEDは `canonical-model-order-counterexample.json`、pytestの15本分の全引数は `canonical-unit-suite.json` に残した。

```text
cwd: {root}
/opt/homebrew/opt/python@3.12/bin/python3.12 check_canonical_fix.py
/opt/homebrew/opt/python@3.12/bin/python3.12 check_hash_order_model.py
/opt/homebrew/opt/python@3.12/bin/python3.12 recheck_saved_fingerprints.py
/opt/homebrew/opt/python@3.12/bin/python3.12 compare_saved_canonical.py
/opt/homebrew/opt/python@3.12/bin/python3.12 build_canonical_report.py
```

保存された記録の確認結果と、人工的な状態での条件付き依存を分けて報告した。模型の修正、残りの関門の再走行、本走行はここから行わない。
'''
text = report.read_text()
assert '## 指紋の修正と模型の集合順依存の調査（最新の停止結果）' not in text
old = text.split('\n\n')[1]
new = '停止報告。集合順に左右されない検査用の指紋へ修正し、保存記録を当て直した。模型側にも辞書外名の同一鍵で集合順依存があることを人工小例で確認したため、ユーザー条件(3)に従い、その箇所は変更せず残りの関門の走行を停止した。最新の結果と保存記録の再計算の限界は末尾の「指紋の修正と模型の集合順依存の調査」。途中の停止・未採点行の原文・台本の差分は履歴として残した。本走行160本は開始していない。'
report.write_text(text.replace(old, new, 1) + section)
print(report)

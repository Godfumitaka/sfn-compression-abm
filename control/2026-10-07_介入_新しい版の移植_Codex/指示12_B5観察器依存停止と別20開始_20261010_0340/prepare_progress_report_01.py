"""B5着手・計算論10草稿・再開予定の保存を同じ報告へ残す。"""
from pathlib import Path
import datetime
import hashlib
import json
import shutil
import sys

here = Path(__file__).resolve().parent
port = here.parents[1]
report = port / 'report'
sys.path.insert(0, str(port))
from admission_guard import census
rows, active, paused = census()
parents = set()
for pid in active | paused:
    parent = rows[pid]['parent']; seen = set()
    while parent in rows and parent not in seen:
        seen.add(parent)
        if parent in active | paused:
            parents.add(parent)
        parent = rows[parent]['parent']
active -= parents; paused -= parents
at = datetime.datetime.now().astimezone().isoformat(timespec='seconds')
assert len(active) < 8 and shutil.disk_usage(here).free >= 20 * 2**30
(here / 'progress_report_before_start_01.json').write_text(json.dumps(dict(at_jst=at, active=len(active),
    paused=len(paused), excluded_parents=sorted(parents), processes=[dict(pid=p, **rows[p]) for p in sorted(active | paused)],
    free_disk_bytes=shutil.disk_usage(here).free), ensure_ascii=False, indent=2) + '\n')
assert json.loads((here / 'automation_B5_verified_02.json').read_text())['all_match']
assert 'Ran 4 tests' in (here / 'audit_tests.log').read_text() and '\nOK\n' in (here / 'audit_tests.log').read_text()
assert json.loads((port / 'instruction12/B7_computational_drafts/changes_sha256.json').read_text())['passed']
evidence = report / 'control/2026-10-07_介入_新しい版の移植_Codex/指示12_B5記録修正と計算論草稿_20261010_0330'
evidence.mkdir(exist_ok=False)
files = {p.name: p for p in here.iterdir() if p.is_file()}
for name in ['status.json', 'before_start.json', 'protected_before.json', 'model.log', 'runtime.json', 'admission_timing_invalid.json']:
    files['B5_pilot20_before/' + name] = here / 'B5_pilot20_before' / name
files['source_candidate/tools/smeshared.py'] = port / 'source_coll_instruction12_B5/tools/smeshared.py'
files['source_baseline/tools/smeshared.py'] = port / 'source_coll_instruction12_baseline/tools/smeshared.py'
for p in (port / 'instruction12/B7_computational_drafts').iterdir():
    files['B7_computational_drafts/' + p.name] = p
for name in ['instruction12_status.json', 'instruction13_status.json']:
    files[name] = port / name
manifest = {}
for name, source in files.items():
    data = source.read_bytes()
    dest = evidence / name
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)
    digest = hashlib.sha256(data).hexdigest()
    assert hashlib.sha256(dest.read_bytes()).hexdigest() == digest
    manifest[name] = dict(source=str(source), sha256=digest, bytes=len(data), snapshot_at_jst=at)
(evidence / 'evidence_sha256.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
main = report / 'control/2026-10-07_介入_新しい版の移植_Codex.md'
heading = '## 指示12B5：指定の監査修正、計算論10草稿と一体ONの測定開始'
text = main.read_text()
assert heading not in text
body = f'\n\n{heading}（{at}）\n\n'
body += 'Aの受け入れ版94dbebc2と本番全argvの報告はbcc5860aで通常push済み。指示12の順にB5・7の計算論の準備へ進んだ。B6のD・D＋注意と人間的な集団化は未着手。指示12・13全体は未完了で、済みを付けない。\n\n'
body += '指定c4cfed12a3944071951775b2c9373ca27705fb25から作った自分の別の枝codex/coll-record-fix-instruction12-2026-10-10に、c57467eab13ee9ef84277059024ab892756fd2f8のtools/smeshared.pyのTypeError時だけの書き出し変更を移した。指定ファイルとの全バイト一致を確認、変更はこの一ファイルだけ。通常受付43249（0.3GB）で、正常記録の字節不変、混合鍵の写しだけの変換、文字列化の衝突停止、鍵以外のTypeErrorを隠さない、の構造4件が通過。候補92913206f5d3b4b4cfbcd1015e0aebf5351bf567を通常push済み。候補は未受け入れで、B5関門全体の合格ではない。\n\n'
body += '同じマックの一体ON200の修正前後の関門を準備し、既存の一体ONの全旗・設定・観察器をそのまま保存した。世界2・種1・f0.1・q0・no-tags・b_n8・B/E価格0.01873710622997919、C*・注意・第二段/HU on。まず元のc4の20試行でメモリを測る一本を通常受付1GBへ通し、03:21:40.266064 JSTに入口43665・模型親43672から開始。保存した時点では走行中で、200の二本と全出力比較は未開始。実出力はinstruction12/B5/B5_pilot20_before/output。\n\n'
body += 'この20の受付前時刻を実時計から保存せず固定値で環境へ記した誤りがあるため、元のstatusのadmission_wait_secondsを受付待ちの実測に使わない。未計測としてadmission_timing_invalid.jsonへ記録した。元記録・模型設定・出力を保持し、再起動しない。後続launch_case.pyはtime.time()を受付の起動直前に保存する。\n\n'
body += '計算論の10草稿は旧cloud/n5の元ファイルを保持した別フォルダへ保存し、変更はcommitを候補92913206へ替えることと--shop-scatter・--horizon 1740の追加だけ。全10件のE価格0.01873710622997919、λの{L50_ref}保持、変更前後SHA256、その他の全argvと旧requiresの不変を確認した。正式な列のλはClaudeが埋める扱いを維持し、本番を開始しない。\n\n'
body += '次は20の自然終了と必要記録・実RSSを受付内で点検し、200のメモリを実測と条件差から埋める。修正前後の一体ON200を同じ機械・起動指紋で一度ずつ通し、compare_on200.pyで既存の集団化の比較関数を使って全実在出力の名前集合・原順・全模型行、side・注意・第二段・控え・乱数・通信・manifest全研究者辞書を照合する。既存の時計と、必須検査した版・物理サイズのメタデータ以外は除かない。不一致なら最初のファイルと行を保存して停止し、候補修正・並べ替え・許容差追加をしない。その後に本番価格20〜50の関門を通す。マックの他の本番2本に八体を重ねず、指示12B8が明示許可したデスクトップ受け箱への依頼を準備する。\n\n'
body += '継続確認の再開情報をA完了・B5測定中へ更新し、native保存のid・kind・name・prompt・rrule・ACTIVE・対象チャットの全欄一致を確認。最初の検証器はAPIのtargetThreadIdと保存のtarget_thread_idの欄名を同一と読んで失敗したため、その失敗証拠を保持し、正しい対応で全欄一致を確認した。期限10/13 09:00 JSTと、変化のない確認は静かにする決まりを維持する。\n\n'
body += f'証拠：{evidence.relative_to(report)}（保存時点の{len(manifest)}ファイルのSHA256）。全旧停止・候補・原命令・一時資料・出力、指示2・3・5・8の未完了、bと正式3b材料の別指示待ち、四つの禁止と受付・CPU・容量・移植関門を維持する。\n'
main.write_text(text + body)
inbox = report / 'control/受け箱/探索の腕と介入の係.md'
text = inbox.read_text()
note = f'\nB5・7の進捗（{at}、control/2026-10-07_介入_新しい版の移植_Codex.md）。Aの全関門報告を通常push後、c4の別枝へ指定c574の監査修正だけを全バイト同じ形で移した。候補92913206を通常push、受付43249の監査構造4件通過。元の一体ON20を受付1GBで03:21:40から測定中。一体ON200の修正前後比較と本番価格20〜50は未開始。計算論10草稿は指定の二旗追加・候補版だけの差分と全SHAを確認。候補は未受け入れ、指示12・13全体は未完了で済みを付けない。\n\n'
assert 'B5・7の進捗（' not in text
inbox.write_text(text.replace('## 指示 13（', note + '## 指示 13（', 1))
for name in ['instruction12_status.json', 'instruction13_status.json']:
    path = port / name; row = json.loads(path.read_text())
    row.update(B5_progress_report_prepared_at_jst=at, B5_progress_evidence=str(evidence), B5_progress_report_pushed=False)
    path.write_text(json.dumps(row, ensure_ascii=False, indent=2) + '\n')
print(json.dumps(dict(evidence=str(evidence), copied_files=len(manifest), at_jst=at), ensure_ascii=False))

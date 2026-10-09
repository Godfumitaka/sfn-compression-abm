"""旧20の観察器停止と、同じ同梱依存を置いた別20の開始を保存する。"""
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
assert len(active) < 8 and shutil.disk_usage(here).free >= 20 * 2**30
at = datetime.datetime.now().astimezone().isoformat(timespec='seconds')
with (here / 'dependency_progress_before_start_01.json').open('x') as f:
    json.dump(dict(at_jst=at, active=len(active), paused=len(paused), excluded_parents=sorted(parents),
        processes=[dict(pid=p, **rows[p]) for p in sorted(active | paused)],
        free_disk_bytes=shutil.disk_usage(here).free), f, ensure_ascii=False, indent=2)
read = lambda p: json.loads(p.read_text())
failure = read(here / 'pilot20_failure_evidence_02.json')
assert failure['protected_unchanged'] and failure['native_ledger_rows'] == 20 and not failure['case_accepted']
assert read(here / 'automation_dependency01_verified.json')['all_match']
retry = here / 'B5_pilot20_before_dependency01'
status = read(retry / 'status.json')
assert status['state'] == 'running'
assert status['admission_wait_seconds'] >= 0 and status['cpu_wait_seconds'] >= 0
assert read(here / 'observer_dependency_01.json')['copied_all_bytes']
evidence = report / 'control/2026-10-07_介入_新しい版の移植_Codex/指示12_B5観察器依存停止と別20開始_20261010_0340'
evidence.mkdir(exist_ok=False)
files = {p.name: p for p in here.iterdir() if p.is_file()}
for case in ['B5_pilot20_before', 'B5_pilot20_before_dependency01']:
    for name in ['status.json', 'before_start.json', 'runtime.json', 'model.log', 'protected_before.json']:
        files[case + '/' + name] = here / case / name
for name in ['protected_after.json', 'admission_timing_invalid.json', 'output/manifest.jsonl', 'output/comm/run001.summary.json']:
    files['B5_pilot20_before/' + name] = here / 'B5_pilot20_before' / name
for p in (here / 'cloud_gate_request_draft01').iterdir():
    files['cloud_gate_request_draft01/' + p.name] = p
for name in ['instruction12_status.json', 'instruction13_status.json']:
    files[name] = port / name
manifest = {}
for name, source in files.items():
    data = source.read_bytes()
    dest = evidence / name
    dest.parent.mkdir(parents=True, exist_ok=True)
    with dest.open('xb') as f:
        f.write(data)
    digest = hashlib.sha256(data).hexdigest()
    assert hashlib.sha256(dest.read_bytes()).hexdigest() == digest
    manifest[name] = dict(source=str(source), sha256=digest, bytes=len(data), snapshot_at_jst=at)
with (evidence / 'evidence_sha256.json').open('x') as f:
    json.dump(manifest, f, ensure_ascii=False, indent=2); f.write('\n')
main = report / 'control/2026-10-07_介入_新しい版の移植_Codex.md'
heading = '## 指示12B5：観察器の同梱依存不足、別出力の20試行で確認'
text = main.read_text()
assert heading not in text
body = f'\n\n{heading}（{at}）\n\n'
body += '旧B5_pilot20_beforeは03:36:09.645270 JSTに外側終了0となった。通常受付46787（0.3GB）で台帳全20件（0〜19）・実版と物理サイズを照合した完了札・性能20件・旧資料430ファイルの前後不変を確認した。しかし、模型の計算が終わった後、観察器observe.pyの最終控えがruntime_captureをimportできず、manifestと通信集計のagentにerrorが残っている。最初のエラーはmodel.logの9行目、ModuleNotFoundError: No module named runtime_capture。通信のerrorsが空でもagentがerrorなので、旧一本を関門完了にしない。外側終了0だけで進めず、200は未開始。模型の修正前後の出力の不一致を検出したものではない。\n\n'
body += '旧一本の模型時間869.372049秒、最大agent RSS87490560バイト、最大children RSS87654400バイト、CPU枠待ち0.060241秒。旧受付待ちは固定した時刻の保存誤りのため未計測を維持する。最初の点検器46700はrg --filesで除外された実在の台帳を不存在と読んで止まったため、旧検査とログを保持した別点検器46787で実体の台帳と完了札を全量確認した。比較条件や模型を変更していない。\n\n'
body += '不足したruntime_capture.pyは元の集団化の包み（集団化_クラウドの包み_2026-10-09）に同梱されていた。自分のB5の観察器の横へ全バイト同じ形で複製し、SHA256 232eafb5d199316b6fbdd244498a6b8b8bfe0d33ff5db1b0f391afc3ac337551とimport先を点検した。候補92913206・元のc4・abm/toolsの模型、設定、observe.pyの原字節と計算は変えていない。元の命令・停止・全出力と原検査を保持し、commands_dependency01.json・run_case_dependency01.py・launch_case_dependency01.py・protected_with_dependency_01.jsonを別保存した。\n\n'
body += '元20と同じ全旗・同じマック・種1の別出力B5_pilot20_before_dependency01を、03:40:06.923133 JSTに通常受付46813（owner intervention-instruction12-B5_pilot20_before_dependency01、1GB）、入口46817・模型親46824から一度開始した。実時計で保存した受付待ち0.161169秒、CPU枠待ち0.055293秒。開始前の実模型2・停止0、親の二重計数を除き全体8本の上限、空き184724148224バイトと受付を維持した。保存時点では走行中。模型設定を途中で変えず、自然終了と必要記録を待つ。\n\n'
body += '次はverify_case_dependency01.pyを通常受付へ通し、別20の台帳全件・完了札・manifestと通信の全agentにerrorなし・最終控えと全乱数・旧資料不変・実RSSを確認してから、200の二本の予約を実測と条件差で埋める。外側の終了だけで通さない。合格後に同じ同梱依存を使った一体ON200の修正前後を各一本ずつ通し、既存compare_on200.pyで全出力の名前集合・全模型行・原順・状態・乱数・全研究者辞書を照合する。候補は未受け入れ、B5全関門は未合格。不一致なら最初のファイルと行を保存して停止し、候補修正・並べ替え・許容差追加をしない。\n\n'
body += '八体20の依頼控えはcloud_gate_request_draft01へ別保存。元の計算論f0.1・種1の草稿から試行数1740→20とB価格の指定値だけを変更した全argv、設定、変更前後SHAを保存した。現時点では未依頼・未走行。B5の一体ON200全出力一致後に、指示12B8の範囲でデスクトップ受け箱の「走行の係から」へ依頼する。実CPU8枠・実測予約・受付・容量・永続出力先を先に確認し、八体をマックの他の本番へ重ねない。旧cloud_run.pyの版・phase・期限・関門の決まりを外して使わない。\n\n'
body += '継続確認の保存状態を旧20の観察器停止・別20走行中へ更新し、nativeの全7欄（全文・期限・ACTIVE・対象チャットを含む）の一致を確認。指示12・13はB未完了で済みを付けない。B6・人間的な集団化・正式3b材料・実材料介入・本番は未開始。Aの完了、指示9〜11の済み、指示2・3・5・8の未完了とb・正式材料の別指示待ちを維持。四つの禁止と受付・CPU・容量・移植関門、期限10/13 09:00 JSTを維持し、全旧停止・候補・一時資料・全命令・出力を保持する。\n\n'
body += f'証拠：{evidence.relative_to(report)}。原出力はinstruction12/B5の旧20と別20へ保持し、保存時点の{len(manifest)}ファイルを全SHA付きで報告Gitへ複製した。\n'
main.write_text(text + body)
inbox = report / 'control/受け箱/探索の腕と介入の係.md'
text = inbox.read_text()
note = f'\nB5の観察器依存と別20（{at}、control/2026-10-07_介入_新しい版の移植_Codex.md）。旧20の外側終了0と台帳20・完了札を確認したが、最終控えのruntime_capture依存不足によりmanifest/agentがerror。関門完了とせず、旧停止と全出力を保持。元の包みの同梱依存だけを全バイト複製して、同じ模型・全旗の別20を03:40:06 JSTに受付46813（1GB）から一度開始。候補92913206・観察器・設定は未変更。200・八体依頼・B6・本番は未開始、指示12・13は未完了。\n\n'
assert 'B5の観察器依存と別20（' not in text
inbox.write_text(text.replace('## 指示 13（', note + '## 指示 13（', 1))
for name in ['instruction12_status.json', 'instruction13_status.json']:
    path = port / name; value = read(path)
    value.update(B5_dependency_report_prepared_at_jst=at, B5_dependency_report_evidence=str(evidence), B5_dependency_report_pushed=False)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
print(json.dumps(dict(evidence=str(evidence), copied_files=len(manifest), at_jst=at), ensure_ascii=False))

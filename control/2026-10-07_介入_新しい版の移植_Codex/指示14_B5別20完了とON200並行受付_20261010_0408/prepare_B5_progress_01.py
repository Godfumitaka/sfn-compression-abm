"""指示14の受領・通常受付の状況と別20の必要記録を保存する。"""
from pathlib import Path
import datetime
import hashlib
import json
import shutil
import subprocess
import sys

here = Path(__file__).resolve().parent
port = here.parent
b5 = port / 'instruction12/B5'
report = port / 'report'
sys.path.insert(0, str(port))
from admission_guard import census

read = lambda p: json.loads(p.read_text())
at = datetime.datetime.now().astimezone().isoformat(timespec='seconds')
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
assert len(active) <= 8 and shutil.disk_usage(b5).free >= 20 * 2**30
warning = dict(at_jst=at, reason='修正後200の受付ログが22GB+3GB>24GBで待機を記録した。予約を減らさず通常受付で待つ。',
    active=len(active), paused=len(paused), excluded_parents=sorted(parents),
    processes=[dict(pid=p, **rows[p]) for p in sorted(active | paused)],
    free_disk_bytes=shutil.disk_usage(b5).free,
    thermal=subprocess.check_output(['pmset', '-g', 'therm'], text=True),
    swap=subprocess.check_output(['sysctl', 'vm.swapusage'], text=True),
    admission_log=(b5 / 'B5_on200_after_admission.log').read_text())
with (here / 'on200_admission_warning_01.json').open('x') as f:
    json.dump(warning, f, ensure_ascii=False, indent=2); f.write('\n')
pilot = read(b5 / 'B5_pilot20_before_dependency01_verification_01.json')
assert pilot['passed'] and pilot['trial_count'] == 20 and pilot['protected_unchanged']
current = {}
for label in ['B5_on200_before', 'B5_on200_after']:
    request = read(b5 / (label + '_launch_request.json'))
    p = b5 / label / 'status.json'
    current[label] = dict(request=request, status=read(p) if p.exists() else None)
    assert request['production_started'] is False
    if p.exists():
        assert current[label]['status']['state'] == 'running'
assert current['B5_on200_before']['status'] is not None
running = [label for label, row in current.items() if row['status']]
queued = [label for label, row in current.items() if not row['status']]
state = 'B5_on200_both_running' if not queued else 'B5_on200_before_running_after_admission_wait'
for name in ['instruction12_status.json', 'instruction13_status.json', 'instruction14_status.json']:
    path = port / name; value = read(path)
    value.update(state=state, completed=False, running_labels=running, queued_labels=queued,
        B5_on200_submitted=True, B5_on200_started=True,
        B5_on200_commands=str(b5 / 'commands_dependency01.json'),
        B5_pilot_verified=True, B5_pilot_verification=str(b5 / 'B5_pilot20_before_dependency01_verification_01.json'),
        B5_pilot_completed_at_jst=pilot['completed_at_jst'],
        B5_on200_sessions=dict(B5_on200_before=94535, B5_on200_after=13073),
        B5_on200_admission_pids={label: row['request']['admission_pid'] for label,row in current.items()},
        B5_on200_reservation_gb_each=3,
        B5_cloud_gate_requested=True, B5_cloud_gate_request_commit='c0c3839536f8688a11062dceb9d5fbb1161c7332',
        B5_cloud_gate_request=str(here / 'cloud_gate_request_01'),
        B5_cloud_gate_started=False, B5_candidate_accepted=False, B6_started=False,
        next_action='二本の保存状態と受付待ちを読む。模型・比較を重複起動しない。200両側の自然終了と必要記録を通常受付で確認後、既存compare_on200.pyで全出力・全控え・乱数を照合。デスクトップへのB5(b)依頼の回答を根拠として読む。B5(a/b)が実際に揃ってからB6へ。')
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')

evidence = report / 'control/2026-10-07_介入_新しい版の移植_Codex/指示14_B5別20完了とON200並行受付_20261010_0408'
evidence.mkdir(exist_ok=False)
files = {p.name: p for p in here.iterdir() if p.is_file() and not p.name.startswith('automation')}
for name in ['instruction12_status.json', 'instruction13_status.json', 'instruction14_status.json']:
    files[name] = port / name
for name in ['B5_pilot20_before_dependency01_verification_01.json',
        'B5_pilot20_before_dependency01_verification_before_start_01.json',
        'pilot_dependency_verification_admission_01.log', 'commands_dependency01.json',
        'commands_dependency01_before_reservation_01.json', 'on200_reservation_evidence_01.json',
        'run_case_dependency01.py', 'launch_case_dependency01.py', 'verify_case_dependency01.py',
        'compare_on200.py', 'reference_compare.py', 'command_reference.json', 'observe.py',
        'runtime_capture.py', 'observer_dependency_01.json', 'protected_with_dependency_01.json',
        'shop_f0.1.json']:
    files[name] = b5 / name
pilot_dir = b5 / 'B5_pilot20_before_dependency01'
for name in ['status.json', 'runtime.json', 'before_start.json', 'protected_before.json',
        'protected_after.json', 'model.log', 'output/manifest.jsonl', 'output/comm/run001.summary.json',
        'agent0.performance.jsonl', 'agent0.validation.jsonl']:
    files['pilot20/' + name] = pilot_dir / name
for label, row in current.items():
    for name in ['status.json', 'runtime.json', 'before_start.json', 'protected_before.json', 'model.log']:
        p = b5 / label / name
        if p.exists():
            files[label + '/' + name] = p
    for tail in ['admission.log', 'launch_request.json']:
        files[label + '_' + tail] = b5 / (label + '_' + tail)
manifest = {}
for name, source in files.items():
    data = source.read_bytes(); dest = evidence / name
    dest.parent.mkdir(parents=True, exist_ok=True)
    with dest.open('xb') as f:
        f.write(data)
    assert dest.read_bytes() == data
    manifest[name] = dict(source=str(source), sha256=hashlib.sha256(data).hexdigest(), bytes=len(data), snapshot_at_jst=at)
with (evidence / 'evidence_sha256.json').open('x') as f:
    json.dump(manifest, f, ensure_ascii=False, indent=2); f.write('\n')
main = report / 'control/2026-10-07_介入_新しい版の移植_Codex.md'
heading = '## 指示14：別20の必要記録が揃い、B5のON200二本を並行受付、八体20を依頼'
text = main.read_text(); assert heading not in text
before = current['B5_on200_before']['status']
body = f'\n\n{heading}（{at}）\n\n'
body += '自分の番号付き指示14（03:51）を04:06:45.976489 JSTに受領し、受領コミット31615bbb72847e4c99e04c0ba06fcb071cacc721を先に通常pushした。B5の修正前後ON200は同じマックで同時に通常受付へ通し、本番価格の短いB5(b)も並行して依頼する。B5(a)を(b)の開始前に待つ順だけを指示14で更新し、二つの合格条件と既存c4の関門、四つの禁止、受付・CPU・容量を維持する。\n\n'
body += f'同梱依存を置いた別20は{pilot["completed_at_jst"]}に自然終了0。通常受付50532（0.3GB）で04:07:28に台帳20件・実版と物理サイズを照合した完了札・manifest1辞書・通信全agentのerrorなし・辞書外0・辞書点検40回・最終SME/C*の控え・模型とPythonの乱数各20件・Python大域乱数不変・性能全20件・旧資料431ファイル不変を確認した。外側終了0だけで通していない。模型時間{pilot["model_seconds"]:.6f}秒、受付待ち{pilot["admission_wait_seconds"]:.6f}秒、CPU枠待ち{pilot["cpu_wait_seconds"]:.6f}秒、最大agent RSS{pilot["peak_agent_rss_bytes"]}バイト、最終控えを含む最大children RSS{pilot["peak_children_rss_bytes"]}バイト。旧20の依存不足と全停止資料は保持する。\n\n'
body += '200の予約は最大children RSSを試行数比10倍し25%余裕を付けた3049676800バイトの見込みを3GiBへ切り上げ、各3GBに保存した。これは予約用見込みで、200の確定実測とはしない。元のcommands_dependency01.jsonを別名で保持し、reservation_gbだけの変更と全SHAを保存。設定・観察器・全模型argvは変えていない。\n\n'
body += f'修正前B5_on200_before（元c4）は通常受付50885（3GB）、入口{before["wrapper_pid"]}・模型親{before["model_parent_pid"]}から{before["started_at_jst"]}に一度開始。受付待ち{before["admission_wait_seconds"]:.6f}秒、CPU枠待ち{before["cpu_wait_seconds"]:.6f}秒。修正後B5_on200_after（候補92913206）は04:08:37.710022 JSTに通常受付50927（3GB）へ一度投入した。'
if queued:
    body += '受付表22GB＋予約3GBが24GBを超えるため、修正後は受付待ちで模型未開始。予約を下げず、走っている本番を止めず、同じ待つ受付を保持する。'
else:
    after = current['B5_on200_after']['status']
    body += f'修正後も{after["started_at_jst"]}に模型開始した。'
body += f'資源警告時の機械状態を一回保存し、親の二重計数を除いて実模型{len(active)}・停止{len(paused)}、空き{warning["free_disk_bytes"]}バイト。全体8本上限を維持する。\n\n'
body += '両側とも一体・世界2・種1・f0.1、q/m0、no-tags、名札長8、B/E0.01873710622997919、C*・注意・第二段/HU on、元の設定と試験行を固定。保存済み二本の自然終了を待ち、verify_case_dependency01.pyで全必要記録を通常受付内で点検してからcompare_on200.pyで全実在模型出力の名前集合・全行・原順・原字節・manifest全研究者辞書・最終控え・全乱数を既存の同じ関数で比べる。除外は既存時間と、実版・実物理サイズを必須照合したメタデータだけ。一件でも違えば最初のファイルと行を保存して停止し、候補修正・並べ替え・許容差追加をしない。\n\n'
body += 'B5(b)八体20の具体的な全argv・設定・候補版92913206の差分bundle・元観察器と同梱依存・全SHAを別包みに固定した。指示12B8・14の範囲でデスクトップの受け箱の「走行の係から」へ依頼し、通常push c0c3839536f8688a11062dceb9d5fbb1161c7332で届けた。世界2・種1・f0.1、q0.2・m0.1、受信A、C*・注意・第二段/HU on、B0.00035129738499384776・E0.01873710622997919・shop-scatter・horizon1740の先頭20。既存の五つのc4の関門を残し、B5(a)の一致はB5受け入れの条件として残す。実CPU8枠・実測予約・永続実出力先・正式受付入口が揃うまで待つ。マックの他の模型へ八体を重ねず、旧cloud_run.pyの版・phase・期限・証明を外して使わない。現時点では依頼済み、八体は未走行・B5全体は未合格。\n\n'
body += '候補92913206は未受け入れ。B6・人間的な集団化はB5(a/b)の実際の完了後であり、指示13の試験・反実仮想でDの包みに入る前の抑止、全ST/AUDITとD記録の前後不変を引き継ぐ。指示12・13・14は未完了、済みを付けない。Aと指示9〜11の済みを再実行せず、指示2・3・5・8、bのアストラ仕様判断待ち、正式3b材料の別指示待ちを維持する。期限10/13 09:00 JST、全旧停止・候補・一時資料・命令・出力を保持する。\n\n'
body += f'証拠：{evidence.relative_to(report)}（{len(manifest)}ファイル、全SHA）。八体依頼はcontrol/2026-10-07_介入_新しい版の移植_Codex/指示14_B5八体20クラウド依頼_20261010_0411。\n'
main.write_text(text + body)
inbox = report / 'control/受け箱/探索の腕と介入の係.md'
text = inbox.read_text()
note = f'\nB5の並行受付と依頼（{at}、control/2026-10-07_介入_新しい版の移植_Codex.md）。別20の自然終了0と全必要記録を受付50532で確認し、実測からON200の修正前後を各3GBで同じマックへ同時投入。修正前50885は04:08:25 JSTから走行中、修正後50927は受付表22+3>24GBで待機。予約と受付条件を維持。八体の本番価格20はデスクトップ受け箱へ通常push c0c38395で依頼済み、未走行。B5全関門と指示12・13・14は未完了、候補92913206は未受け入れ、B6・本番は始めない。\n'
assert 'B5の並行受付と依頼（' not in text
inbox.write_text(text + note)
for name in ['instruction12_status.json', 'instruction13_status.json', 'instruction14_status.json']:
    path = port / name; value = read(path)
    value.update(B5_on200_report_prepared_at_jst=at, B5_on200_report_evidence=str(evidence), B5_on200_report_pushed=False)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
print(json.dumps(dict(at_jst=at, state=state, files=len(manifest), evidence=str(evidence)), ensure_ascii=False))

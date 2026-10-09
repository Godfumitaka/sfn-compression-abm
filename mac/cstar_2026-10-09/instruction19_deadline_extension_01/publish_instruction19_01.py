"""指示19の予定の保存結果と二つの確認を、追記と通常pushで報告する。"""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import fcntl
import hashlib
import json
import re
import shutil
import subprocess

private = Path(__file__).resolve().parent
root = private.parent
repo = root / 'codex_worldv4_2026-10-01/results'
marker = private / 'instruction19_reported_01.json'
assert not marker.exists(), '指示19の完了報告を重複しない'
phases = ('heartbeat_20261009_2221', 'heartbeat_20261009_2228')
snapshots = [json.loads((private / (p + '.json')).read_text()) for p in phases]
initial, latest = snapshots
receipt = json.loads((private / 'instruction19_received_01.json').read_text())
automation = json.loads((private / 'instruction19_automation_01.json').read_text())
sampler = json.loads((private / (phases[1] + '_sampler.json')).read_text())
assert receipt['received'] and automation['updated'] and automation['schedule_until_verified']
assert automation['deadline'] == '2026-10-13T09:00:00+09:00'
assert automation['interval_minutes'] == 30 and automation['status'] == 'ACTIVE'
assert automation['quiet_policy_preserved'] and automation['historical_prompt_after_first_paragraph_preserved']
assert sampler['ps_exit'] == 0 and sampler['starts'] == 0
assert 'caffeinate -i -t 200332' in sampler['ps'] and 'jobs.py sampler' in sampler['ps']
assert not latest['eligible_mac_rows'] and not latest['own_controllers']
assert not any(not x['received'] and not x['held'] for x in latest['instructions'])
assert latest['cpu']['own_compute_count'] == latest['cpu']['own_reserved_slots'] == 0
assert latest['resources']['free_bytes'] >= 20 * 2**30
for phase in phases:
    assert not (private / (phase + '_reported.json')).exists()

inbox = 'control/受け箱/SMEの係.md'
report = 'control/2026-10-07_C星の照合とディリクレ_実装_Codex.md'
progress = 'control/2026-09-30_Codex_進み具合.md'
proof = 'mac/cstar_2026-10-09/instruction19_deadline_extension_01'


def git(*args):
    p = subprocess.run(['git', *args], cwd=repo, text=True, capture_output=True)
    with (private / 'instruction19_publish_git_01.jsonl').open('a') as f:
        f.write(json.dumps({'at': datetime.now(ZoneInfo('Asia/Tokyo')).isoformat(),
                           'args': args, 'exit': p.returncode, 'out': p.stdout,
                           'err': p.stderr}, ensure_ascii=False) + '\n')
    if p.returncode:
        raise RuntimeError(p.stderr)
    return p.stdout


def confirmation(d):
    received = [re.search(r'指示 (\d+)', x['header'])[1] for x in d['instructions'] if x['received']]
    done = [re.search(r'指示 (\d+)', x['header'])[1] for x in d['instructions'] if x['done']]
    held = [re.search(r'指示 (\d+)', x['header'])[1] for x in d['instructions'] if x['held']]
    unread = [re.search(r'指示 (\d+)', x['header'])[1] for x in d['instructions'] if not x['received'] and not x['held']]
    c = d['cpu']
    return ('確認時刻' + d['at'] + '、取り込み' + d['fetched_commit'] + '。受領済み指示' +
            '・'.join(received) + '、済み' + '・'.join(done) + '、指示全体の保留' +
            ('・'.join(held) if held else '0件') + '、新規未受領' + str(len(unread)) + '件' +
            ('（指示' + '・'.join(unread) + '）' if unread else '') + '、取得可能行0件。'
            '模型の過程は自分' + str(c['own_compute_count']) + '・他' + str(c['external_count']) +
            '・計' + str(c['total_compute_count']) + '本、上限8。待機中の小さい模型の子も数え、'
            '親の二重計上とSIGSTOP中の子は除く。空き（' + d['at'] + '）。'
            '空き容量' + str(d['resources']['free_bytes']) + 'バイト（' +
            format(d['resources']['free_bytes'] / 2**30, '.3f') + 'GiB）。スワップ' +
            str(d['resources']['swap_mb']) + 'MB、直近増加なし、熱警告なし。'
            '旧診断3欄の省略の仕様確認1件は保留。\n\n')


try:
    with (root / 'codex_sme_light_2026-10-04/control_writer_01.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        assert not git('status', '--porcelain').strip(), '汚れた作業状態のため停止'
        git('fetch', 'origin', 'results-2026-09-27')
        git('rebase', 'origin/results-2026-09-27')
        current = git('rev-parse', 'origin/results-2026-09-27').strip()
        for path in (inbox, 'control/受け箱/README.md', 'control/走行の列_2026-10-08.md'):
            assert git('show', current + ':' + path) == latest['files'][path], '受け箱・README・列の更新を読み直す'
        at = datetime.now(ZoneInfo('Asia/Tokyo')).isoformat()
        p = repo / inbox
        text = p.read_text()
        m = re.search(r'(?ms)^## 指示 19（.*?(?=^## 指示 |\Z)', text)
        assert m and '受領（' in m.group() and '済み（' not in m.group()
        addition = ('\n- 済み（' + at + '、SMEの係、2026-10-07_C星の照合とディリクレ_実装_Codex.md）：'
                    '既存の継続確認1件を30分間隔・2026-10-13 09:00日本時間までに更新し、保存内容と終了時刻を照合。'
                    '四つの禁止と受付・資源・関門・静かな継続を維持。模型と眠り止めの新規起動0件。\n')
        p.write_text(text[:m.end()] + addition + text[m.end():])
        title = '### 指示19：継続確認の期限延長（' + at + '）'
        old = (repo / report).read_text()
        assert title not in old
        line = len(old.splitlines()) + 2
        lines = ('\n' + title + '\n\n'
                 '受領は' + receipt['at'] + '、コミット' + receipt['commit'] + 'で通常push。'
                 'READMEの10/13 9:00までの延長とアストラの承認「伸ばしていい」（台帳D-07γω）を読了。'
                 '前もっての承認と継続確認の運用上の期限は2026-10-13 09:00日本時間。'
                 '10/9と10/11の古い運用上の期限もこの更新で扱い、過去の実行時刻と完了記録は保存。\n\n'
                 '既存の予定sme-25-cを' + automation['at'] + 'に更新して保存を照合。'
                 '有効、30分間隔、終了2026-10-13 09:00日本時間、同じチャット。新規の予定作成0件。'
                 '保存された本文のSHA256は' + automation['prompt_sha256'] + '。'
                 '変化のないときは静かに継続し、完了・失敗・必要な人間の判断だけを知らせる。'
                 '期限以降の新規作業開始を止めて継続確認を終了し、動いている処理を期限だけで止めない。'
                 '予定の保存の自動承認の拒否0件。\n\n'
                 '四つの禁止と受付・資源・関門を維持。受け箱と報告の追記どうしの衝突は、'
                 '指示19により双方の追記を両方残して通常pushで続けてよい。'
                 '追記以外の汚れや衝突は止めて報告する。既存の記録の削除・書換え・force pushは0件。\n\n'
                 + confirmation(initial) + confirmation(latest) +
                 '更新後の確認時には指示19は受領済み・未完了で、今回の済みの追記で完了。'
                 '指示12は完了済み。指示9・13・案(b)・較正・4は未完了。'
                 'GC・encodeの全長はデスクトップ係の結果待ち、Macの旧gates_01は開始していない。\n\n'
                 '21:22:14の空き265420800バイトの下限割れの後、上の二つの確認で空き容量の回復を確認。'
                 'このチャットで容量を回復するための削除・過程の停止は0件。'
                 '指示17のcaffeinate PID13200とsampler PID97541は' + sampler['at'] +
                 'のpsで存続。重複起動0件。既存の眠り止めの命令は-i -t 200332のまま。'
                 '今回の模型の新規起動0件、本番の版と旗の変更0件、種21〜40への操作0件。'
                 '小さい証拠は' + proof + '。報告前の取り込み' + current + '。\n')
        with (repo / report).open('a') as f:
            f.write(lines)
        with (repo / progress).open('a') as f:
            f.write('\n- ' + at + '：SMEの指示19を完了。継続確認は30分間隔・10/13 09:00日本時間まで。'
                    '確認時刻' + latest['at'] + '、取り込み' + latest['fetched_commit'] + '、未受領0・取得可能行0、'
                    '模型自分0・他' + str(latest['cpu']['external_count']) + '・計' +
                    str(latest['cpu']['total_compute_count']) + '。空き容量' +
                    format(latest['resources']['free_bytes'] / 2**30, '.3f') + 'GiBへ回復。新規起動・停止・削除0件。\n')
        dest = repo / proof
        dest.mkdir(parents=True, exist_ok=False)
        names = ['instruction19_received_01.json', 'instruction19_automation_prepared_01.json',
                 'instruction19_automation_args_01.json', 'instruction19_automation_01.json',
                 'publish_instruction19_01.py']
        for phase in phases:
            names += [phase + '.json', phase + '_sampler.json']
        for name in names:
            source = private / name
            assert source.stat().st_size < 10 * 2**20
            shutil.copy2(source, dest / name)
        (dest / 'sha256.json').write_text(json.dumps(
            {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in dest.iterdir() if p.is_file()},
            ensure_ascii=False, indent=2) + '\n')
        git('sparse-checkout', 'add', proof)
        git('add', '--sparse', inbox, report, progress, proof)
        git('commit', '-m', 'SMEの指示19の期限延長と空き容量の回復を記録')
        git('fetch', 'origin', 'results-2026-09-27')
        git('rebase', 'origin/results-2026-09-27')
        p = subprocess.run(['git', 'push', 'origin', 'HEAD:results-2026-09-27'],
                           cwd=repo, capture_output=True, text=True)
        if p.returncode and any(x in p.stderr for x in ('fetch first', 'fetch-first', 'non-fast-forward')):
            git('fetch', 'origin', 'results-2026-09-27')
            git('rebase', 'origin/results-2026-09-27')
            git('push', 'origin', 'HEAD:results-2026-09-27')
        elif p.returncode:
            raise RuntimeError(p.stderr)
        result = {'at': at, 'instruction': 19, 'done': True, 'reported': True,
                  'commit': git('rev-parse', 'HEAD').strip(), 'report': report, 'line': line,
                  'proof': proof, 'deadline': automation['deadline'], 'interval_minutes': 30,
                  'models_started': 0, 'process_stops': 0, 'deletions': 0}
        marker.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
        for phase, d in zip(phases, snapshots):
            (private / (phase + '_reported.json')).write_text(json.dumps(
                dict(result, confirmation_at=d['at'], included_in='instruction19'),
                ensure_ascii=False, indent=2) + '\n')
        p = private / 'pending_01.json'
        pending = json.loads(p.read_text())
        pending.update(instruction19_received=True, instruction19_done=True,
                       instruction19_report=result, heartbeat_deadline=automation['deadline'],
                       caffeinate_approved_deadline=automation['deadline'])
        p.write_text(json.dumps(pending, ensure_ascii=False, indent=2) + '\n')
        print(json.dumps(result, ensure_ascii=False))
except Exception as e:
    (private / 'instruction19_publish_stop_01.json').write_text(json.dumps(
        {'at': datetime.now(ZoneInfo('Asia/Tokyo')).isoformat(), 'reason': str(e),
         'conflicts_not_resolved': True}, ensure_ascii=False, indent=2) + '\n')
    raise

"""指示17の受領、期限付きの眠り止め、延長の完了報告を各一度だけ行う。"""
from pathlib import Path
from datetime import datetime, timedelta, timezone
import fcntl, hashlib, json, re, shutil, subprocess, sys

R = Path(__file__).resolve().parent
REPO = R.parent / 'codex_worldv4_2026-10-01/results'
LOCK = R.parent / 'codex_sme_light_2026-10-04/control_writer_01.lock'
INBOX = 'control/受け箱/SMEの係.md'
README = 'control/受け箱/README.md'
REPORT = 'control/2026-10-08_C星の一本の時間の内訳_Codex.md'
MAIN = 'control/2026-10-07_C星の照合とディリクレ_実装_Codex.md'
JST = timezone(timedelta(hours=9))
DEADLINE = datetime(2026, 10, 11, 9, tzinfo=JST)
PATTERN = r'(^## 指示 17（.*?)(?=^## 指示 |\Z)'

def now():
    return datetime.now(JST).isoformat()

def save(path, data):
    with path.open('x') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write('\n')

def git(*args):
    p = subprocess.run(['git', *args], cwd=REPO, capture_output=True, text=True)
    with (R / 'instruction17_git_01.jsonl').open('a') as f:
        f.write(json.dumps(dict(at=now(), args=args, exit=p.returncode,
                               out=p.stdout, err=p.stderr), ensure_ascii=False) + '\n')
    if p.returncode:
        raise RuntimeError(p.stderr)
    return p.stdout

def latest():
    assert not git('status', '--porcelain').strip(), '汚れた作業状態。解決しない'
    git('fetch', 'origin', 'results-2026-09-27')
    git('rebase', 'origin/results-2026-09-27')
    body = (REPO / INBOX).read_text()
    section = re.search(PATTERN, body, re.M | re.S)
    readme = (REPO / README).read_text()
    assert section and '2026-10-11 09:00' in section[1]
    assert '10/11 9:00 までの延長' in readme and '台帳 D-07βι' in readme
    assert '2026-10-11 09:00' in readme
    return body, section

def publish(message, paths):
    git('add', '--sparse', *paths)
    git('commit', '-m', message)
    git('fetch', 'origin', 'results-2026-09-27')
    git('rebase', 'origin/results-2026-09-27')
    git('push', 'origin', 'HEAD:results-2026-09-27')
    return git('rev-parse', 'HEAD').strip()

mode = sys.argv[1]
assert mode in ('receive', 'start', 'report')
try:
    if mode == 'start':
        with (R / 'instruction17_start_01.lock').open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            assert json.loads((R / 'instruction17_received_01.json').read_text())['received']
            assert not (R / 'instruction17_caffeinate_claim_01.json').exists(), '眠り止めの重複起動をしない'
            assert not (R / 'instruction17_caffeinate_01.json').exists()
            ps = subprocess.run(['ps', '-axo', 'pid=,comm=,args='], capture_output=True, text=True)
            assert ps.returncode == 0
            existing = [row for row in ps.stdout.splitlines()
                        if len(row.split(None, 2)) == 3 and Path(row.split(None, 2)[1]).name == 'caffeinate']
            assert not existing, '既存のcaffeinateがある。重複起動せず状態を読む'
            at = datetime.now(JST)
            seconds = int((DEADLINE - at).total_seconds())
            assert seconds > 0, '延長した期限以降に起動しない'
            command = ['/usr/bin/caffeinate', '-i', '-t', str(seconds)]
            save(R / 'instruction17_caffeinate_claim_01.json', dict(
                at=at.isoformat(), instruction=17, deadline=DEADLINE.isoformat(),
                duration_seconds=seconds, command=command, existing_caffeinate=existing))
            with (R / 'instruction17_caffeinate_01.log').open('ab') as log:
                process = subprocess.Popen(command, stdin=subprocess.DEVNULL,
                                           stdout=log, stderr=log, start_new_session=True)
            check = subprocess.run(['ps', '-p', str(process.pid), '-o', 'pid=,ppid=,stat=,command='],
                                   capture_output=True, text=True)
            assert process.poll() is None and check.returncode == 0 and 'caffeinate -i -t' in check.stdout
            power = subprocess.run(['pmset', '-g'], capture_output=True, text=True)
            assert power.returncode == 0
            result = dict(at=now(), instruction=17, started=True, pid=process.pid,
                          command=command, deadline=DEADLINE.isoformat(),
                          duration_seconds=seconds,
                          planned_expiration=(at + timedelta(seconds=seconds)).isoformat(),
                          ps=dict(exit=check.returncode, out=check.stdout, err=check.stderr),
                          pmset=dict(exit=power.returncode, out=power.stdout, err=power.stderr),
                          existing_caffeinate=existing, processes_stopped=0, models_started=0)
            save(R / 'instruction17_caffeinate_01.json', result)
    else:
        marker = R / ('instruction17_received_01.json' if mode == 'receive' else 'instruction17_reported_01.json')
        assert not marker.exists(), '受領・報告を重複しない'
        with LOCK.open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            body, section = latest()
            at = now()
            if mode == 'receive':
                assert '受領（' not in section[1]
                addition = f'\n- 受領（{at}、SMEの係）：READMEのアストラ承認（台帳D-07βι）を確認。既存の眠り止めと電源の状態を読み、10月11日09:00日本時間までの期限付きcaffeinateを一度だけ起動する。継続確認の期限も同時刻へ延長し、30分間隔を維持する。四つの禁止、受付・関門・資源の決まりを維持。\n\n'
                (REPO / INBOX).write_text(body[:section.end()] + addition + body[section.end():])
                commit = publish('指示17の眠り止めと継続確認の期限延長を受領', [INBOX])
                result = dict(at=at, instruction=17, received=True, commit=commit, deadline=DEADLINE.isoformat())
            else:
                assert '受領（' in section[1] and '済み（' not in section[1]
                assert all('受領（' in s for s in re.findall(r'^## 指示 .*?(?=^## 指示 |\Z)', body, re.M | re.S)), '新しい指示を先に読む'
                sleep = json.loads((R / 'instruction17_caffeinate_01.json').read_text())
                auto = json.loads((R / 'instruction17_automation_01.json').read_text())
                assert sleep['started'] and sleep['deadline'] == DEADLINE.isoformat()
                assert auto['updated'] and auto['deadline'] == DEADLINE.isoformat()
                check = subprocess.run(['ps', '-p', str(sleep['pid']), '-o', 'pid=,ppid=,stat=,command='], capture_output=True, text=True)
                assert check.returncode == 0 and ' '.join(sleep['command']) in check.stdout
                proof = 'mac/cstar_2026-10-09/instruction17_deadline_extension_01'
                addition = f'\n- 済み（{at}、SMEの係、2026-10-08_C星の一本の時間の内訳_Codex.md）：期限付きcaffeinateのPID{sleep["pid"]}の存続を確認し、pmset -gと命令・秒数・期限を報告。継続確認sme-25-cを2026-10-11 09:00日本時間まで延長、30分間隔を維持。既存caffeinate0本、停止した過程0本、模型の新規起動0本。\n\n'
                (REPO / INBOX).write_text(body[:section.end()] + addition + body[section.end():])
                text = f'\n### 指示17の眠り止めと継続確認の期限延長（{at}）\n\nREADMEのアストラ承認（2026-10-09 01:15、台帳D-07βι）と受け箱の指示17を確認。期限を2026-10-11 09:00日本時間へ延長。\n\n'
                text += f'起動直前の既存caffeinateは0本。{sleep["at"]}にPID{sleep["pid"]}を一度起動し、{at}のpsで存続を確認。命令はcaffeinate -i -t {sleep["duration_seconds"]}。idle sleepを抑える秒数は{sleep["duration_seconds"]}秒、指定期限は{sleep["deadline"]}、起動直前時刻から秒数を足した予定終了は{sleep["planned_expiration"]}。秒未満を切り捨てた期間であり、起動の所要時間との差は秒未満の予定値。起動前に終了した25′の眠り止めを再起動せず、指示17による別の起動として保存。停止した過程0本。\n\n'
                text += '起動後の電源の状態（pmset -g）：\n\n```text\n' + sleep['pmset']['out'].rstrip() + '\n```\n\n'
                text += f'継続確認sme-25-cの期限を同時刻へ更新、30分間隔と現在のチャットを維持。更新確認{auto["at"]}。期限以降の新しい作業を開始しない。期限を理由に動いている処理を止めない。模型の新規起動0本、本番の旗の変更0件。種21〜40、受付表と関門の条件を変更していない。指示9・13・案(b)・較正・4は未完了、旧診断3欄の省略は仕様確認1件で保留、GC・encodeの全長はデスクトップ係の結果待ち。証拠：{proof}。\n'
                with (REPO / REPORT).open('a') as f:
                    f.write(text)
                with (REPO / MAIN).open('a') as f:
                    f.write(f'\n### 継続確認の期限延長：{at}\n\n指示17とREADMEのアストラ承認に従い、継続確認の期限を2026-10-11 09:00日本時間へ延長、間隔30分。caffeinateのPID{sleep["pid"]}・秒数・期限・pmset -gを{REPORT}へ報告。指示17は済み。模型の新規起動0本。\n')
                dest = REPO / proof
                dest.mkdir(parents=True, exist_ok=False)
                for path in (R / 'instruction17_before_01.json', R / 'instruction17_received_01.json',
                             R / 'instruction17_caffeinate_claim_01.json', R / 'instruction17_caffeinate_01.json',
                             R / 'instruction17_automation_01.json', Path(__file__).resolve()):
                    assert path.stat().st_size < 2**20
                    shutil.copy2(path, dest / path.name)
                (dest / 'sha256.json').write_text(json.dumps({p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in dest.iterdir() if p.is_file()}, indent=2)+'\n')
                git('sparse-checkout', 'add', proof)
                commit = publish('指示17の眠り止めと10月11日までの期限延長を報告', [INBOX, REPORT, MAIN, proof])
                result = dict(at=at, instruction=17, done=True, reported=True, commit=commit, report=REPORT, proof=proof, deadline=DEADLINE.isoformat(), caffeinate_pid=sleep['pid'])
            save(marker, result)
            path = R / 'pending_01.json'
            pending = json.loads(path.read_text())
            pending['instruction17_received'] = True
            if mode == 'report':
                pending.update(instruction17_done=True, instruction17_reported=result,
                               heartbeat_deadline=DEADLINE.isoformat(), caffeinate_deadline=DEADLINE.isoformat(), caffeinate_pid=sleep['pid'])
            path.write_text(json.dumps(pending, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps(result, ensure_ascii=False))
except Exception as e:
    path = R / ('instruction17_' + mode + '_STOP_01.json')
    if not path.exists():
        save(path, dict(at=now(), reason=str(e), conflicts_not_resolved=True))
    raise

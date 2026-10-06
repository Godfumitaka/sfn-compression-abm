"""25′二本の受付と開始を待ち、監督役だけを戻す。模型の命令・計算は変えない。"""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import argparse
import json
import os
import shutil
import signal
import subprocess
import threading
import time
from common import ROOT, AREA, digest

JST = timezone(timedelta(hours=9))
HERE = Path(__file__).resolve().parent
PROOF = AREA / 'preview_n3/priority25'
REPORT = AREA / 'report_priority25'
NAME = 'control/2026-10-06_飾り_SME版_Codex.md'
RELPATH = 'control/shop_deco_sme_2026-10-06/priority25'
SME = AREA.parent / 'codex_sme_time_evict_2026-10-06'
CASES = ('shop_profile1740_02', 'verb_profile1000_01')


def now():
    return datetime.now(JST).isoformat()


def save(path, value):
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    temporary.replace(path)


def git(*args):
    return subprocess.check_output(['git', '-c', 'user.name=Codex', '-c', 'user.email=codex@openai.com', *args],
                                   cwd=REPORT, text=True).strip()


def ps():
    text = subprocess.check_output(['/bin/ps', '-axww', '-o', 'pid=,ppid=,rss=,stat=,args='], text=True)
    result = {}
    for line in text.splitlines():
        row = line.split(None, 4)
        if len(row) == 5:
            result[int(row[0])] = {'parent': int(row[1]), 'rss_bytes': int(row[2]) * 1024,
                                  'state': row[3], 'command': row[4]}
    return result


def descendants(rows, parent):
    result = {parent}
    while True:
        extra = {pid for pid, r in rows.items() if r['parent'] in result}
        if extra <= result:return result
        result |= extra


def registry():
    # 受付表を読むだけ。対象は25′二本と自分のN3だけ。
    result = []
    for line in Path('/Users/tatsu-admin/jobs/registry.tsv').read_text().splitlines()[1:]:
        p = line.split('\t', 4)
        if len(p) == 5 and (p[1] in ['SME25 ' + x for x in CASES] or p[1].startswith('shop-deco-sme-n3')):
            result.append(dict(pid=int(p[0]), owner=p[1], mem_gb=float(p[2]), registered_at=p[3], command=p[4]))
    return result


def case_starts(observed):
    rows = registry();processes = ps()
    for case in CASES:
        if case in observed:continue
        admitted = next((r for r in rows if r['owner'] == 'SME25 ' + case), None)
        folder = SME / case
        if admitted is None or not (folder / 'model_pid.json').exists() or not (folder / 'run.log').exists():continue
        model = json.loads((folder / 'model_pid.json').read_text())['pid']
        if model not in descendants(processes, admitted['pid']) or model not in processes:continue
        with (folder / 'run.log').open() as stream:first = stream.readline()
        if ' 開始 ' not in first:continue
        started = datetime.strptime(first[:19], '%Y-%m-%d %H:%M:%S').replace(tzinfo=JST).isoformat()
        observed[case] = {'model_started_at': started, 'confirmed_at': now(), 'registry': admitted,
            'model_pid': model, 'model_command': processes[model]['command'],
            'first_log_line': first.rstrip(), 'first_log_line_sha256': __import__('hashlib').sha256(first.encode()).hexdigest()}
    return observed


def publish(status):
    hold = json.loads((PROOF / 'hold.json').read_text())
    release = json.loads((PROOF / 'release.json').read_text()) if (PROOF / 'release.json').exists() else None
    observed = json.loads((PROOF / 'observed_starts.json').read_text()) if (PROOF / 'observed_starts.json').exists() else {}
    marker = '25prime_shop_deco_' + status + '_' + hold['suspended_at']
    lines = ['\n## 25′ の先通し', '', '<!-- ' + marker + ' -->', '', f"記録時刻：{now()}。状態：{status}。", '',
        f"{hold['suspended_at']}に、新規投入を止めた。自分の受付待ちから下ろした処理は0本。受付済みの`plus8_N3_D_w2_s001`（受付PID64528）は継続し、次の処理を投入する監督役PID{hold['controller_pid']}だけを待機させた。模型・worker・CPU監視・共有受付には停止の信号を送っていない。未投入は当該一本の解析と残り79本の模型・解析。", '',
        '25′のお店1,740試行と動詞の先頭1,000試行を、受付表の対象担当名と模型開始ログで確認する。先に動いた一本の受付時刻と開始時刻を保存し、両方の開始を確認するまで新しい模型・解析を受付へ渡さない。', '',
        f"2時間の期限：{hold['deadline_at']}。両方の開始がそれまでに確認できなければ期限で元の順番・命令による投入を再開し、その事実を報告する。", '',
        '| 測定 | 受付時刻 | 模型の開始時刻 | 確認時刻 |', '|---|---|---|---|']
    for case, label in zip(CASES, ('お店 1,740試行', '動詞 先頭1,000試行')):
        r = observed.get(case)
        lines.append('| ' + label + ' | ' + (' | '.join([r['registry']['registered_at'], r['model_started_at'], r['confirmed_at']]) if r else '未確認 | 未確認 | 未確認') + ' |')
    if release:
        lines += ['', f"戻した時刻：{release['returned_at']}。理由：{release['reason']}。下ろした受付が0本のため再登録する待機命令はなく、監督役を戻して以後の投入を許可した。既存の命令、旗、値、種1〜5の順番、各関門は変更していない。"]
        if release['reason'] == '2時間の期限に到達':
            lines += ['', '25′の両方の開始を2時間以内に確認できなかったため、それ以上待たずに戻した。未確認の測定を開始済みと扱わない。']
    else:
        lines += ['', '戻した時刻は未確定。確認用の軽い監督処理が、両方の開始または2時間の期限で自動的に監督役を戻す。']
    lines += ['', 'マック全体の模型過程8本の上限、受付表の資源条件、事前予想P-05cとD-04vを変更していない。種21〜40には触れていない。支持の割合の旗はN3の80本の報告が済むまで保留する。', '',
        '監督役が待機する間は、別の軽い記録係がこの受付PIDの子孫のRSSを標本化する。標本と受付表の対象行はcontrolのpriority25資料にも保存する。元の台帳・side・完了印・時間の値を書き換えない。']
    text = '\n'.join(lines) + '\n'
    assert not git('status', '--porcelain'), '報告専用の作業場所に未保存の変更がある'
    for attempt in range(6):
        git('fetch', 'origin', 'refs/heads/results-2026-09-27:refs/remotes/origin/results-2026-09-27')
        git('checkout', '--detach', 'origin/results-2026-09-27')
        if marker not in (REPORT / NAME).read_text():
            with (REPORT / NAME).open('a') as stream:stream.write(text)
        dest = REPORT / RELPATH;dest.mkdir(parents=True, exist_ok=True)
        for path in PROOF.glob('*.json'):shutil.copy2(path, dest / path.name)
        shutil.copy2(__file__, dest / 'priority25.py')
        git('add', '--sparse', NAME, RELPATH)
        if git('diff', '--cached', '--name-only'):
            git('commit', '-m', f'飾りの25′先通しの{status}を報告')
        try:
            git('push', 'origin', 'HEAD:refs/heads/results-2026-09-27')
            receipt = {'status': status, 'report_commit': git('rev-parse', 'HEAD'), 'reported_at': now()}
            save(PROOF / ('reported_' + status + '.json'), receipt)
            print(json.dumps(receipt, ensure_ascii=False), flush=True)
            return
        except subprocess.CalledProcessError:
            if attempt == 5:raise
            # 自分の報告コミットは保存済み。最新の他係の追記の後ろへ同じ節を足し直す。
            time.sleep(2)


def sample(stop, queue_pid):
    peak = 0;count = 0
    with (PROOF / 'resources_while_held.jsonl').open('a') as stream:
        while not stop.is_set():
            rows = ps();chosen = descendants(rows, queue_pid)
            rss = sum(rows[p]['rss_bytes'] for p in chosen if p in rows)
            peak = max(peak, rss);count += 1
            stream.write(json.dumps({'at': now(), 'queue_pid_alive': queue_pid in rows,
                'descendants_rss_bytes': rss}) + '\n');stream.flush()
            save(PROOF / 'resource_samples.json', {'peak_descendants_rss_bytes': peak, 'samples': count,
                'last_sample_at': now(), 'queue_pid_alive': queue_pid in rows})
            stop.wait(0.5)


def watch():
    hold = json.loads((PROOF / 'hold.json').read_text())
    deadline = datetime.fromisoformat(hold['deadline_at'])
    stop = threading.Event()
    observer = threading.Thread(target=sample, args=(stop, hold['running_queue_pid']), daemon=True)
    observer.start()
    observed = json.loads((PROOF / 'observed_starts.json').read_text()) if (PROOF / 'observed_starts.json').exists() else {}
    try:
        while True:
            observed = case_starts(observed)
            save(PROOF / 'observed_starts.json', observed)
            if len(observed) == 2 or datetime.now(JST) >= deadline:break
            stop.wait(min(5.0, max(0.0, (deadline - datetime.now(JST)).total_seconds())))
        rows = ps();pid = hold['controller_pid']
        assert pid in rows and 'shop_deco_sme_2026-10-06/run_n3.py' in rows[pid]['command'], '待機した監督役が見つからない'
        # 本来のCPU監視と受付・資源の関門は、そのまま監督役に適用される。
        os.kill(pid, signal.SIGCONT)
        release = {'returned_at': now(), 'reason': '25′二本の開始を確認' if len(observed) == 2 else '2時間の期限に到達',
            'controller_pid': pid, 'withdrawn_waiting_jobs_restored': 0, 'observed_starts': observed,
            'original_command_sha256': hold['original_command_sha256'], 'flags_values_order_gates_changed': False}
        save(PROOF / 'release.json', release)
        stop.set();observer.join(timeout=3)
        publish('復帰')
    except BaseException:
        save(PROOF / 'watch_error.json', {'at': now(), 'error': __import__('traceback').format_exc()})
        raise
    finally:
        stop.set();observer.join(timeout=3)


if __name__ == '__main__':
    parser = argparse.ArgumentParser();parser.add_argument('mode', choices=('prepare', 'watch'))
    args = parser.parse_args()
    if args.mode == 'prepare':
        hold = json.loads((PROOF / 'hold.json').read_text())
        hold.update(deadline_at=(datetime.fromisoformat(hold['suspended_at']) + timedelta(hours=2)).isoformat(),
            running_queue_pid=64528,
            original_command_sha256=digest(AREA / 'preview_n3/runs/plus8_N3_D_w2_s001/command.json'))
        save(PROOF / 'hold.json', hold)
        save(PROOF / 'observed_starts.json', case_starts({}))
        publish('待機')
    else:watch()

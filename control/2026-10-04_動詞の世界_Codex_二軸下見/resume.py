"""監督だけ終了した二軸を再開。実行中の一本を引き継ぎ、完走分は再走行しない。"""
from __future__ import annotations
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import time

BASE = Path(__file__).resolve().parent
ROOT = BASE.parent
SOURCE = ROOT/'source'
sys.path[:0] = [str(SOURCE), str(SOURCE/'tools'), str(SOURCE/'tools/verb')]
import axes
import night


def alive(pid):
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False


def command(pid):
    return subprocess.check_output(['/bin/ps', '-p', str(pid), '-o', 'command='], text=True).strip() if alive(pid) else ''


def main():
    plan = axes.read_plan()
    lock = (BASE/'pipeline.lock').open('w')
    fcntl.flock(lock, fcntl.LOCK_EX|fcntl.LOCK_NB)
    stop = False
    def request_stop(_signal, _frame):
        nonlocal stop
        stop = True
    signal.signal(signal.SIGINT, request_stop)
    signal.signal(signal.SIGTERM, request_stop)
    done = {r['label'] for r in plan['runs'] if (BASE/r['axis']/r['label']/'complete.json').exists()}
    active = {}
    adopted = []
    for r in plan['runs']:
        label = r['label']
        out = BASE/r['axis']/label
        if label in done or not out.exists():
            continue
        admitted = json.loads((out/'admitted.json').read_text())
        pid = admitted['pid']
        text = command(pid)
        assert text and 'tools/verb/axes.py one '+label in text, label
        parent = int(subprocess.check_output(['/bin/ps', '-p', str(pid), '-o', 'ppid='], text=True))
        assert 'jobs/jobs.py run --wait' in command(parent) and 'Codex-動詞二軸-'+label in command(parent)
        active[label] = {'run': r, 'adopted_pid': pid, 'jobs_pid': parent}
        adopted.append({'label': label, 'model_restarted': False})
    pending = [r for r in plan['runs'] if r['label'] not in done and r['label'] not in active]
    assert len(done)+len(active)+len(pending) == 50
    published = set(json.loads((BASE/'axes_published.json').read_text()))
    resume_info = {'time': night.now(), 'completed_on_resume': len(done), 'adopted': adopted,
                   'pending_on_resume': [r['label'] for r in pending], 'work_commit': plan['commit'],
                   'supervisor_script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                   'model_reruns_of_completed_or_adopted': 0, 'persistent_supervisor_stdout': 'ファイルへ保存'}
    night.write_json(BASE/'resume_info.json', resume_info)
    pub_dir = night.REPORT_REPO/axes.EVIDENCE
    shutil.copy2(Path(__file__), pub_dir/'resume.py')
    shutil.copy2(BASE/'resume_info.json', pub_dir/'resume_info.json')
    try:
        axes.publish(f"二軸の監督再開（{night.now()}）：以前の監督が終了し、状態表が41本で止まっていた。完走ファイルを確認すると{len(done)}本が完了。進行中の{', '.join(r['label'] for r in adopted)}を元の受付・プロセスのまま引き継ぎ、未着手{len(pending)}本を共有受付へ続ける。完走分・引継ぎ分の模型再走行0。作業コミットは{plan['commit']}、種1〜5のみ。新しい監督は出力をファイルへ保存して切断に備える。[監督の再開記録](./{Path(axes.EVIDENCE).name}/resume_info.json)。")
        while pending or active:
            if stop:
                raise InterruptedError('停止指示')
            while pending and len(active) < plan['concurrency_cap']:
                r = pending.pop(0)
                label = r['label']
                output = BASE/r['axis']/label
                assert not output.exists(), label+'の途中出力を上書きしない'
                cmd = [sys.executable, str(night.JOBS), 'run', '--wait', '--owner', 'Codex-動詞二軸-'+label,
                       '--mem', '.4', '--disk-path', str(output), '--', sys.executable,
                       str(SOURCE/'tools/verb/axes.py'), 'one', label]
                log = (BASE/(label+'.jobs.log')).open('w')
                proc = subprocess.Popen(cmd, cwd=SOURCE, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
                active[label] = {'run': r, 'process': proc, 'log': log, 'jobs_pid': proc.pid}
            for label, item in list(active.items()):
                out = BASE/item['run']['axis']/label
                if 'process' in item:
                    proc = item['process']
                    if proc.poll() is None:
                        continue
                    item['log'].close()
                    assert proc.returncode == 0, label+f'終了コード{proc.returncode}'
                else:
                    if not (out/'complete.json').exists() and alive(item['adopted_pid']):
                        continue
                assert (out/'complete.json').exists(), label+'完走・照合未完了'
                res = json.loads((out/'resources.json').read_text())
                assert res['model_returncode'] == res['analysis_returncode'] == res['record_returncode'] == 0
                done.add(label)
                del active[label]
                print('完了', len(done), '/50', label, flush=True)
            for axis in ('tau', 'question'):
                if axis in published:
                    continue
                if not all(r['label'] in done for r in plan['runs'] if r['axis'] == axis):
                    continue
                assert (BASE/'existing_checks.json').exists()
                output, checks = axes.summarize(BASE, plan, axis)
                assert checks['appearance_and_question_checks'] and checks['record_reads'] == checks['new_completed']+checks['reused_completed']
                old = json.loads((ROOT/'stage3_night/plan.json').read_text())
                axes.existing_novel_table(BASE, old)
                sha = axes.publish(f"\n## 二軸下見：{axis}軸の終了\n\n新規{checks['new_completed']}本完了、既存{checks['reused_completed']}本を集計。出現の並びと同じpの質問の並びを種ごとに照合して一致。\n\n"+(output/'axis_tables.md').read_text()+f"\n[表と照合記録](./{Path(axes.EVIDENCE).name}/{axis}/axis_checks.json)。回復の語別質問数による割り算、黙り理由、記憶量を含む。結果の良し悪しの判定はしない。", axis=axis, existing=True)
                published.add(axis)
                night.write_json(BASE/'axes_published.json', sorted(published))
                print('報告push', axis, sha, flush=True)
            night.write_json(BASE/'status.json', {'time': night.now(), 'state': 'running', 'complete': len(done),
                'planned': 50, 'active': list(active), 'pending': len(pending), 'axes_published': sorted(published),
                'supervisor_resumed': True})
            time.sleep(2)
        assert len(published) == 2
        sha = axes.publish(f"二軸の下見は新規50/50本と既存20本分の参照を集計し、二軸の報告をpush済み。作業枝 `{night.WORK_BRANCH}` = `{plan['commit']}`、直前の報告枝 `{night.REPORT_BRANCH}` = `{night.git(night.REPORT_REPO,'rev-parse','HEAD')}`。種1〜5のみ。監督再開時の完走・引継ぎ分の模型再走行0。", existing=True)
        night.write_json(BASE/'status.json', {'time': night.now(), 'state': 'complete', 'complete': 50, 'planned': 50, 'report_commit': sha})
    except BaseException as exc:
        for item in active.values():
            pid = item['jobs_pid']
            if alive(pid):
                os.killpg(pid, signal.SIGTERM)
            if 'log' in item:
                item['log'].close()
        reason = re.sub(r'/(?:Users|home)/[^\s\'\"]+', '<ローカルパス>', f'{type(exc).__name__}: {exc}')
        night.write_json(BASE/'status.json', {'time': night.now(), 'state': 'stopped', 'complete': len(done), 'reason': reason})
        try:
            for axis in ('tau', 'question'):
                output, checks = axes.summarize(BASE, plan, axis)
                axes.publish(f"二軸下見停止：{reason}。{axis}軸は新規{checks['new_completed']}/{checks['new_planned']}本が完走。途中出力を保存し、完走分のみ集計。", axis=axis, existing=True)
        except BaseException as problem:
            night.write_json(BASE/'unpublished_stop.json', {'reason': reason, 'publish_error_type': type(problem).__name__})
        raise


if __name__ == '__main__':
    main()

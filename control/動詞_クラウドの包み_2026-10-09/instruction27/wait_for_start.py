"""指示27の一本だけの開始待ち。既存本を止めず、原終了の変化で開始前を確認する。"""
from datetime import datetime, timezone
from pathlib import Path
import fcntl
import hashlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import time
from run_registered import start_counts

HERE = Path(__file__).resolve().parent
NR = HERE.parent
ROOT = NR.parent
RR = ROOT/'report-results'
CASE = NR/'instruction27_production/19_seed001_flags_on'
PY = '/opt/homebrew/opt/python@3.12/bin/python3.12'
NAME = '2026-10-07_動詞の世界_新しい版の移植_Codex'
MAIN = RR/'control'/f'{NAME}.md'
QUEUE = RR/'control/走行の列_2026-10-08.md'
INBOX = RR/'control/受け箱/動詞の世界の係.md'
spec_module = importlib.util.spec_from_file_location('night', ROOT/'source/tools/verb/night.py')
night = importlib.util.module_from_spec(spec_module); spec_module.loader.exec_module(night)


def save(name, value):
    (CASE/name).write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n')


def state(name, **extra):
    save('start_waiter_status.json', dict(at=datetime.now().astimezone().isoformat(),
         state=name, waiter_pid=os.getpid(), model_started=False, **extra))


def available_snapshot():
    raw = subprocess.check_output(['/bin/ps', '-axo', 'pid=,ppid=,pgid=,rss=,stat=,args='], text=True)
    value = start_counts(raw)
    limit = int(subprocess.check_output(['/usr/sbin/sysctl', '-n', 'hw.physicalcpu'], text=True))-2
    thermal = subprocess.check_output(['/usr/bin/pmset', '-g', 'therm'], text=True)
    thermal_ok = ('No thermal warning level has been recorded' in thermal and
                  not re.search(r'CPU_Speed_Limit\s*=\s*(?!100(?:\s|$))\d+', thermal))
    free = shutil.disk_usage(CASE).free
    ready = value['model_process_count']+5 <= 8 and value['unknown_active_spawn'] == 0 and value['outside_heavy']+6 <= limit and thermal_ok and free >= 20*2**30
    value.update(at=datetime.now().astimezone().isoformat(), cpu_limit=limit, thermal=thermal,
        free_disk_bytes=free, processes=raw, ready=ready, reason='既存#22二本の原終了後の開始直前の実枠変化を確認')
    return value


def main():
    lockfile = CASE/'start_waiter.lock'
    with lockfile.open('a') as singleton:
        fcntl.flock(singleton, fcntl.LOCK_EX | fcntl.LOCK_NB)
        assert not (CASE/'launcher_pid.json').exists() and not (CASE/'pid.json').exists()
        spec = json.loads((CASE/'spec.json').read_text())
        assert not spec['ready_to_start'] and not (CASE/'result.json').exists()
        state('waiting_for_original_22_results', required_cpu_slots=6, required_model_slots=5)
        while True:
            if datetime.now(timezone.utc) >= datetime.fromisoformat(spec['start_deadline_jst']):
                state('deadline_no_new_start'); return 0
            results = [NR/f'instruction26_production/22_seed{seed:03d}_retry26/result.json' for seed in (1, 2)]
            if all(p.exists() for p in results):
                if any(json.loads(p.read_text())['exit_code'] != 0 for p in results):
                    state('original_22_failure_needs_report'); return 1
                break
            # この待ちにはps・全機械の資源記録やcommitを増やさない。
            time.sleep(10)
        with (ROOT.parent/'codex_sme_light_2026-10-04/control_writer_01.lock').open('a') as writer:
            fcntl.flock(writer, fcntl.LOCK_EX)
            night.fetch_report()
            for section in re.split(r'(?m)(?=^## 指示 \d+)', INBOX.read_text())[1:]:
                if '受領（' not in section:
                    state('new_unreceived_instruction_before_start'); return 0
            # 受領済みの後続指示が来ても、この古い開始待ちが先行しない。
            instructions = [int(x) for x in re.findall(r'(?m)^## 指示 (\d+)', INBOX.read_text())]
            if max(instructions) not in (27, 28):
                state('later_instruction_recheck_required'); return 0
            lines = QUEUE.read_text().splitlines()
            index = next(i for i, line in enumerate(lines) if line.startswith('| 19p |'))
            fields = lines[index].split('|')
            if fields[-2].strip() != '未着手':
                state('queue_already_claimed_or_changed'); return 0
            # 列の上の取得可能なMac行を飛ばさない。
            from model_count import queue_rows
            eligible = queue_rows(QUEUE.read_text())
            if not eligible or eligible[0]['row'] != '19p':
                state('earlier_eligible_queue_row'); return 0
            value = available_snapshot()
            save('before_admission.json', value)
            if not value['ready']:
                state('actual_resources_not_ready_requires_next_check'); return 0
            if datetime.now(timezone.utc) >= datetime.fromisoformat(spec['start_deadline_jst']):
                state('deadline_no_new_start'); return 0
            # 完全なspecを先に固定して、列取得と開始前連絡の正常pushを確認する。
            spec['ready_to_start'] = True
            (CASE/'spec.json').write_text(json.dumps(spec, ensure_ascii=False, indent=2)+'\n')
            at = datetime.now().astimezone().isoformat()
            fields[-2] = f' 走行中（Mac・列取得{at}、CPU6枠/模型5枠/10GiB。通常push後に受付） '
            lines[index] = '|'.join(fields)
            QUEUE.write_text('\n'.join(lines)+'\n')
            with MAIN.open('a') as f:
                f.write(f'\n\n指示27の開始前連絡（{at}）：Claudeへ、#22二本の原終了0と実枠の変化を確認し、19p種1の同じMacの旗つき比較用一本を列から取得した。固定6e4・元19全旗＋V1 on/出生4、指示26の固定観察器、10GiB・CPU6枠・模型5枠。列取得の通常push成功後にだけ既存受付へ通す。原19二本は保持、全長一致までは仮。\n')
            public = RR/'control/動詞_クラウドの包み_2026-10-09/instruction27/mac/spec.json'
            public.write_text((CASE/'spec.json').read_text().replace(str(ROOT),'$WORKSPACE').replace(str(Path.home()),'$HOME'))
            night.checked_git(RR, 'add', '--', str(MAIN.relative_to(RR)), str(QUEUE.relative_to(RR)), str(public.relative_to(RR)))
            night.checked_git(RR, 'commit', '-m', '動詞: 指示27の種1旗つき比較を実枠確認後に列取得')
            for attempt in range(3):
                night.fetch_report(); night.scan_range(RR, night.REPORT_BRANCH, 'origin/'+night.REPORT_BRANCH)
                pushed = subprocess.run(['git','push','--no-follow-tags','origin','refs/heads/results-2026-09-27:refs/heads/results-2026-09-27'],cwd=RR)
                if pushed.returncode == 0: break
            assert pushed.returncode == 0
            save('queue_claim_published.json', dict(normal_push_succeeded=True, case_label=CASE.name,
                machine='Mac', commit=night.git(RR, 'rev-parse', 'HEAD'), spec_sha256=hashlib.sha256((CASE/'spec.json').read_bytes()).hexdigest()))
        command = [PY, str(Path.home()/'jobs/jobs.py'), 'run', '--wait', '--owner', '動詞・指示27・19種1旗つき比較',
            '--mem', '10.0', '--disk-path', spec['output'], '--', PY, str(HERE/'run_registered.py'), str(CASE)]
        save('admission_command.json', dict(command=command, cpu_slots=6, model_slots=5))
        with (CASE/'jobs.log').open('x') as log:
            child = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        save('launcher_pid.json', dict(pid=child.pid, command=command))
        state('submitted_once_to_existing_jobs', launcher_pid=child.pid)
        return 0


if __name__ == '__main__':
    raise SystemExit(main())

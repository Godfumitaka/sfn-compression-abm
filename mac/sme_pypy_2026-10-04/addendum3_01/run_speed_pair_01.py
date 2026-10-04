"""追記3だけの速さ診断。同じ不変の模型を二つの処理系でほぼ同時に始める。"""
from pathlib import Path
from datetime import datetime
import hashlib
import json
import os
import shutil
import signal
import subprocess
import time

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT.parent / "codex_sme_memory_2026-10-04/source_rng_share"
CPY = "/opt/homebrew/opt/python@3.12/bin/python3.12"
PYPY = "/opt/homebrew/Cellar/pypy3.11/8.0.0/bin/pypy3.11"
OUT = ROOT / "speed_pair_01"


def conditions():
    rows = []
    for line in Path('/Users/tatsu-admin/jobs/swap.tsv').read_text().splitlines():
        fields = line.split('\t')
        if len(fields) >= 4 and fields[1] != 'None' and float(fields[0]) >= time.time() - 600:
            rows.append(fields)
    return {"at": datetime.now().astimezone().isoformat(),
            "free_bytes": shutil.disk_usage(ROOT).free,
            "swap_grew": bool(rows) and max(float(x[1]) for x in rows) > float(rows[0][1]),
            "thermal_warning": next((x[3] for x in rows[-2:] if x[3] != 'ok'), None),
            "swap_mb": float(rows[-1][1]) if rows else None}


def main():
    assert not OUT.exists(), '二重に走らせない'
    row = conditions()
    assert row['free_bytes'] >= 20 * 2**30 and not row['swap_grew'] and not row['thermal_warning'], row
    revision = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=SOURCE, text=True).strip()
    assert revision.startswith('6e93e0b'), revision
    assert not subprocess.check_output(['git', 'status', '--porcelain'], cwd=SOURCE, text=True).strip()
    OUT.mkdir()
    (OUT / 'resources_start.json').write_text(json.dumps(row, ensure_ascii=False, indent=2) + '\n')
    base = json.loads((ROOT / 'small_01/stage3_learning_01_A/command.json').read_text())
    env = dict(os.environ, PYTHONHASHSEED='0')
    for key in ('LC_ALL', 'LANG', 'LC_CTYPE'):
        env.pop(key, None)
    active = []
    for name, interpreter in [('cpython', CPY), ('pypy', PYPY)]:
        folder = OUT / name
        folder.mkdir()
        command = list(base)
        command[0] = interpreter
        command[3] = str(folder / 'output')
        command[command.index('--trial-count') + 1] = '200'
        (folder / 'command.json').write_text(json.dumps(command, ensure_ascii=False, indent=2) + '\n')
        log = (folder / 'run.log').open('w')
        began = time.perf_counter()
        proc = subprocess.Popen(command, cwd=SOURCE, env=env, stdout=log, stderr=subprocess.STDOUT,
                                start_new_session=True)
        active.append({'name': name, 'folder': folder, 'proc': proc, 'log': log, 'began': began,
                       'began_at': datetime.now().astimezone().isoformat()})
    launch_delta = active[1]['began'] - active[0]['began']
    (OUT / 'launch.json').write_text(json.dumps({'source_commit': revision,
        'launch_delta_seconds': launch_delta, 'cprofile': False,
        'processes': [{k: x[k] for k in ('name', 'began_at')} | {'pid': x['proc'].pid} for x in active]},
        ensure_ascii=False, indent=2) + '\n')
    next_resource = 0.0
    while any('result' not in x for x in active):
        now = time.perf_counter()
        for item in active:
            rc = item['proc'].poll()
            if rc is not None and 'result' not in item:
                item['log'].close()
                result = {'exit': rc, 'wall_seconds': now - item['began'],
                          'started': item['began_at'], 'finished': datetime.now().astimezone().isoformat()}
                item['result'] = result
                (item['folder'] / 'run_result.json').write_text(json.dumps(result, indent=2) + '\n')
                print(item['name'], result, flush=True)
        if now >= next_resource:
            row = conditions()
            row['processes'] = subprocess.check_output(['/bin/ps', '-axo', 'pid=,ppid=,rss=,%cpu=,command='], text=True)
            with (OUT / 'resources.jsonl').open('a') as stream:
                stream.write(json.dumps(row, ensure_ascii=False) + '\n')
            next_resource = now + 15
            if row['free_bytes'] < 18.5 * 2**30 or row['swap_grew'] or row['thermal_warning']:
                row.pop('processes', None)
                for item in active:
                    if item['proc'].poll() is None:
                        os.killpg(item['proc'].pid, signal.SIGSTOP)
                (OUT / 'resource_stop.json').write_text(json.dumps(row, ensure_ascii=False, indent=2) + '\n')
                print('自分の二処理を資源条件で停止', row, flush=True)
                while not (OUT / 'resume_authorized.json').exists():
                    time.sleep(5)
                resumed = conditions()
                assert resumed['free_bytes'] >= 20 * 2**30 and not resumed['swap_grew'] and not resumed['thermal_warning'], resumed
                for item in active:
                    if item['proc'].poll() is None:
                        os.killpg(item['proc'].pid, signal.SIGCONT)
        time.sleep(.1)
    summary = {'diagnostic_only': True, 'not_adopted': True, 'source_commit': revision,
               'launch_delta_seconds': launch_delta, 'cprofile': False}
    for item in active:
        result = dict(item['result'])
        manifests = list((item['folder'] / 'output').glob('manifest.jsonl'))
        if manifests:
            result['manifest'] = [json.loads(s) for s in manifests[0].read_text().splitlines() if s]
        summary[item['name']] = result
    summary['cpython_over_pypy_wall'] = summary['cpython']['wall_seconds'] / summary['pypy']['wall_seconds']
    (OUT / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n')
    assert subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=SOURCE, text=True).strip() == revision
    assert not subprocess.check_output(['git', 'status', '--porcelain'], cwd=SOURCE, text=True).strip()
    print('diagnostic ratio', summary['cpython_over_pypy_wall'], flush=True)
    if any(item['result']['exit'] for item in active):
        raise SystemExit(1)


if __name__ == '__main__':
    main()

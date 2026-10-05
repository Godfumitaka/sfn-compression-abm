"""受付済みの一件を実行し検査する。固定の機械本数制限は使わず、模型は変更しない。"""
from pathlib import Path
import gzip
import hashlib
import importlib.util
import json
import os
import pstats
import re
import signal
import subprocess
import sys
import time
import traceback

root = Path(__file__).resolve().parent
source = root / 'source'
sys.path[:0] = [str(source / 'tools/v311c_checks'), str(source / 'tools'), str(source)]
import coll8_gate as g
from v311c_fingerprint import VERSION

spec = json.loads(Path(sys.argv[1]).read_text())
name = spec['name']
g.OUT = root / 'outputs/resume-jobs-20261004'
g.EV = root / 'evidence/resume-jobs-20261004' / name
g.EV.mkdir(parents=True, exist_ok=True)
g.RESULT = {'status': 'running', 'checks': [], 'runs': [], 'name': name,
            'started': g.now(), 'fingerprint_version': VERSION, 'model_changed': False}
g.HALT.clear()
g.checkpoint()
model_process = None

def interrupted(signum, frame):
    raise InterruptedError(f'自分の受付済み処理を停止：signal {signum}')

signal.signal(signal.SIGTERM, interrupted)

def load_receipt():
    location = Path('/Users/tatsu-admin/jobs/jobs.py')
    module_spec = importlib.util.spec_from_file_location('collective_receipt', location)
    module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(module)
    processes = module.procs()
    rows = module.read_reg()
    own = [r for r in rows if os.getpid() in module.registered_pids([r], processes)]
    if len(own) != 1:
        raise RuntimeError('自分の処理が受付表の一件に登録されていない')
    return {'time': g.now(), 'rows': rows, 'own': own[0],
            'jobs_sha256': hashlib.sha256(location.read_bytes()).hexdigest()}

def run_model():
    global model_process
    code = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=source, text=True).strip()
    if code != spec['source_commit']:
        raise RuntimeError('開始前に集団化のコードのコミットが変わった')
    receipt = load_receipt()
    h, _ = g.health()
    path = g.OUT / name
    if path.exists():
        raise RuntimeError('保存済み出力を上書きしない：' + str(path))
    environment = dict(os.environ, **spec.get('extra_env', {}))
    job = {**spec, 'initial': h, 'receipt': receipt}
    g.save(g.EV / 'argv.json', job)
    start = time.monotonic()
    peak = 0
    samples = 0
    with (g.EV / 'model.stdout.log').open('w') as stdout, (g.EV / 'model.time.log').open('w') as stderr:
        model_process = subprocess.Popen(['/usr/bin/time', '-l', *spec['argv']],
            cwd=source, env=environment, stdout=stdout, stderr=stderr, start_new_session=True)
        g.save(g.EV / 'model-process.json', {'pid': model_process.pid, 'started': g.now()})
        with gzip.open(g.EV / 'health.jsonl.gz', 'wt') as log:
            while model_process.poll() is None:
                hh, processes = g.health()
                descendants = {model_process.pid}
                for _ in range(8):
                    descendants.update(r['pid'] for r in processes if r['ppid'] in descendants)
                rss = sum(r['rss_kib'] for r in processes if r['pid'] in descendants) * 1024
                peak = max(peak, rss)
                samples += 1
                hh.update(job=name, rss_sum_bytes=rss, model_pid=model_process.pid,
                          allocation_gb=receipt['own']['mem_gb'], receipt_pid=receipt['own']['pid'])
                log.write(json.dumps(hh, ensure_ascii=False) + '\n')
                log.flush()
                # 受付の本数の上限を復活させない。熱・速度制限は走行中も監視する。
                match = re.search(r'CPU_Speed_Limit\s*=\s*(\d+)', hh['thermal']['output'])
                if match and int(match[1]) != 100:
                    raise RuntimeError('熱又は性能の警告：CPUの速度制限')
                time.sleep(1)
    end, _ = g.health()
    measurement = {'name': name, 'elapsed_seconds': time.monotonic() - start,
        'exitcode': model_process.returncode, 'finished': g.now(), 'rss_sum_peak_bytes': peak,
        'rss_sample_interval_seconds': 1, 'samples': samples,
        'swap_start_mib': h['swap_mib'], 'swap_end_mib': end['swap_mib']}
    g.save(g.EV / 'resource.json', measurement)
    g.check(name + ' 実行の終了コード', model_process.returncode == 0, exitcode=model_process.returncode)
    summaries = list((path / 'comm').glob('*.summary.json'))
    if summaries:
        summary = json.loads(summaries[0].read_text())
        g.check(name + ' 完走', summary['trials'] == 1740 and not summary['errors'],
                trials=summary['trials'], errors=summary['errors'])
        agents = summary['agents']
        measurement['agent_peak_rss_mb_decimal'] = [a['peak_rss_mb'] for a in agents]
        g.check(name + ' 受信の採点・名札費用',
                all(not a['v311c'][k] for a in agents
                    for k in ('recv_score_changed', 'recv_merit_changed', 'dC_mismatch')))
        g.check(name + ' 辞書外カウンタと毎試行の停止検査',
                all(a['v39'].get('not_in_dictionary', 0) == 0
                    and a['v311c'].get('dictionary_checks') == 3480 for a in agents),
                counts=[a['v39'].get('not_in_dictionary', 0) for a in agents],
                checks=[a['v311c'].get('dictionary_checks') for a in agents])
    else:
        row = json.loads((path / 'manifest.jsonl').read_text().splitlines()[-1])
        measurement['agent_peak_rss_mb_decimal'] = [row['peak_rss_mb']]
        g.check(name + ' 辞書外カウンタと毎試行の停止検査',
                row['v39'].get('not_in_dictionary', 0) == 0
                and row['v311c'].get('dictionary_checks') == 1740)
    measurement['output_bytes'] = sum(f.stat().st_size for f in path.rglob('*') if f.is_file())
    g.save(g.EV / 'resource.json', measurement)
    g.RESULT['runs'].append(measurement)
    g.checkpoint()
    return path

def main():
    path = run_model()
    if spec['kind'] == 'solo':
        reference = Path(spec['reference'])
        left = g.body(g.ledger_paths(reference)[spec['agent']])
        right = g.body(g.ledger_paths(path)[0])
        g.check(f"通信なし8体と単独：種{spec['run']}個体{spec['agent']}",
                left == right, collective=left, solo=right)
    else:
        current = g.inspect_population(name, path, g.FS, g.GROUPS, 1740, spec['q'], spec['m'])
        if spec['q']:
            reference = [g.minimal_rows(p) for p in g.ledger_paths(Path(spec['reference']))]
            coins = [[(r['coin_t'], r['f_fired'], r['f_realized']) for r in rows] for rows in reference]
            g.check(name + ' 開示の抽選の並び', current == coins, agents=8, trials_per_agent=1740)
        if spec['kind'] == 'profile':
            equivalent = Path(spec['equivalent'])
            g.compare('cProfileの非干渉（8体）', equivalent, path, comm=True)
            g.check('cProfileの学習状態と本走行乱数（新指紋）',
                    next((equivalent/'comm').glob('*.state.jsonl')).read_bytes()
                    == next((path/'comm').glob('*.state.jsonl')).read_bytes())
            profiles = path / 'profiles'
            files = sorted(profiles.glob('*.prof'))
            g.check('cProfileが8体とまとめ役を記録',
                    {p.name for p in files} == {'coordinator.prof', *{f'agent{i}.prof' for i in range(8)}})
            top = {}
            for file in files:
                stats = pstats.Stats(str(file))
                top[file.name] = {'total_calls': stats.total_calls, 'primitive_calls': stats.prim_calls,
                    'total_tt': stats.total_tt, 'top_cumulative': [
                        {'file': k[0], 'line': k[1], 'function': k[2],
                         'primitive_calls': v[0], 'calls': v[1], 'self_seconds': v[2], 'cumulative_seconds': v[3]}
                        for k, v in sorted(stats.stats.items(), key=lambda item: item[1][3], reverse=True)[:25]]}
            g.save(g.EV/'profile-top.json', top)
    g.RESULT.update(status='passed', finished=g.now())
    g.save(g.EV/'final-receipt.json', load_receipt())
    g.checkpoint()

if __name__ == '__main__':
    try:
        main()
    except BaseException as error:
        if model_process is not None and model_process.poll() is None:
            os.killpg(model_process.pid, signal.SIGTERM)
            model_process.wait()
        g.RESULT.update(status='stopped', reason=str(error), finished=g.now(), traceback=traceback.format_exc())
        g.checkpoint()
        print(g.RESULT['traceback'], flush=True)
        sys.exit(1)

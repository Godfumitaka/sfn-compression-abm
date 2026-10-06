"""受付から呼ぶ一本の検査。模型の内容を変えず、全試行のSME乱数を保存。

--pin-commitは旧土台とのバイト比較時の来歴欄だけを共通にする。
実装の実コミットは別のexecution.jsonに記録する。
"""
from pathlib import Path
import argparse
import hashlib
import json
import os
import platform
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'tools'), str(ROOT)]
import v3_run
REAL_WORKER = v3_run.worker


def runtime_environment():
    binary = Path(sys.executable).resolve()
    return {'executable': sys.executable, 'resolved': str(binary), 'version': sys.version,
            'build': platform.python_build(), 'compiler': platform.python_compiler(),
            'architecture': platform.machine(), 'utf8_mode': sys.flags.utf8_mode,
            'hash_seed': os.environ.get('PYTHONHASHSEED'),
            'locale_variables': {k:v for k,v in os.environ.items() if k == 'LANG' or k.startswith('LC_')},
            'binary_sha256': hashlib.sha256(binary.read_bytes()).hexdigest()}


def cpu_admission():
    cores = int(subprocess.check_output(['/usr/sbin/sysctl', '-n', 'hw.ncpu'], text=True))
    thermal = subprocess.check_output(['/usr/bin/pmset', '-g', 'therm'], text=True, stderr=subprocess.STDOUT)
    if 'CPU_Speed_Limit' in thermal or 'CPU_Scheduler_Limit' in thermal:
        raise RuntimeError('温度・性能の制限があるので新しい模型を開始しない')
    if 'No thermal warning level has been recorded' not in thermal or 'No performance warning level has been recorded' not in thermal:
        raise RuntimeError('温度・性能の制限なしを確認できないので開始しない')
    from uposition_cpu import census, descendants
    rows = census()
    own = descendants(rows, os.getpid())
    outside = sum(heavy for pid, (_, heavy) in rows.items() if pid not in own)
    # 一つのworkerを開始し、外側の監視が走行中の親も含め上限を保つ。
    if outside + 1 > cores-2:
        raise RuntimeError(('マック全体の模型過程の上限', outside, cores-2))
    return {'cores': cores, 'limit': cores-2, 'outside_heavy': outside, 'reserved_own': 1, 'thermal': thermal}


def worker(task):
    import sweep
    real_run = sweep.run_one
    root = Path(task['out_root']).parent
    (root / 'environment_worker.json').write_text(json.dumps(runtime_environment(), ensure_ascii=False, indent=2)+'\n')
    stream = (root / 'tie_state.jsonl').open('x')
    def run_one(task):
        import abm.loop as loop
        import smeshared
        import smereplay
        real_record = loop._ledger_record
        def record(agent, trial, *args, **kw):
            result = real_record(agent, trial, *args, **kw)
            seeds = list(smeshared.ENGINE.cache_rng.values())
            digest = hashlib.sha256(json.dumps(seeds, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
            stream.write(json.dumps({'trial': trial.trial, 'rng': smeshared.ENGINE.rng.getstate(),
                'call_context': dict(smeshared.CTX), 'cache_count': len(smeshared.ENGINE.cache),
                'self_cache_count': len(smeshared.ENGINE.self_cache), 'cache_rng_count': len(seeds),
                'cache_seed_sha256': digest}, ensure_ascii=False)+'\n')
            if (trial.trial+1) % 100 == 0:
                stream.flush()
                print(f"検査：種{task['seed']} {trial.trial+1}試行", flush=True)
            return result
        loop._ledger_record = record
        rec = real_run(task)
        with smeshared._text_gzip(root / 'saved_matcher.jsonl.gz') as out:
            out.write(json.dumps({'section': 'context', 'value': smereplay.encode(smeshared.CTX)}, ensure_ascii=False)+'\n')
            out.write(json.dumps({'section': 'rng', 'value': smereplay.encode(smeshared.ENGINE.rng.getstate())}, ensure_ascii=False)+'\n')
            for label, table in [('cache', smeshared.ENGINE.cache), ('self_cache', smeshared.ENGINE.self_cache),
                                  ('cache_rng', smeshared.ENGINE.cache_rng), ('results', smeshared.RESULTS),
                                  ('graphs', smeshared.GRAPHS), ('choices', smeshared.CHOICES), ('stats', smeshared.STATS)]:
                for key, value in table.items():
                    out.write(json.dumps({'section': label, 'key': smereplay.encode(key), 'value': smereplay.encode(value)},
                                          ensure_ascii=False, separators=(',', ':'))+'\n')
        return rec
    sweep.run_one = run_one
    try:
        return REAL_WORKER(task)
    finally:
        stream.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('command_file', type=Path)
    ap.add_argument('--pin-commit')
    args = ap.parse_args()
    command = json.loads(args.command_file.read_text())
    seed = command[command.index('--seeds')+1]
    if seed not in ('1', '2', '3') or command[command.index('--workers')+1] != '1':
        raise SystemExit('この検査は種1〜3の一過程だけ')
    output = Path(command[3])
    if output.exists():
        raise SystemExit('出力を上書きしない')
    root = output.parent
    root.mkdir(parents=True, exist_ok=True)
    admission = cpu_admission()
    import sweep
    commit = sweep.code_commit()
    if args.pin_commit:
        sweep.code_commit = lambda: args.pin_commit
    execution = {'source': str(ROOT), 'implementation_commit': commit, 'metadata_commit': args.pin_commit or commit,
                 'command': command, 'cpu_admission': admission, 'started_unix': time.time(),
                 'runtime_environment': runtime_environment()}
    (root / 'execution.json').write_text(json.dumps(execution, ensure_ascii=False, indent=2)+'\n')
    v3_run.worker = worker
    sys.argv = command[1:]
    os.chdir(ROOT)
    v3_run.main()
    execution['finished_unix'] = time.time()
    (root / 'execution.json').write_text(json.dumps(execution, ensure_ascii=False, indent=2)+'\n')


if __name__ == '__main__':
    main()

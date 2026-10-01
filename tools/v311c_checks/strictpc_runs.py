"""現行版への載せ直しの関門と、一対一の試し。出力を消さず、関門の不通で止まる。"""
from __future__ import annotations
import concurrent.futures
from datetime import datetime
import gzip
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time
import traceback
import xml.etree.ElementTree as ET

SOURCE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(SOURCE/'tools'))
ROOT = SOURCE.parent
BASE = ROOT / 'baseline'
OUTPUTS = ROOT / 'outputs'
RESULTS = ROOT.parents[1] / 'codex_worldv4_2026-10-01/results'
PY = '/opt/homebrew/opt/python@3.12/bin/python3.12'
TEST_PY = str(ROOT.parents[1] / 'codex_v310ans_2026-09-30/verify-env/bin/python')
CELL = 'f0.5000_th2.1000_vt0.3842_first_order'
PRICE = '0.01873710622997919'
FLAGS = ('--nohash --vt 0.3842 --extend-rule none --charge1 d32 --fast --no-public-history --dump-slot-history '
         '--fix2-full --fix-order2 --proj-first --fill-norestate --no-charge2 --own-evidence '
         '--v39 --v39-budget inf --v39-decay actr --v310-be --hist-role --score-role '
         '--nsim 0.7 --ident-rho 0.5 --ident-argmax --ident-commons --u-struct --relearn-init --tie-struct --amb-local '
         '--dump-answers --dump-routing --answer-gap --strict-pc --cf-value --probe-world '
         '--cells f0.5000_th2.1000_first_order --no-compare').split()
COLLECTIVE = '--v311c --v311c-f 0.5,0.5 --v311c-runs 1 --workers 1'.split()
LAST_PROGRESS = time.monotonic()


def now():
    return datetime.now().astimezone().isoformat(timespec='seconds')


def save(path, value):
    assert not path.exists(), path
    path.write_text(json.dumps(value, ensure_ascii=False, indent=1)+'\n')


def progress(message, force=False):
    global LAST_PROGRESS
    if force or time.monotonic()-LAST_PROGRESS >= 1800:
        with (RESULTS/'control/2026-09-30_Codex_進み具合.md').open('a') as f:
            f.write(f'\n- {now()} {message} 空き{shutil.disk_usage(ROOT).free/1e9:.3f}GB。\n')
        LAST_PROGRESS = time.monotonic()


def body(name, seed):
    assert seed in (1, 1001)
    path = OUTPUTS/name/'ledgers/cells'/CELL/f'seed{seed:03d}.jsonl.gz'
    digest = hashlib.sha256()
    n = 0
    with gzip.open(path, 'rb') as f:
        next(f)
        for line in f:
            digest.update(line)
            n += 1
    return {'sha256': digest.hexdigest(), 'rows': n}


def run_job(name, count, extra, *, source=SOURCE, config='config/sweep_b2_hide_s1_2026-09-22.json',
            forgetting=PRICE, learning=PRICE):
    if shutil.disk_usage(ROOT).free-2_000_000_000 < 15_000_000_000:
        raise RuntimeError('新しい走行を始める空きが無い')
    dest = OUTPUTS/name
    log = OUTPUTS/(name+'.log')
    assert not dest.exists() and not log.exists(), name
    cmd = [PY, 'tools/v3_run.py', config, str(dest), *FLAGS, '--trial-count', str(count),
           '--v39-price', forgetting, '--e-price', learning, *extra]
    save(OUTPUTS/(name+'.argv.json'), {'argv': cmd, 'cwd': str(source), 'start': now()})
    with log.open('x') as f:
        result = subprocess.run(cmd, cwd=source, stdout=f, stderr=subprocess.STDOUT)
    assert result.returncode == 0, (name, result.returncode, str(log))
    summaries = [json.loads(p.read_text()) for p in sorted((dest/'comm').glob('*.summary.json'))]
    if '--v311c' in extra:
        assert summaries and all(not s.get('errors') and s.get('trials') == count for s in summaries), name
        assert all(not a.get('error') for s in summaries for a in s['agents']), name
        assert all((a.get('v311c') or {}).get(k, 0) == 0 for s in summaries for a in s['agents']
                   for k in ('recv_score_changed', 'recv_merit_changed', 'dC_mismatch')), name
    else:
        records = [json.loads(l) for l in (dest/'manifest.jsonl').read_text().splitlines()]
        assert records and all(not r.get('error') for r in records), name
    print(json.dumps({'finished': name, 'time': now(), 'populations': len(summaries)}, ensure_ascii=False), flush=True)
    progress(f'集団化の確認：{name} が終了。')
    return summaries


def small_examples():
    files = [('test_v311c.py', 6), ('test_v311ch_role.py', 3), ('test_v311cu_receiver.py', 2),
             ('test_v311cu_ties.py', 1), ('test_v310u.py', 9), ('test_v310urta_amb_local.py', 6),
             ('test_v310h_hist_role.py', 5), ('test_v310hs_score_role.py', 5),
             ('test_v310_be.py', 11), ('test_v39_budget.py', 16)]
    items = [('test_v311cs_current_flags.py::'+name, 1) for name in (
             'test_received_bundle_strict_parent_child_mapping', 'test_received_argument_kinds_survive_definition_graph',
             'test_received_definition_obeys_answer_gap_in_world', 'test_probe_restores_current_records_and_counter_types')]
    results = []
    for i, (name, expected) in enumerate(files+items):
        out = OUTPUTS/f'pytest_{i:02d}.xml'
        log = OUTPUTS/f'pytest_{i:02d}.log'
        assert not out.exists() and not log.exists()
        with log.open('x') as f:
            r = subprocess.run([TEST_PY, '-m', 'pytest', '-q', '--maxfail=1', 'tests/'+name,
                                '--junitxml='+str(out)], cwd=SOURCE, stdout=f, stderr=subprocess.STDOUT)
        suites = list(ET.parse(out).getroot().iter('testsuite'))
        counts = {k: sum(int(s.attrib.get(k, 0)) for s in suites) for k in ('tests', 'failures', 'errors', 'skipped')}
        result = {'item': name, 'expected': expected, 'returncode': r.returncode, **counts}
        results.append(result)
        print(json.dumps(result, ensure_ascii=False), flush=True)
        assert r.returncode == 0 and counts['tests'] == expected and not any(counts[k] for k in ('failures', 'errors', 'skipped')), result
    save(OUTPUTS/'small_examples.json', results)
    assert sum(r['tests'] for r in results) == 68


def checks():
    small_examples()
    jobs = [('off_base', 1740, ['--seeds', '1', '--workers', '1'], BASE),
            ('off_port', 1740, ['--seeds', '1', '--workers', '1'], SOURCE),
            ('notags', 300, COLLECTIVE+['--v311c-no-tags'], SOURCE),
            ('short_ind', 300, ['--seeds', '1', '--workers', '1'], SOURCE),
            ('solo_notags', 300, ['--v311c', '--v311c-f', '0.5', '--v311c-no-tags', '--v311c-runs', '1001', '--workers', '1'], SOURCE),
            ('q0', 300, COLLECTIVE+['--v311c-q', '0'], SOURCE),
            ('solo_q0', 300, ['--v311c', '--v311c-f', '0.5', '--v311c-q', '0', '--v311c-b-n', '2', '--v311c-runs', '1,1001', '--workers', '1'], SOURCE),
            ('repeat1', 300, COLLECTIVE+['--v311c-q', '0.5', '--v311c-recv', 'B', '--v311c-probe-every', '10'], SOURCE),
            ('repeat2', 300, COLLECTIVE+['--v311c-q', '0.5', '--v311c-recv', 'B', '--v311c-probe-every', '10'], SOURCE),
            ('noprobe', 300, COLLECTIVE+['--v311c-q', '0.5', '--v311c-recv', 'B', '--v311c-probe-every', '0'], SOURCE),
            ('recvA_check', 300, COLLECTIVE+['--v311c-q', '0.5', '--v311c-recv', 'A', '--v311c-probe-every', '10'], SOURCE)]
    pairs = [('off_base', 'off_port', 1), ('short_ind', 'notags', 1), ('solo_notags', 'notags', 1001),
             ('q0', 'solo_q0', 1), ('q0', 'solo_q0', 1001), ('repeat1', 'repeat2', 1),
             ('repeat1', 'repeat2', 1001), ('repeat1', 'noprobe', 1), ('repeat1', 'noprobe', 1001)]
    completed = set()
    compared = []
    for name, count, extra, source in jobs:
        run_job(name, count, extra, source=source)
        completed.add(name)
        for a, b, seed in pairs:
            if a in completed and b in completed and not any(p['a'] == a and p['b'] == b and p['seed'] == seed for p in compared):
                left, right = body(a, seed), body(b, seed)
                pair = {'a': a, 'b': b, 'seed': seed, 'left': left, 'right': right, 'equal': left == right}
                compared.append(pair)
                assert pair['equal'], pair
    def comm_hash(name):
        h = hashlib.sha256()
        for line in (OUTPUTS/name/'comm/run001.jsonl').read_text().splitlines(True):
            if json.loads(line).get('kind') != 'summary':
                h.update(line.encode())
        return h.hexdigest()
    assert len(compared) == 9 and comm_hash('repeat1') == comm_hash('repeat2')
    save(OUTPUTS/'checks_hashes.json', {'body_pairs': compared, 'comm_repeat_equal': True})
    # E の値段を忘却の値段と分けた受信を、実際の学習の経路で確認する。
    run_job('eprice_check', 300, COLLECTIVE+['--v311c-q', '0.5', '--v311c-recv', 'A', '--v311c-probe-every', '10'], learning='0.2')
    comm = [json.loads(l) for l in (OUTPUTS/'eprice_check/comm/run001.jsonl').read_text().splitlines()]
    priced = [r['E'] for r in comm if r.get('kind') == 'recv' and (r.get('E') or {}).get('lam') is not None]
    assert priced and all(r['lam'] == 0.2 for r in priced)
    save(OUTPUTS/'eprice_receipts.json', {'forgetting': float(PRICE), 'learning': 0.2, 'receipts_with_costs': len(priced),
                                      'all_receipt_prices_equal': True, 'records': priced})
    import v311c_report
    rows = []
    for name in ('notags', 'solo_notags', 'q0', 'solo_q0', 'repeat1', 'repeat2', 'noprobe', 'recvA_check', 'eprice_check'):
        for path in sorted((OUTPUTS/name/'comm').glob('run*.jsonl')):
            r = v311c_report.one_population(str(OUTPUTS/name), str(path))
            c, s = r['突き合わせ'], r['数']
            assert r['失敗'] == 0 and c['個体の課題の和'] == c['誤答の出どころの和'] == r['個体']
            assert c.get('一致の四分類の和', 0) == r['probes']
            assert all(c[k] == 1 for k in ('送信＝配達', '配達＝受け取りの記録', '束のある試行は実際に答えた試行',
                                           '一個体一試行に束は一つまで', '受け取りで束を送らない'))
            assert all(s.get('STATS_'+k, 0) == 0 for k in ('recv_score_changed', 'recv_merit_changed', 'dC_mismatch'))
            assert s.get('誤答_?', 0) == 0
            rows.append({'condition': name, **r})
    save(OUTPUTS/'checks_counts.json', rows)
    save(OUTPUTS/'gate_passed.json', {'time': now(), 'base': '88e0e38bbd4f8ebbdc3f087de36801ce64a673e2',
                                   'small_examples': 68, 'body_pairs': 9, 'populations_audited': len(rows)})
    progress('関門2：小例68件、台帳本文9組、通信の再現、件数と受信の採点・費用の一致を確認。', force=True)
    print('関門2を確認', flush=True)


def pilot():
    assert (OUTPUTS/'gate_passed.json').exists()
    jobs = [(world, mode, seed) for world in (2, 1) for mode in ('recvA', 'no_comm') for seed in (1, 2, 3)]
    def one(job):
        world, mode, seed = job
        extra = ['--v311c', '--v311c-f', '0.5,0.5', '--v311c-runs', str(seed), '--workers', '1',
                 '--v311c-q', '0.2' if mode == 'recvA' else '0', '--v311c-recv', 'A',
                 '--shop-world', str(world), '--shop-exc', '0.2']
        return run_job(f'pilot_w{world}_{mode}_g{seed:03d}', 1740, extra,
                       config='config/sweep_shop_hide1_s1_2026-10-01.json', forgetting='0.0187', learning='0.0187')
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        # 関門の後の試し。各実行は二体だけで、集団二つを上限とする。
        queue = iter(jobs)
        pending = {pool.submit(one, next(queue)) for _ in range(2)}
        while pending:
            finished, pending = concurrent.futures.wait(pending, return_when=concurrent.futures.FIRST_COMPLETED)
            for future in finished:
                future.result()
            for _ in finished:
                job = next(queue, None)
                if job is not None:
                    pending.add(pool.submit(one, job))
    progress('一対一の試し12集団・41760世界課題の走行が終了。', force=True)


if __name__ == '__main__':
    OUTPUTS.mkdir(exist_ok=True)
    try:
        {'checks': checks, 'pilot': pilot}[sys.argv[1]]()
    except Exception as error:
        failure = {'time': now(), 'mode': sys.argv[1], 'error': repr(error), 'traceback': traceback.format_exc()}
        path = OUTPUTS/('stopped_'+datetime.now().strftime('%Y%m%d_%H%M%S')+'.json')
        save(path, failure)
        with (RESULTS/'control/2026-10-01_穴出しと集団化_Codex.md').open('a') as f:
            f.write(f'\n- {now()} 段{2 if sys.argv[1] == "checks" else 3}で停止。{error!r}。詳しい記録：{path}。後の走行を開始しない。\n')
        print(failure['traceback'], file=sys.stderr)
        sys.exit(2)

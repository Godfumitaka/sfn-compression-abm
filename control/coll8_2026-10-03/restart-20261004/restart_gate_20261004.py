"""委任書2026-10-04：段2の一致後、新指紋で種1〜3の関門を新規出力へ直列実行。"""
from pathlib import Path
import json
import subprocess
import sys
import traceback

root = Path(__file__).resolve().parent
source = root / 'source'
sys.path[:0] = [str(source / 'tools/v311c_checks'), str(source / 'tools'), str(source)]
import coll8_gate as g
from v311c_fingerprint import VERSION

g.OUT = root / 'outputs/restart-20261004'
g.EV = root / 'evidence/restart-20261004'
g.OUT.mkdir(exist_ok=True)
g.EV.mkdir(exist_ok=True)
assert not (g.EV / 'gates.json').exists(), '再開の途中出力を自動で再使用しない'
g.RESULT = {'status': 'running', 'checks': [], 'runs': [], 'started': g.now(),
            'source_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=source, text=True).strip(),
            'fingerprint_version': VERSION, 'old_runtime_fingerprints_used': False,
            'main_run_started': False}
g.HALT.clear()
g.checkpoint()


def run_job(name, count, **kw):
    path = g.run_job(name, count, **kw)
    summaries = list((path / 'comm').glob('*.summary.json'))
    if summaries:
        agents = json.loads(summaries[0].read_text())['agents']
        g.check(name + ' 辞書外カウンタと毎試行の停止検査',
                all(a['v39'].get('not_in_dictionary', 0) == 0
                    and a['v311c'].get('dictionary_checks') == 2 * count for a in agents),
                counts=[a['v39'].get('not_in_dictionary', 0) for a in agents],
                checks=[a['v311c'].get('dictionary_checks') for a in agents])
    elif kw.get('solo_agent') is not None:
        rec = json.loads((path / 'manifest.jsonl').read_text().splitlines()[-1])
        g.check(name + ' 辞書外カウンタと毎試行の停止検査',
                rec['v39'].get('not_in_dictionary', 0) == 0
                and rec['v311c'].get('dictionary_checks') == count)
    return path


def main():
    # 段2は旧い指紋を読まず、保存済みの台帳本体だけとの一致を確認する。
    before = root / 'outputs/record8_logged'
    old = json.loads((root / 'evidence/record8_logged.argv.json').read_text())['argv']
    new = g.argv('guard_equivalence_seed1', 200)
    g.check('段2の保存走行と全引数一致（出力場所を除く）', old[:3] + old[4:] == new[:3] + new[4:],
            old=old, new=new)
    after = run_job('guard_equivalence_seed1', 200)
    g.compare('段2・停止検査追加前後（種1）', before, after)
    g.RESULT['stage2_passed'] = True
    g.checkpoint()

    # ここから全て新規走行。旧い監査ハッシュは合格の証拠に使用しない。
    p = run_job('serial2_simultaneous', 100, fs=[0.1, 0.9], groups=[0, 1], serial=False)
    s = run_job('serial2_serial', 100, fs=[0.1, 0.9], groups=[0, 1])
    g.compare('直列と同時（2体）', p, s, comm=True)
    old = g.run_job('default2_baseline', 200, fs=[0.1, 0.9], groups=[0, 1],
                    serial=False, shop=False, audit=False, lineage=False, source=root / 'baseline')
    new = run_job('default2_current', 200, fs=[0.1, 0.9], groups=[0, 1],
                  serial=False, shop=False, audit=False, lineage=False)
    g.compare('追加旗が全てオフと土台（2体）', old, new, comm=True)
    off = run_job('off8', 100, fs=[0.5] * 8, q=0, m=0, no_tags=True,
                  shop=False, audit=False, lineage=False)
    for i in range(8):
        base = g.run_job(f'baseline_a{i}', 100, standalone_seed=1 + 1000 * i, source=root / 'baseline')
        g.check(f'集団化全部オフと固定個体版：個体{i}',
                g.body(g.ledger_paths(off)[i]) == g.body(g.ledger_paths(base)[0]))
    plain = run_job('record8_plain', 200, shop=False, audit=True, lineage=False)
    logged = run_job('record8_logged', 200)
    g.compare('お店試験・系譜の非干渉（8体）', plain, logged)
    state_plain = next((plain / 'comm').glob('*.state.jsonl')).read_bytes()
    state_logged = next((logged / 'comm').glob('*.state.jsonl')).read_bytes()
    g.check('お店試験・系譜の学習状態と本走行乱数（新指紋）', state_plain == state_logged)
    no_audit = run_job('record8_no_audit', 200, audit=False)
    g.compare('状態指紋の非干渉（8体）', logged, no_audit, comm=True)
    for run in (1, 2, 3):
        name = f'no_comm_r{run}'
        nocomm = run_job(name, 1740, run=run, q=0, m=0)
        reference = g.inspect_population(name, nocomm, g.FS, g.GROUPS, 1740, 0, 0)
        for i in range(8):
            solo = run_job(f'solo_r{run}_a{i}', 1740, run=run, solo_agent=i, q=0, m=0)
            g.check(f'通信なし8体と単独：種{run}個体{i}',
                    g.body(g.ledger_paths(nocomm)[i]) == g.body(g.ledger_paths(solo)[0]))
        for m in (0, 0.1, 0.3):
            name = f'comm_m{m}_r{run}'
            pop = run_job(name, 1740, run=run, m=m)
            current = g.inspect_population(name, pop, g.FS, g.GROUPS, 1740, 0.2, m)
            g.check(name + ' 開示の抽選の並び', current == reference, agents=8, trials_per_agent=1740)
    g.RESULT.update(status='passed', finished=g.now())
    g.checkpoint()


if __name__ == '__main__':
    try:
        main()
    except BaseException as error:
        g.RESULT.update(status='stopped', finished=g.now(), reason=str(error), traceback=traceback.format_exc())
        g.checkpoint()
        print(g.RESULT['traceback'], flush=True)
        sys.exit(1)

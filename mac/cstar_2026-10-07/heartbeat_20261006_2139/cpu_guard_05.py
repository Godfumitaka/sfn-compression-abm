"""小さい待機中の模型の子も数える。模型の計算は変更しない。"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'codex_logp_main_2026-10-06'))
from common_01 import ps, descendants, now

def compute_leaves(rows):
    candidates = {}
    for pid, x in rows.items():
        command = x['command']
        if 'T' in x['stat'] or 'Z' in x['stat']:
            continue
        if 'python' not in Path(command.split()[0]).name.lower():
            continue
        if '/jobs/jobs.py' in command or 'resource_tracker' in command:
            continue
        known_model = 'spawn_main' in command or 'sme_evict_observe_' in command
        if known_model or x['rss'] >= 100 * 2**20 or x['cpu'] >= 10:
            candidates[pid] = x
    return {p: x for p, x in candidates.items()
            if not any(q != p and q in descendants(p, rows) for q in candidates)}

def cpu_reading(active):
    rows = ps()
    own = set()
    for job in active:
        own.update(descendants(job['child'].pid, rows))
    leaves = compute_leaves(rows)
    external = {p: x for p, x in leaves.items() if p not in own}
    return {'at': now(), 'cores': 10, 'cap': 8,
            'external_compute_processes': external, 'external_count': len(external),
            'own_reserved_slots': len(active), 'total_reserved_slots': len(external) + len(active),
            'own_compute_count': sum(p in own for p in leaves), 'total_compute_count': len(leaves),
            'count_includes_small_waiting_model_workers': True}

if __name__ == '__main__':
    def row(ppid, command, stat='S', rss=40*2**20, cpu=0):
        return {'ppid': ppid, 'command': command, 'stat': stat, 'rss': rss, 'cpu': cpu}
    rows = {1: row(0, 'python sme_evict_observe_test.py'),
            2: row(1, 'python sme_evict_observe_test.py')}
    rows.update({p: row(2, 'python sme_evict_observe_test.py') for p in range(3,11)})
    assert set(compute_leaves(rows)) == set(range(3,11))
    rows[3]['stat'] = 'T'
    assert set(compute_leaves(rows)) == set(range(4,11))
    rows[11] = row(0, 'python -c spawn_main()', rss=1)
    assert set(compute_leaves(rows)) == set(range(4,12))
    print('PASS: 小さい待機中の8子、親の除外、停止中の除外、spawn子の計上')

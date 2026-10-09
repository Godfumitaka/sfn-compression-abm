"""既存の確定M1を読む。種3〜10の判断を代行せず、模型・記録を変えない。"""
from pathlib import Path
import argparse
import hashlib
import json


def extract(case1, case2, destination, through=500):
    assert through in (500, 1000, 2000, 3000, 4000, 4999)
    destination = Path(destination)
    assert not destination.exists(), '同じ確定M1を再集計しない'
    rows, commits = [], []
    for seed, case in enumerate((Path(case1), Path(case2)), 1):
        spec = json.loads((case/'spec.json').read_text())
        assert spec['flags'][spec['flags'].index('--seeds')+1] == str(seed)
        path = Path(spec['output'])/'comparison_checkpoints'/f'm1_at_trial{through}.json'
        row = json.loads(path.read_text())
        assert row['zero_based'] and row['first_trial'] == 200 and row['last_trial'] == through
        # 適用される既存M1はapplicable欄を持たない。適用外だけ明示False。
        assert row['trials'] == through-199 and row.get('applicable', True)
        rows.append(dict(seed=seed, **row, proof_sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
        commits.append(spec['source_commit'])
    assert commits[0] == commits[1]
    result = dict(rows=rows, source_commit=commits[0], claude_confirmation_required=True,
        no_stop_criterion=all(not x['stop_criterion'] for x in rows), seeds3_to10_may_start=False,
        other_queue_conditions_required=True, do_not_wait_for_calibration_1000=True,
        report_to_Claude_if_criterion=True, automatic_stop=False)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
    return result


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('seed1'); p.add_argument('seed2'); p.add_argument('destination')
    p.add_argument('--through', type=int, default=500)
    a = p.parse_args()
    extract(a.seed1, a.seed2, a.destination, a.through)

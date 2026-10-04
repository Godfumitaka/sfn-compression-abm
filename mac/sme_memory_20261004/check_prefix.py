"""進行中の閉じた行だけを比較する。全走行の受入検査の代わりにはしない。"""
from pathlib import Path
import argparse
import datetime
import gzip
import hashlib
import json

ROOT = Path(__file__).resolve().parent
BASE = ROOT.parent / 'codex_sme_fast_2026-10-03/exact_full_01/baseline'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('run', choices=('profile_late_01', 'proof_rng_share_01'))
    parser.add_argument('trials', type=int)
    args = parser.parse_args()
    candidate = ROOT / args.run
    records = []
    patterns = [('output/ledgers/**/*.jsonl.gz', args.trials, True),
                ('output/side/**/*.sme.states.jsonl.gz', args.trials * 3, False),
                ('tie_rng.jsonl', args.trials, False)]
    for pattern, count, header in patterns:
        left = next(BASE.glob(pattern))
        right = next(candidate.glob(pattern))
        opener = gzip.open if str(left).endswith('.gz') else open
        a_hash, b_hash = hashlib.sha256(), hashlib.sha256()
        with opener(left, 'rb') as a, opener(right, 'rb') as b:
            if header:
                next(a)
                next(b)
            for index in range(count):
                x, y = next(a), next(b)
                if not x.endswith(b'\n') or not y.endswith(b'\n'):
                    raise RuntimeError('未完の行は比較しない')
                a_hash.update(x)
                b_hash.update(y)
                if x != y:
                    raise RuntimeError(f'不一致: {pattern} 行{index + 1}。案は採用しない')
        records.append({'file': str(right.relative_to(candidate)), 'lines': count, 'equal': True,
                        'baseline_sha256': a_hash.hexdigest(), 'candidate_sha256': b_hash.hexdigest()})
    report = {'time': datetime.datetime.now().astimezone().isoformat(), 'partial_check_only': True,
              'trials': args.trials, 'records': records}
    (candidate / f'prefix{args.trials}.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(report, ensure_ascii=False))


if __name__ == '__main__':
    main()

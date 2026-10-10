"""指示34。d/d2/d3それぞれの実完了gate100から、同じ旗の新入口100のspecを作るだけ。"""
from pathlib import Path
import argparse
import hashlib
import json
import sys
from prepare_case import prepare, HERE
from prefix_gate_compare import completion


def prepare_from_gate(source, output_root, existing_gate_case):
    original = Path(existing_gate_case).resolve()
    spec, result, out = completion(original)
    assert spec['seed'] == 1 and spec['source_commit'] == '6e4bcba94874a4f49c5a1bae11d385534504e2e5'
    children = int(spec['flags'][spec['flags'].index('--stage2-birth-workers')+1])
    plan = json.loads((HERE/'plan.json').read_text())
    assert spec['flags'] == plan['gate_commands'][f'gate100_birth{children}']['flags']
    prepared = prepare(source, output_root, f'prefix_gate100_birth{children}')
    case = Path(prepared['case'])
    comparison = [sys.executable, str(HERE/'run_prefix_comparison.py'), str(original), str(case),
                  str(Path(output_root)/'prefix_comparisons'/f'prefix_gate_birth{children}.json'),
                  '--clearance', '$COMPARISON_CLEARANCE']
    proof = dict(original_case=str(original), original_spec_sha256=hashlib.sha256((original/'spec.json').read_bytes()).hexdigest(),
                 original_result_sha256=hashlib.sha256((original/'result.json').read_bytes()).hexdigest(),
                 original_boot=json.loads((original/'machine_before_start.json').read_text())['machine_boot_sha256'],
                 comparison_admission_command=[sys.executable, '$JOBS/jobs.py', 'run', '--wait', '--mem', '0.3',
                     '--disk-path', str(Path(output_root)/'prefix_comparisons'), '--', *comparison],
                 memory_reservation_gb=0.3, comparison_executed=False, model_starts=0,
                 formal_gate_claim_normal_push_and_fresh_clearance_required=True)
    (case/'original_gate_and_comparison.draft.json').write_text(json.dumps(proof, ensure_ascii=False, indent=2)+'\n')
    return prepared


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source', required=True)
    p.add_argument('--output-root', required=True)
    p.add_argument('--existing-gate-case', required=True)
    a = p.parse_args()
    print(json.dumps(prepare_from_gate(a.source, a.output_root, a.existing_gate_case), ensure_ascii=False))

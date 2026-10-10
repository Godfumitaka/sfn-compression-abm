"""指示30までのx86用70命令と100関門3本を実パスへ展開するだけ。模型を起動しない。"""
from pathlib import Path
import argparse
import hashlib
import json
import subprocess
import sys

HERE = Path(__file__).resolve().parent


def prepare(source, output_root, label):
    source, output_root = Path(source).resolve(), Path(output_root).resolve()
    plan = json.loads((HERE/'plan.json').read_text())
    draft = {**plan['commands'], **plan['gate_commands'], **plan.get('partial_commands', {}), **plan.get('prefix_gate_commands', {})}[label]
    assert subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=source, text=True).strip() == draft['source_commit']
    assert subprocess.check_output(['git', 'rev-parse', 'HEAD^{tree}'], cwd=source, text=True).strip() == draft.get('source_tree',plan['source_tree'])
    assert not subprocess.check_output(['git', 'status', '--porcelain'], cwd=source)
    case = output_root/label
    case.mkdir(parents=True, exist_ok=False)
    files = {str(HERE/rel):sha for rel, sha in plan['observer_files'].items()}
    driver = HERE/draft.get('driver_relative', 'gate/measurement_driver.py' if draft.get('measurement_limit') == 100 else 'tools/production/measurement_driver.py')
    if draft.get('driver_relative'):
        files[str(driver)] = hashlib.sha256(driver.read_bytes()).hexdigest()
    prefix = [sys.executable, str(driver), str(source)]
    if draft.get('measurement_limit') in (100, 1000):
        prefix.append(str(draft['measurement_limit']))
    runner = HERE/draft.get('runner_relative', 'run_registered.py')
    spec = {**draft, 'machine':'x86', 'cwd':str(source), 'output':str(case/'output'),
        'observer_files':files, 'runner_sha256':hashlib.sha256(runner.read_bytes()).hexdigest(),
        'sources':{str(source):draft['source_commit']}, 'ready_to_start':False,
        'command':[*prefix, str(source/'config/sweep_verb_hide1_s1_2026-10-04.json'), str(case/'output'), *draft['flags']]}
    (case/'spec.json').write_text(json.dumps(spec, ensure_ascii=False, indent=2)+'\n')
    admission = [sys.executable, '$JOBS/jobs.py', 'run', '--wait', '--owner', '動詞・指示28・'+label,
                 '--mem', str(spec['memory_reservation_gb']), '--disk-path', spec['output'], '--',
                 sys.executable, str(runner), str(case), '--clearance', '$CLEARANCE']
    (case/'admission_command.draft.json').write_text(json.dumps(dict(command=admission,
        cpu_slots=spec['cpu_start_slots'], model_slots=spec['model_start_slots'], executed=False,
        official_queue_and_clearance_required=True), ensure_ascii=False, indent=2)+'\n')
    return dict(case=str(case), ready_to_start=False, model_starts=0)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source', required=True); p.add_argument('--output-root', required=True)
    p.add_argument('--label', required=True)
    a = p.parse_args()
    print(json.dumps(prepare(a.source, a.output_root, a.label), ensure_ascii=False))

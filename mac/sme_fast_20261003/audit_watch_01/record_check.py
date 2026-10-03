"""fetch済みの合図、自己管理の20本、機械の余裕を記録する。走行は始めない。"""
from pathlib import Path
import datetime
import importlib.util
import json
import subprocess


def main():
    watch = Path(__file__).resolve().parent
    own = watch.parent
    repo = own.parent / 'codex_worldv4_2026-10-01/results'
    revision = subprocess.check_output(['git', 'rev-parse', 'origin/results-2026-09-27'], cwd=repo, text=True).strip()
    page = subprocess.check_output(['git', 'show', revision + ':control/2026-10-03_SME版の独立点検_走行の係.md'], cwd=repo, text=True)
    audit = {'time': datetime.datetime.now().astimezone().isoformat(), 'commit': revision,
             'exact_line_present': '【合図】SME独立点検 1〜8 全部通過（デスクトップ）' in page.splitlines()}
    plan = json.loads((own / 'production_plan_01/sme.commands.json').read_text())
    if len(plan) != 20 or sorted(row['seed'] for row in plan) != list(range(1, 21)):
        raise SystemExit('予定の本数又は種が範囲外')
    states = []
    for row in plan:
        if row['arm'] != 'w1_D_tau04':
            raise SystemExit('予定の腕が範囲外')
        output = Path(row['command'][3])
        manifest = output / 'manifest.jsonl'
        records = [json.loads(line) for line in manifest.read_text().splitlines()] if manifest.exists() else []
        states.append({'seed': row['seed'], 'output_exists': output.exists(), 'manifest_rows': len(records),
                       'completed': any(record.get('trial_count') == 1740 for record in records)})
    status = {'time': audit['time'], 'arm': 'w1_D_tau04', 'states': states,
              'completed_runs': sum(row['completed'] for row in states),
              'outputs_existing': sum(row['output_exists'] for row in states)}
    spec = importlib.util.spec_from_file_location('resource_check', own / 'exact_tools/run_one.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    resources = module.resources(own)
    for name, value in [('checks.jsonl', audit), ('production_status.jsonl', status), ('resources.jsonl', resources)]:
        with (watch / name).open('a') as stream:
            stream.write(json.dumps(value, ensure_ascii=False) + '\n')
    visible_resources = {key: value for key, value in resources.items() if key != 'memory'}
    print(json.dumps({'audit': audit, 'outputs_existing': status['outputs_existing'],
                      'completed_runs': status['completed_runs'], 'resources': visible_resources}, ensure_ascii=False))


if __name__ == '__main__':
    main()

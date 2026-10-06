"""受付の後、模型の過程の空きを確認して既存の計測台本を実行する。"""
from pathlib import Path
import json, os, sys, time

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent / 'codex_logp_main_2026-10-06'))
from common_01 import PY, conditions, cpu_reading, now, save

folder = Path(sys.argv[1]).resolve()
while True:
    resource = conditions()
    cpu = cpu_reading([])
    save(folder / 'registered_cpu_gate.json', {'at': now(), 'resources': resource, 'cpu': cpu})
    assert not resource['swap_grew'] and not resource['thermal_warning'], resource
    if resource['free_bytes'] >= 20 * 2**30 and cpu['total_compute_count'] < 8:
        break
    time.sleep(5)
os.execv(PY, [PY, str(ROOT / 'run_case_02.py'), str(folder)])

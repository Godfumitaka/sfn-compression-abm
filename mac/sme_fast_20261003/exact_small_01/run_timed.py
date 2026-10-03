"""sec_trialの値だけを除外し、Cと診断付きの残りの小走行を比較する。"""
from pathlib import Path
import json
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
HERE = Path(__file__).resolve().parent

for row in json.loads((HERE / 'plan.json').read_text()):
    if '--cf-learn' not in row['command'] and '--cf-value' not in row['command']:
        continue
    for phase, source in (('baseline', 'baseline_bdaa110'), ('fast', 'source')):
        subprocess.run([sys.executable, str(ROOT / 'exact_tools/run_one.py'),
                        str(HERE / (phase + '_' + row['name'] + '.command.json')), str(ROOT / source)], check=True)
    subprocess.run([sys.executable, str(ROOT / 'exact_tools/compare.py'),
                    str(HERE / 'baseline' / row['name'] / 'output'),
                    str(HERE / 'fast' / row['name'] / 'output'),
                    str(HERE / (row['name'] + '.comparison.json'))], check=True, stdout=subprocess.DEVNULL)
    print(row['name'] + '：sec_trial以外の全バイト一致', flush=True)

"""今回の試験の共通設定。鍵は環境から読むだけで保存しない。"""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
from decimal import Decimal
import hashlib
import json
import os
import sys

SCRIPT_DIR = Path(__file__).resolve().parent
ARCHIVED_SCRIPT = SCRIPT_DIR.name == 'scripts' and (SCRIPT_DIR.parent / 'scope.json').exists()
ROOT = SCRIPT_DIR.parent.parents[2] if ARCHIVED_SCRIPT else SCRIPT_DIR
PREVIOUS = ROOT.parent / 'codex_llm_door_2026-10-03'
SOURCE = PREVIOUS / 'source'
DEST = SCRIPT_DIR.parent if ARCHIVED_SCRIPT else ROOT / 'results/mac/llm_effort_instruction_20261004'
LEDGER = Path(os.environ['LLM_LEDGER_PATH'])
PREFIX = 'Codex 指示と考える量 2026-10-04'
CAP = Decimal('4')
MODEL = 'claude-sonnet-5-5'
OLD = 'Do not explain your reasoning. Output nothing except the JSON object.'
NEW = 'You may think the problem through before answering. Output only the JSON object.'
SOURCE_COMMIT = '73876dc2f020a70da02419c76bea0a3067164593'
sys.path.insert(0, str(SOURCE / 'llm_trial'))

def now():
    return datetime.now(ZoneInfo('Asia/Tokyo')).isoformat(timespec='seconds')

def sha(data):
    return hashlib.sha256(data).hexdigest()

def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=1) + '\n')

def read_rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line]

def append(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a') as stream:
        stream.write(json.dumps(value, ensure_ascii=False) + '\n')

def known_spent():
    return sum((Decimal(str(row['cost'])) for row in read_rows(LEDGER)
                if row['what'].startswith(PREFIX)), Decimal(0))

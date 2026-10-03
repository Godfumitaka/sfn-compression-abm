"""bdaa110の200試行を一本だけ計る。新しい高速化は入れない。"""
from pathlib import Path
import json
import os
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path[:0] = [str(HERE), str(ROOT / 'source/tools'), str(ROOT / 'source')]
import profile_hook
import v3_run

def main():
    command = json.loads((HERE / 'command.json').read_text())
    if Path(command[3]).exists():
        raise SystemExit('新しい出力先を使う。既存の記録は上書きしない')
    v3_run.worker = profile_hook.worker
    sys.argv = command[1:]
    os.chdir(ROOT / 'source')
    v3_run.main()

if __name__ == '__main__':
    main()

"""関門の出所タグだけを既存参照とそろえる。実際の版は外のspecへ残す。"""
import sys
from pathlib import Path
source=Path(sys.argv[1]).resolve()
sys.path[:0]=[str(source/'tools'),str(source)]
import sweep
import v3_run
sweep.code_commit=lambda:'4dc6a05d88ba10dbc22fd14ec77ec5c720e1c9a2'
if __name__=='__main__':
    sys.argv=[str(source/'tools/v3_run.py'),*sys.argv[2:]]
    v3_run.main()

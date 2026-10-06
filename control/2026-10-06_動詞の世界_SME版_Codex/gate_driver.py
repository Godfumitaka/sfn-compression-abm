"""一致関門ではヘッダの出所タグだけを共通に固定する。実際の版は外側で記録する。"""
import sys
from pathlib import Path
source = Path(sys.argv[1]).resolve()
sys.path[:0] = [str(source / 'tools'), str(source)]
import sweep
import v3_run
sweep.code_commit = lambda: '10cd8bdd46416aff55d0015e9072fc2186deed83'
if __name__ == '__main__':
    sys.argv = [str(source / 'tools/v3_run.py'), *sys.argv[2:]]
    v3_run.main()

"""関門だけ：①の材料保持を、新しい旗の値を変えずに呼ぶ。"""
from pathlib import Path
import sys
SOURCE = Path(__file__).resolve().parent/'source'
sys.path[:0] = [str(SOURCE/'tools'),str(SOURCE)]
import cstar_runtime
real_install = cstar_runtime.install
def keep_install(**options):
    return real_install(**options,material_keep=True)
cstar_runtime.install = keep_install
import v3_run
if __name__ == '__main__':
    v3_run.main()

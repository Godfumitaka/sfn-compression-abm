"""pytest が無くても全部の検査を走らせる：python3.12 tests/run_all.py"""
import importlib
import os
import sys
import time
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

fails = 0
total = 0
for fn in sorted(os.listdir(HERE)):
    if not (fn.startswith("test_") and fn.endswith(".py")):
        continue
    mod = importlib.import_module(fn[:-3])
    for name in sorted(dir(mod)):
        if not name.startswith("test_"):
            continue
        total += 1
        t = time.time()
        try:
            getattr(mod, name)()
            print(f"ok    {fn}:{name} ({time.time() - t:.2f}s)")
        except Exception:
            fails += 1
            print(f"FAIL  {fn}:{name}")
            traceback.print_exc()
print(f"{total - fails}/{total} passed")
sys.exit(1 if fails else 0)

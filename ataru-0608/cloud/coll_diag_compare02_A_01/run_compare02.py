"""指示 93（アストラのこの PC での直接の承認 10/11 08:2x）：compare_02 の compare(root,'on1-f0.1') を走らせ、gates/gate-on1-f0.1.compare02.json に書く。元の gate・STOP・compare.py には書かない。"""
import sys, json, traceback
from pathlib import Path
sys.path.insert(0, sys.argv[1]); sys.dont_write_bytecode = True
import compare_02
root = Path(sys.argv[2]); out = Path(sys.argv[3])
try:
    r = compare_02.compare(root, "on1-f0.1")
except Exception as e:
    r = dict(passed=False, candidate=compare_02.C, mode="on1-f0.1", error=repr(e), traceback=traceback.format_exc(), host=None, comparator="compare_02.py")
r["comparator"] = "compare_02.py"; r["comparator_sha256"] = "482f7afe60cb2594b359fd15127e516f36ecc8f7e5ff8974bcfee7468a57dcc6"
compare_02.save(out, r)
print(json.dumps({k: (v if not isinstance(v, (list, dict)) else len(v)) for k, v in r.items() if k != "traceback"}, ensure_ascii=False))
if r.get("traceback"): print(r["traceback"])

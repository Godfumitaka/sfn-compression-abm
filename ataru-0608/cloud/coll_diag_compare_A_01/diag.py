"""指示 87：診断だけ。包みの compare.py を変えずに読み込み、compare(root, 'on1-f0.1') を直接呼んで、例外の traceback と、その場の変数を残す。
gates/ と STOP.json には書かない（main を呼ばない）。"""
import sys, traceback, json
sys.path.insert(0, sys.argv[1]); sys.dont_write_bytecode = True
import compare
out = sys.argv[3]
try:
    r = compare.compare(__import__("pathlib").Path(sys.argv[2]), "on1-f0.1")
    open(out + "/result.json", "w").write(json.dumps({"passed": r.get("passed"), "note": "例外なし"}, ensure_ascii=False))
except BaseException:
    tb = traceback.format_exc(); open(out + "/traceback.txt", "w").write(tb); print(tb)
    t = sys.exc_info()[2]
    while t.tb_next: t = t.tb_next
    loc = {k: (repr(v)[:2000]) for k, v in t.tb_frame.f_locals.items()}
    open(out + "/locals.json", "w").write(json.dumps({"file": t.tb_frame.f_code.co_filename, "line": t.tb_lineno, "function": t.tb_frame.f_code.co_name, "locals": loc}, ensure_ascii=False, indent=1))
    print("行", t.tb_frame.f_code.co_filename, t.tb_lineno, t.tb_frame.f_code.co_name); print(json.dumps(loc, ensure_ascii=False)[:3000])

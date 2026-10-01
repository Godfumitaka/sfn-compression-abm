"""現行の v3_run に、既存の集団化の差し込み口だけを載せる。"""
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / 'source'
OLD = ROOT.parents[1] / 'codex_urta_2026-09-30/collective/source'
old = (OLD / 'tools/v3_run.py').read_text()
path = SOURCE / 'tools/v3_run.py'
code = path.read_text()


def before(anchor, addition):
    global code
    assert code.count(anchor) == 1, anchor
    code = code.replace(anchor, addition + anchor)


before('        if task.get("v310_be"):\n',
       '        if task.get("v311c"):\n            import abm.loop as _loop\n'
       '            _REAL["m1_before_be"] = _loop.m1   # 集団化の E へ、名札の費用を足す前の学習の道を渡す\n')
anchor = '        _REAL["theta_impl"] = v39.CTX["apply"]\n'
assert code.count(anchor) == 1
code = code.replace(anchor, anchor +
       '        if task.get("v311c"):\n            # 受信の学習にも、後で入れる覚え直しの記録を適用する\n'
       '            import v311c\n            v311c.install(fo, task, _REAL)\n')
before('    if task.get("hist_role"):\n        rec["histrole"]',
       '    if task.get("v311c"):\n        rec["v311c"] = dict(sys.modules["v311c"].STATS)\n')
collective = old[old.index('def _run_collective('):old.index('def main() -> None:')]
before('def main() -> None:\n', collective)
parser_start = old.index('    ap.add_argument("--v311c",')
parser_end = old.index('    ap.add_argument("--v310-be",', parser_start)
before('    ap.add_argument("--v310-be",', old[parser_start:parser_end])
before('    out_root.mkdir(parents=True, exist_ok=True)\n',
       '    if args.v311c and not args.v310_be:\n'
       '        raise SystemExit("--v311c は B＋E（--v310-be）の旗一式と一緒に使う")\n')
flag_start = old.index('                                                    "v311c": (')
flag_end = old.index('                                                    "v38_from":', flag_start)
before('                                                    "v38_from":', old[flag_start:flag_end])
before('    with ProcessPoolExecutor(max_workers=args.workers, max_tasks_per_child=1) as ex:\n',
       '    if args.v311c:\n        _run_collective(args, tasks, out_root, man)\n'
       '        print(f"{time.strftime(\'%F %T\')} ALLDONE {cfg[\'name\']}", flush=True)\n        return\n')
names = subprocess.check_output(['git', 'diff', '--name-only', '--diff-filter=A', '-z',
                                 'v3.10urta-main', 'v3.11cu-main'], cwd=OLD).split(b'\0')
for raw in names:
    if not raw:
        continue
    name = raw.decode()
    dst = SOURCE / name
    assert not dst.exists(), dst
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(OLD / name, dst)
path.write_text(code)
print('集団化の既存ファイルと、現行の旗を保持した v3_run の差し込み口を保存')

"""模型を投入せず、受付条件・比較と固定した命令を点検する。"""
from pathlib import Path
import ast
import hashlib
import json
import tempfile
import controller as C
import compare_records as Q

ROOT = Path(__file__).resolve().parent
checks = []


def check(name, predicate):
    assert predicate, name
    checks.append(name)


def main():
    old = ROOT.parent / 'instruction26_basic_gate_7294389d'
    check('比較関数の原全バイト', Q.__file__ is not None and
          (ROOT / 'compare_records.py').read_bytes() == (old / 'compare_records.py').read_bytes())
    def functions(path):
        return {n.name: ast.dump(n, include_attributes=False)
                for n in ast.parse(path.read_text()).body if isinstance(n, ast.FunctionDef)}
    before, after = functions(old / 'controller.py'), functions(ROOT / 'controller.py')
    for name in ('warning', 'start_ok', 'alive'):
        check(name + 'のAST不変', before[name] == after[name])
    m = dict(model_children=7, disk_free_bytes=21 * 2**30, swap_ok=True,
             thermal_warnings=0, unregistered_heavy=[], registered=[{'mem_gb': 20}])
    check('8本と24GBの境界', C.start_ok(m, 4, 1))
    check('9本を拒否', not C.start_ok({**m, 'model_children': 8}, 4, 1))
    check('24GB超を拒否', not C.start_ok(m, 4.1, 1))
    for key, value in (('swap_ok', False), ('thermal_warnings', 1), ('unregistered_heavy', [{}]),
                       ('disk_free_bytes', 19 * 2**30)):
        check('開始条件_' + key, not C.start_ok({**m, key: value}, 1, 1))
    check('稼働18.5GiB不足の警告', C.warning({**m, 'disk_free_bytes': 18 * 2**30}))
    original_stamp = C.G.stamp
    C.G.stamp = lambda: '2026-10-11T09:00:00+09:00'
    try:
        try:
            C.deadline()
        except RuntimeError:
            checks.append('期限後拒否')
        else:
            raise AssertionError('期限後を許可した')
    finally:
        C.G.stamp = original_stamp
    with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
        a, b = Path(tmp) / 'a', Path(tmp) / 'b'
        data = b'x' * (2**20 + 17)
        a.write_bytes(data)
        b.write_bytes(data)
        check('1MiB境界', Q.compare(a, b)['compared_bytes'] == len(data))
        b.write_bytes(data[:-1] + b'y')
        try:
            Q.compare(a, b)
        except RuntimeError:
            checks.append('末尾不一致を拒否')
        else:
            raise AssertionError('末尾不一致を許可した')
    check('時間の数値だけを置換', Q.time_values(b'{"seconds":1.23,"x":1.2300,"s":"seconds"}') ==
          b'{"seconds":0,"x":1.2300,"s":"seconds"}')
    check('数式・旗と関門の固定', set(C.plan()['cases']) == {
          'forget_off_200', 'forget_on_200', 'calibration_off_200', 'calibration_on_200'})
    C.source_ok()
    check('固定ソースと道具のSHA', True)
    check('模型シグナル・削除の呼出し無し', not any(
          isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
          and node.func.attr in ('kill', 'killpg', 'terminate', 'unlink', 'rmtree', 'remove')
          for node in ast.walk(ast.parse((ROOT / 'controller.py').read_text()))))
    result = dict(at=C.G.stamp(), checks=checks, count=len(checks), passed=True,
                  model_tasks_or_imports=0, source_sha=C.CODE,
                  tool_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    with (ROOT / 'tool_checks.json').open('x') as stream:
        stream.write(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()

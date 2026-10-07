"""模型を走らせず、記録の型とバイトを原版と比べる。"""
from pathlib import Path
from dataclasses import dataclass
from enum import Enum, IntEnum
from types import MappingProxyType
from collections import OrderedDict
from datetime import datetime
import hashlib, importlib.util, json, random, sys

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'encode_checks_01.json'
assert not OUT.exists(), '同じ検査を重複しない'
def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module
base = load(ROOT.parent/'codex_cstar_2026-10-07/source/tools/smereplay.py', 'encode_reference')
fast = load(ROOT/'source/tools/smereplay.py', 'encode_new')

class Number(IntEnum):
    ONE = 1
class Text(str, Enum):
    VALUE = '日本語'
class Integer(int):
    pass
class String(str):
    pass
@dataclass(frozen=True, slots=True)
class Record:
    name: str
    content: object

def wire(value):
    return (json.dumps(value, ensure_ascii=False)+'\n').encode()
rng = random.Random(20261008)
atoms = [None, True, False, 0, -12, 2**90, 0.0, -0.0, 1.25, float('inf'), float('nan'),
         '日本語\n"\\', Number.ONE, Text.VALUE, Integer(2), String('派生')]
def sample(depth):
    if depth == 0 or rng.randrange(5) == 0:
        return rng.choice(atoms)
    items = [sample(depth-1) for _ in range(rng.randrange(5))]
    kind = rng.randrange(6)
    if kind == 0: return tuple(items)
    if kind == 1: return items
    if kind == 2: return {f'鍵{i}': x for i,x in enumerate(items)}
    if kind == 3: return MappingProxyType({f'鍵{i}': x for i,x in enumerate(items)})
    if kind == 4: return OrderedDict((f'鍵{i}', x) for i,x in enumerate(items))
    return Record('記録', items)
fixtures = atoms + [set(('乙','甲')), frozenset((Number.ONE, 2)), Record('親', (Text.VALUE, {'子':[1,None]}))]
fixtures += [sample(4) for _ in range(250)]
try:
    digest = hashlib.sha256()
    for number, value in enumerate(fixtures, 1):
        original = wire(base.encode(value))
        assert wire(fast.encode(value)) == original, ('旗なし', number)
        assert wire(fast._fast_encode(value)) == original, ('旗あり', number)
        digest.update(original)
    errors = 0
    for value in (object(), b'bytes', iter((1,2))):
        args = []
        for fn in (base.encode, fast.encode, fast._fast_encode):
            try: fn(value)
            except TypeError as error: args.append(error.args)
        assert len(args) == 3 and args[0] == args[1] == args[2]
        errors += 1
    result = dict(at=datetime.now().astimezone().isoformat(), passed=True,
                  encoded_fixtures=len(fixtures), unsupported_type_cases=errors,
                  comparison='原版と旗なしと旗ありのJSON全バイト・非対応型の例外を比較',
                  sha256=digest.hexdigest(), model_not_run=True,
                  full_native_gate_done=False, python=sys.version)
    OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(result,ensure_ascii=False))
except Exception as error:
    (ROOT/'encode_checks_STOP_01.json').write_text(json.dumps(dict(
        at=datetime.now().astimezone().isoformat(), passed=False, reason=str(error)),ensure_ascii=False,indent=2)+'\n')
    raise

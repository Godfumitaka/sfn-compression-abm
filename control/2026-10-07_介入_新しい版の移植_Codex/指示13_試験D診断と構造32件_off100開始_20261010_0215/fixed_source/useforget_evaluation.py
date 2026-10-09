"""指示13：試験・反実仮想ではDの包みを通さない。復元はしない。"""
from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
import sys

_DEPTH = 0
CHECKS = []


def active():
    return _DEPTH > 0


@contextmanager
def evaluation():
    global _DEPTH
    _DEPTH += 1
    try:
        yield
    finally:
        _DEPTH -= 1


def install(path):
    """Dありの経路だけ。計算入口を変えず、Dの書き込みを入る前に止める。"""
    import useforget_cstar as N
    CHECKS.clear()
    destination = Path(path)

    def wrap(module, name):
        native = getattr(module, name)
        def evaluated(*args, **kwargs):
            before = N.probe_snapshot()
            with evaluation():
                result = native(*args, **kwargs)
            after = N.probe_snapshot()
            same = before == after
            CHECKS.append(dict(call=f'{module.__name__}.{name}', unchanged=same,
                before_sha256=hashlib.sha256(before).hexdigest(),
                after_sha256=hashlib.sha256(after).hexdigest()))
            destination.write_text(json.dumps(CHECKS, ensure_ascii=False, indent=2)+'\n')
            if not same:
                raise RuntimeError('指示13：試験又は反実仮想がDの状態又は記録を変えた')
            return result
        setattr(module, name, evaluated)

    for module_name, function in [('probeworld', '_probe'), ('cfvalue', '_measure'),
                                 ('cflearn', 'variants_correct')]:
        module = sys.modules.get(module_name)
        if module is not None:
            wrap(module, function)

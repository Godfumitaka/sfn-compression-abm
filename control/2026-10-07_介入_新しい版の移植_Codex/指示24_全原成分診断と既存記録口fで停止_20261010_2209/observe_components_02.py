"""指示24：元の先頭200観察器をそのまま実行し、原控えの成分だけ別保存する。"""
from pathlib import Path
import hashlib
import json
import os
import sys

SOURCE = Path(sys.argv[1] if __name__ == '__main__' else os.environ['VERB_MEASUREMENT_SOURCE'])
sys.path[:0] = [str(SOURCE/'tools'), str(SOURCE)]
import useforget as D
import useforget_cstar as C

ROOT = Path(os.environ['INTERVENTION24_COMPONENT_ROOT'])
native_snapshot = C.probe_snapshot
native_install_guard = C.install_probe_guard
context = dict(trial=None, sequence=0, calls=0)


def capture_snapshot():
    """元関数の戻り字節を変えず、同じ時点の全成分と記録口を保存する。"""
    original = native_snapshot()
    if context['trial'] is None or sys._getframe(1).f_code is not context['native_guard_code']:
        return original
    context['calls'] += 1
    phase = 'before' if context['calls'] == 1 else 'after'
    assert context['calls'] in (1, 2)
    root = ROOT/f"pid{os.getpid()}_trial{context['trial']:04d}_{context['sequence']:02d}_{phase}"
    root.mkdir(parents=True, exist_ok=False)
    files = []
    records = []
    components = {}
    for label, store in [('D.ST', D.ST), ('AUDIT', C.AUDIT)]:
        raw = repr(store).encode('utf-8')
        (root/(label+'.original_repr.bin')).write_bytes(raw)
        entries = []
        for index, (key, value) in enumerate(store.items()):
            key_raw = repr(key).encode('utf-8')
            value_raw = repr(value).encode('utf-8')
            (root/f'{label}.key{index:03d}.bin').write_bytes(key_raw)
            (root/f'{label}.value{index:03d}.bin').write_bytes(value_raw)
            entry = dict(index=index, key_repr=repr(key), value_sha256=hashlib.sha256(value_raw).hexdigest())
            if hasattr(value, 'tell') and hasattr(value, 'name') and not value.closed:
                position = value.tell()
                name = value.name
                content = Path(name).read_bytes()
                files.append((name, position, content))
                content_name = f'{label}.port{index:03d}.raw'
                (root/content_name).write_bytes(content)
                record = dict(store=label, index=index, key_repr=repr(key), name=name,
                              position=position, raw_file=content_name, raw_bytes=len(content),
                              raw_sha256=hashlib.sha256(content).hexdigest(),
                              type_name=type(value).__module__+'.'+type(value).__qualname__,
                              mode=value.mode, encoding=getattr(value, 'encoding', None),
                              closed=value.closed, original_repr=repr(value))
                records.append(record)
                entry['record_port'] = record
            entries.append(entry)
        components[label] = dict(raw_file=label+'.original_repr.bin', raw_bytes=len(raw),
                                 raw_sha256=hashlib.sha256(raw).hexdigest(), entries=entries)
    reconstructed = repr(((D.ST, C.AUDIT), files)).encode('utf-8')
    assert reconstructed == original, '原関数の全字節と、成分をそのまま戻した字節が異なる'
    (root/'native_snapshot.original.bin').write_bytes(original)
    evidence = dict(pid=os.getpid(), trial=context['trial'], phase=phase,
                    snapshot_sha256=hashlib.sha256(original).hexdigest(), components=components,
                    record_ports=records, original_snapshot_reconstructed_exactly=True,
                    model_state_restored=False, model_record_ports_flushed=False)
    (root/'components.json').write_text(json.dumps(evidence, ensure_ascii=False, indent=2)+'\n')
    return original


def install_guard():
    native_install_guard()
    import probeworld
    native_probe = probeworld._probe
    context['native_guard_code'] = native_probe.__code__

    def probe(state, config, trial):
        context.update(trial=trial, sequence=context['sequence']+1, calls=0)
        try:
            result = native_probe(state, config, trial)
            assert context['calls'] == 2
            return result
        finally:
            context['trial'] = None

    probeworld._probe = probe


C.probe_snapshot = capture_snapshot
C.install_probe_guard = install_guard
ORIGINAL = Path(__file__).resolve().parents[1]/'instruction12/observer_200.py'
original_bytes = ORIGINAL.read_bytes()
assert hashlib.sha256(original_bytes).hexdigest() == 'ccb924c4653572e116ac38fb35d21c202689e32dc848daca16825564af2e4903'
exec(compile(original_bytes, str(ORIGINAL), 'exec'), globals(), globals())

"""指示13の研究者側診断。DとAUDITを読み、元の不変検査を保つ。"""
from pathlib import Path
import json
import hashlib
import sys


def snapshot():
    import useforget as D
    import useforget_cstar as N
    values = {}; files = {}
    for name, store in [('ST', D.ST), ('AUDIT', N.AUDIT)]:
        values[name] = {str(key): repr(value) for key, value in store.items()}
        for key, value in store.items():
            if hasattr(value, 'tell') and hasattr(value, 'name') and not value.closed:
                position = value.tell()
                raw = Path(value.name).read_bytes()
                files[f'{name}.{key}'] = dict(path=value.name, position=position,
                    raw_hex=raw.hex(), raw_sha256=hashlib.sha256(raw).hexdigest())
    return dict(values=values, files=files)


def differences(before, after):
    changes = []
    for store in ('ST', 'AUDIT'):
        a = before['values'][store]; b = after['values'][store]
        for key in dict.fromkeys([*a, *b]):
            if a.get(key) != b.get(key):
                changes.append(dict(component=f'{store}.{key}', before=a.get(key), after=b.get(key)))
    for key in dict.fromkeys([*before['files'], *after['files']]):
        a = before['files'].get(key); b = after['files'].get(key)
        if a != b:
            prior = bytes.fromhex(a['raw_hex']) if a else b''
            current = bytes.fromhex(b['raw_hex']) if b else b''
            added = current[len(prior):] if current.startswith(prior) else None
            changes.append(dict(component=f'file.{key}', before=a, after=b,
                appended_hex=None if added is None else added.hex(),
                appended_lines=None if added is None else added.decode('utf-8', errors='backslashreplace').splitlines()))
    return changes


def install(path, *, candidate):
    import abm.loop as loop
    import v39
    import probeworld as P
    import useforget_cstar as N
    if not candidate:
        # 同じ旧候補の全ST・AUDIT・原記録字節検査を旧Dにも付ける。
        N.install_probe_guard()
    output = Path(path); output.parent.mkdir(parents=True, exist_ok=True)
    original = P._probe
    active = []; events = []

    def watch(module, name):
        native = getattr(module, name)
        def observed(*args, **kwargs):
            if not active:
                return native(*args, **kwargs)
            before = snapshot()
            try:
                return native(*args, **kwargs)
            finally:
                after = snapshot(); changes = differences(before, after)
                if changes:
                    events.append(dict(call=f'{module.__name__}.{name}', changes=changes))
        setattr(module, name, observed)

    for module, name in [(loop, '_agent_input'), (loop, 'm1'), (v39, 'run_conversions')]:
        watch(module, name)

    def probe(state, config, trial):
        before = snapshot(); raw_before = N.probe_snapshot()
        events.clear(); active.append(trial); error = None
        first_mutation = []
        previous_trace = sys.gettrace()
        targets = {str(Path(__file__).parent/name) for name in ('useforget.py', 'useforget_cstar.py')}
        def trace(frame, event, arg):
            if frame.f_code.co_filename not in targets:
                return None
            if event in ('line', 'return') and not first_mutation:
                current = snapshot(); changed = differences(before, current)
                if changed:
                    first_mutation.append(dict(file=frame.f_code.co_filename,
                        function=frame.f_code.co_name, observed_at_line=frame.f_lineno,
                        changes=changed, snapshot=current))
                    sys.settrace(previous_trace)
                    return None
            return trace
        sys.settrace(trace)
        try:
            return original(state, config, trial)
        except BaseException as caught:
            error = repr(caught)
            raise
        finally:
            sys.settrace(previous_trace)
            active.pop()
            after = snapshot(); raw_after = N.probe_snapshot()
            record = dict(trial=trial, candidate=candidate, unchanged=raw_before == raw_after,
                before_sha256=hashlib.sha256(raw_before).hexdigest(),
                after_sha256=hashlib.sha256(raw_after).hexdigest(),
                before=before, after=after, changes=differences(before, after),
                first_observed_call_change=events[0] if events else None,
                call_changes=events, first_temporal_mutation=first_mutation[0] if first_mutation else None, exception=error,
                model_state_restored_by_this_diagnostic=False)
            output.write_text(json.dumps(record, ensure_ascii=False, indent=2)+'\n')
            output.with_suffix('.before.bin').write_bytes(raw_before)
            output.with_suffix('.after.bin').write_bytes(raw_after)
            # 元の検査に加えて原字節を再確認し、診断だけの読み違いでも続けない。
            if raw_before != raw_after and error is None:
                raise RuntimeError(f'指示13：試験がDの状態又は記録を変えた（試行 {trial}）')
    P._probe = probe

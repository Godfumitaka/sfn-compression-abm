"""指示22：原assertの例外と公開側の値だけを研究者の別ファイルへ保存する。"""
import datetime
import json
import os
from pathlib import Path
import sys

_destination = os.environ.get('INTERVENTION22_ASSERT_DEST')
_roots = tuple(os.environ.get('INTERVENTION22_ASSERT_ROOTS', '').split(os.pathsep))
_written = False


def plain(value, depth=0):
    # 模型のメソッドやreprを呼ばず、組み込みの値だけを読む。
    if value is None or type(value) in (bool, int, float, str):
        return value
    if depth >= 5:
        return {'type': type(value).__name__}
    if type(value) is dict and len(value) <= 500:
        return {str(k): plain(v, depth+1) for k, v in value.items()
                if type(k) in (str, int, float, bool, tuple)}
    if type(value) in (tuple, list, set, frozenset) and len(value) <= 500:
        values = sorted(value) if type(value) in (set, frozenset) and all(type(x) is str for x in value) else value
        return [plain(x, depth+1) for x in values]
    return {'type': type(value).__name__}


def frame_values(frame):
    result = {}
    for name, value in frame.f_locals.items():
        if type(value) in (bool, int, float, str, dict, list, tuple, set, frozenset) or value is None:
            result[name] = plain(value)
        elif name in ('observation', 'observations') and type(value).__name__ == 'Observations':
            result[name] = {'names': plain(vars(value)['names']),
                            'last_trial': plain(vars(value).get('last_trial'))}
        elif name == 'state':
            # 名前の控えのassertの両辺。正解・開示前の隠した辺は読まない。
            table = vars(value).get('p_hat') if hasattr(value, '__dict__') else None
            result[name] = {'type': type(value).__name__}
            if table is not None and hasattr(table, '__dict__'):
                result[name]['p_hat'] = plain(vars(table))
        else:
            result[name] = {'type': type(value).__name__}
    return result


def raised(code, offset, exception):
    global _written
    if _written or type(exception) is not AssertionError:
        return
    if not any(root and code.co_filename.startswith(root + os.sep) for root in _roots):
        return
    frame = sys._getframe(1)
    while frame is not None and frame.f_code is not code:
        frame = frame.f_back
    if frame is None:
        return
    _written = True
    stack = []
    current = frame
    while current is not None:
        stack.append({'file': current.f_code.co_filename, 'line': current.f_lineno,
                      'function': current.f_code.co_name, 'locals': frame_values(current)})
        current = current.f_back
    data = {'pid': os.getpid(), 'ppid': os.getppid(),
            'at_jst': datetime.datetime.now().astimezone().isoformat(),
            'file': code.co_filename, 'line': frame.f_lineno, 'function': code.co_name,
            'instruction_offset': offset, 'exception_type': type(exception).__name__,
            'exception_args': plain(exception.args), 'stack': stack,
            'researcher_only': True, 'exception_propagation_unchanged': True}
    target = Path(_destination) / ('assert_pid' + str(os.getpid()) + '.json')
    with target.open('x') as stream:
        json.dump(data, stream, ensure_ascii=False, indent=2)
        stream.write('\n')


if _destination:
    # Python3.12の例外イベントだけを観察し、各行の実行や戻り値には介入しない。
    sys.monitoring.use_tool_id(5, 'intervention22_assert_readonly')
    sys.monitoring.register_callback(5, sys.monitoring.events.RAISE, raised)
    sys.monitoring.set_events(5, sys.monitoring.events.RAISE)

"""P5・P7r：第二段の同じ試行・同じ完全な鍵だけを使い回す。

反実仮想の復元から独立した控え。模型の統計と順つきの控えは元と同じに
書く。OLD_MAPの浅いSTATS復元で残る入れ子Counterも同じ順で再現する。
"""
from collections import Counter
import sys

ENABLED = False
TRIAL = object()
MAPPINGS = {}
AUDITS = []
STATS = {}


def configure(enabled=False):
    global ENABLED, TRIAL
    ENABLED = bool(enabled)
    TRIAL = object()
    MAPPINGS.clear()
    AUDITS.clear()
    STATS.clear()
    STATS.update(p5_runs=0, p5_hits=0, p7_stores=0, p7_hits=0, p7_replayed_calls=0)


def _trial():
    return sys.modules['smeshared'].CTX.get('trial')


def engine_side(engine):
    """engineのsnapshotに含めず、試行が変われば空にする。"""
    trial = _trial()
    if getattr(engine, '_stage2_memo_trial', object()) != trial:
        engine._stage2_memo_trial = trial
        engine._stage2_memo_results = {}
    return engine._stage2_memo_results


def active(expected, seed):
    global TRIAL
    if not ENABLED or not expected or seed is None:
        return False
    shared = sys.modules['smeshared']
    cstar = sys.modules.get('cstar_runtime')
    if (shared.LOG.get('f') is not None or shared.LOG.get('diagnostic_f') is not None
            or cstar is None or getattr(cstar.ENGINE, '_stage2_scope', None) is None):
        return False
    trial = _trial()
    if TRIAL != trial:
        MAPPINGS.clear()
        TRIAL = trial
    return True


def mapping_hit(expected, seed, key):
    if not active(expected, seed):
        return None
    entry = MAPPINGS.get(key)
    if entry is not None:
        STATS['p7_hits'] += 1
    return entry


def mapping_store(expected, seed, key, out, calls):
    if active(expected, seed):
        if calls is None:
            raise RuntimeError('P7rのOLD_MAPの記録が無い')
        MAPPINGS[key] = out, calls
        STATS['p7_stores'] += 1


def begin_audit(expected, seed):
    if not active(expected, seed):
        return None
    # 呼び出すmap_graphsのframeを識別し、同名のOLD_MAPと混同しない。
    record = dict(frame=sys._getframe(1), calls=[])
    AUDITS.append(record)
    return record


def end_audit(record):
    if record is None:
        return None
    if not AUDITS or AUDITS[-1] is not record:
        raise RuntimeError('P7rのOLD_MAPの記録の入れ子が違う')
    AUDITS.pop()
    calls = record['calls']
    record.clear()  # frameの循環参照を控えへ残さない。
    return calls


def record_use(names, frames, caller):
    if not AUDITS:
        return
    record = AUDITS[-1]
    depth = next((i for i, frame in enumerate(frames) if frame is record['frame']), None)
    record['calls'].append((tuple(names[:depth] if depth is not None else names), depth,
                            caller.f_locals['n'], Counter(caller.f_locals['reasons'])))


def replay_calls(calls):
    if calls is None:
        raise RuntimeError('P7rの控えにOLD_MAPの記録が無い')
    sp = sys.modules.get('strictpc')
    if sp is None:
        if calls:
            raise RuntimeError('P7rのstrictpcの記録の読み先が無い')
        return
    here = sys._getframe(1)
    for internal, depth, n, reasons in calls:
        names = list(internal)
        if depth is not None:
            frame = here
            while frame is not None and len(names) < 40:
                names.append(frame.f_code.co_name)
                frame = frame.f_back
        label = next((label for fn, label in sp.USES if fn in names), 'その他')
        # calls/droppedなどの整数は元の浅い復元で戻る。三Counterだけが残る。
        sp.STATS['reasons'].update(reasons)
        sp.STATS['use_calls'][label] += 1
        sp.STATS['use_dropped'][label] += n
        STATS['p7_replayed_calls'] += 1

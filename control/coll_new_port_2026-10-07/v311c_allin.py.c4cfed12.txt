"""準備版の計算を集団化へ接続する。受信の材料と診断の文脈だけを扱う。"""
from collections.abc import Mapping
from contextlib import contextmanager, nullcontext
from copy import deepcopy
from dataclasses import fields, is_dataclass, replace
from enum import Enum
from fractions import Fraction
import inspect
import io
import json
from pathlib import Path
import sys

CTX = {}
ST = {}


def runtime_values(value, memo=None):
    """既知の追加状態を型・順付きで読む。未知の型をreprへ落とさない。"""
    memo = {} if memo is None else memo
    if isinstance(value, Enum):
        return ["enum", type(value).__module__, type(value).__name__, value.value]
    if value is None or type(value) in (str, int, float, bool, Fraction):
        return value
    key = id(value)
    if key in memo:
        return memo[key]
    if is_dataclass(value):
        out = ["dataclass", type(value).__module__, type(value).__name__, []]
        memo[key] = out
        out[3].extend((f.name, runtime_values(getattr(value, f.name), memo)) for f in fields(value))
        return out
    if isinstance(value, Mapping):
        out = ["mapping", []]; memo[key] = out
        out[1].extend((runtime_values(k, memo), runtime_values(v, memo)) for k, v in value.items())
        return out
    if type(value) in (set, frozenset):
        from v311c_fingerprint import canonical_text
        out = [type(value).__name__, sorted((runtime_values(v, memo) for v in value), key=canonical_text)]
        memo[key] = out
        return out
    if type(value) in (list, tuple):
        out = type(value)(runtime_values(v, memo) for v in value)
        memo[key] = out
        return out
    if (type(value).__module__, type(value).__name__) in (
            ("attnsme_features", "Observations"), ("attnstage2_questions", "Questions")):
        out = ["object", type(value).__module__, type(value).__name__, None]
        memo[key] = out
        out[3] = runtime_values(vars(value), memo)
        return out
    raise TypeError((type(value), "集団化の追加状態の検査で扱わない型"))


def runtime_record():
    """次の実課題が読む観察・注意・問い回数・実開示の名前を全量で残す。"""
    out = {}
    attention = sys.modules.get("attnsme")
    if attention is not None and attention.ST:
        out["attention"] = runtime_values(attention.ST["individuals"])
    stage2 = sys.modules.get("attnstage2_runtime")
    if stage2 is not None and stage2.ST:
        out["questions"] = runtime_values(stage2.ST["questions"])
    return out


def isolation_record():
    """試験中に触れる一時の文脈も含める。書込先は模型の材料にしない。"""
    frames = {}
    for name in ("attnsme", "attnstage2_runtime"):
        module = sys.modules.get(name)
        if module is not None:
            frames[name] = runtime_values({k: v for k, v in module.ST.items()
                if k not in ("f", "stream", "initial_stream", "rematch_stream")})
    return frames


def snapshot_mutables():
    """入れ子を元の実体へ戻す。pendingの同一性と別名参照も保つ。"""
    saved, seen = [], set()
    def visit(value):
        key = id(value)
        if key in seen:
            return
        seen.add(key)
        if isinstance(value, dict):
            saved.append((value, value.copy()))
            for item in value.values(): visit(item)
        elif isinstance(value, list):
            saved.append((value, value.copy()))
            for item in value: visit(item)
        elif isinstance(value, set):
            saved.append((value, value.copy()))
        elif isinstance(value, tuple):
            for item in value: visit(item)
        elif (type(value).__module__, type(value).__name__) in (
                ("attnsme_features", "Observations"), ("attnstage2_questions", "Questions")):
            visit(vars(value))
    for name in ("attnsme", "attnstage2_runtime"):
        module = sys.modules.get(name)
        if module is not None: visit(module.ST)
    evict = sys.modules.get("smeevict")
    if evict is not None and evict.MANAGER is not None:
        visit(vars(evict.MANAGER))
    return saved


def restore_mutables(saved):
    for current, old in saved:
        current.clear()
        if isinstance(current, list): current.extend(old)
        else: current.update(old)


def observe_report(observation, graph):
    """公開された実材料だけを観察へ加える。実課題の時計・問いは進めない。"""
    import attnposition_keys as K
    rows = [r.to_dict() for r in graph.relations]
    entities = {e.entity_id for e in graph.entities}
    observation.structure(rows, entities)
    visible = K.position_index(rows, entities)
    for row in rows:
        name = row["predicate"]
        observation.names.add(name)
        observation.shapes[name].add(K.shape(row, entities))
        key = visible["keys"][row["relation_id"]]
        if key is not None:
            counts = observation.table.setdefault(key, {})
            counts[name] = counts.get(name, 0) + 1


@contextmanager
def receive_context(state, graph, trial, config):
    """束を頻度へ書く前の状態を固定する。世界の予測前の控えと分ける。"""
    import v310be as B
    import v311c as C
    from abm.domains import AgentInput
    star = sys.modules.get("cstar_runtime")
    attention = sys.modules.get("attnsme")
    stage2 = sys.modules.get("attnstage2_runtime")
    b_saved = dict(B.CTX)
    star_saved = None if star is None else dict(star.CTX)
    second_saved = None
    initial = CTX.get("initial_policy")
    initial_cache = None if initial is None else dict(initial.cache)
    record_start = 0 if initial is None else len(initial.records)
    B.CTX["score_state"] = state
    if star is not None:
        star.CTX.update(prediction_state=state, last_partial=graph, collective_receive=True)
    if stage2 is not None and stage2.ST:
        if attention is None or not attention.ST:
            raise RuntimeError("報告の第二段の初期値に注意の控えが無い")
        second_saved = (stage2.ST.get("current_pre"), stage2.ST.get("question"))
        observations = deepcopy(attention.ST["individual"]["observations"])
        # 世界の観察は台帳の記録で確定する。受信用の写しには、既に受けた
        # 世界の可視部と実開示だけを先に渡し、実体を二度更新しない。
        world = CTX["world_observation"]
        if observations.last_trial < trial:
            observations.after(trial, world["scene"], world["entities"], world["disclosed"])
        # 仮問いの区分は、実課題の予測前に固定した名前集合のまま。
        # 今の開示を同じ試行の誕生へ戻さず、受信も実課題として数えない。
        question = stage2.ST["question"]
        ai = AgentInput(graph, graph, tuple(r.relation_id for r in graph.relations))
        stage2.ST["current_pre"] = (ai, state, config, state.rng_state, observations,
            dict(attention.ST["individual"]["a"]), False, (), None)
        stage2.ST["question"] = question
        if initial is not None: initial.cache.clear()
    try:
        yield
    finally:
        if initial is not None:
            for row in initial.records[record_start:]:
                row.update(source="報告", bundle=graph.graph_id)
            initial.cache.clear(); initial.cache.update(initial_cache)
        if second_saved is not None:
            stage2.ST["current_pre"], stage2.ST["question"] = second_saved
        B.CTX.clear(); B.CTX.update(b_saved)
        if star_saved is not None:
            star.CTX.clear(); star.CTX.update(star_saved)


def install(task, side_dir):
    import abm.loop as loop
    import v311c as C
    import smeshared as S
    import smereplay as R
    import v39
    CTX.clear(); ST.clear()
    C.CFG["allin_runtime"] = True
    stage2 = sys.modules.get("attnstage2_runtime")
    if stage2 is not None and stage2.ST:
        initial = inspect.getclosurevars(v39._init_rec).nonlocals.get("initial_policy")
        if initial is not None and hasattr(initial, "cache"):
            CTX["initial_policy"] = initial

    original_account = loop._update_accounting
    def accounting(state, output, scene, config, horizon, score, coin, revealed):
        result = original_account(state, output, scene, config, horizon, score, coin, revealed)
        # 非開示では研究者の辺の欄を読む式を評価しない。
        CTX["world_observation"] = dict(scene=[r.to_dict() for r in scene.relations],
            entities={e.entity_id for e in scene.entities},
            disclosed=revealed.to_dict() if coin.f_fired else None)
        return result
    loop._update_accounting = accounting

    original_partner = C.choose_partner
    def partner(state, graph, tag, mode):
        star = sys.modules.get("cstar_runtime")
        scope = nullcontext() if star is None else star.phase(state, v39.CTX["config"], graph,
            bool(star.CFG["match_cstar_e"]))
        with scope:
            return original_partner(state, graph, tag, mode)
    C.choose_partner = partner

    original_receive = C.receive_one
    def receive(state, message, trial, config):
        graph = C.plain_to_graph(message["graph"]) if isinstance(message["graph"], dict) else message["graph"]
        with receive_context(state, graph, trial, config):
            out, record = original_receive(state, message, trial, config)
        attention = sys.modules.get("attnsme")
        if attention is not None and attention.ST:
            observe_report(attention.ST["individual"]["observations"], graph)
        return out, record
    C.receive_one = receive

    original_snapshot, original_restore = C._snapshot_modules, C._restore_modules
    def snapshot():
        return original_snapshot(), snapshot_mutables()
    def restore(saved):
        original_restore(saved[0]); restore_mutables(saved[1])
    C._snapshot_modules, C._restore_modules = snapshot, restore

    def learning_fingerprint(state):
        return C.fingerprint((runtime_values(state), runtime_values(S.snapshot()), isolation_record()))
    C.learning_fingerprint = learning_fingerprint

    original_probe_predict = C.CFG["inner_predict"]
    prepared_predict = C.CFG.get("prepared_predict")
    def probe_predict(ai, state, config, rng):
        if prepared_predict is None: return original_probe_predict(ai, state, config, rng)
        A = sys.modules.get("attnsme")
        if A is not None and A.ST:
            item = CTX["probe_item"]
            if "held_out_is_door" not in item:
                raise RuntimeError("注意の一致試験には公開のドア／非ドアの指示が必要")
            A.ST.update(door_task=bool(item["held_out_is_door"]),
                scene=[r.to_dict() for r in ai.target_graph_partial.relations],
                entities={e.entity_id for e in ai.target_graph_partial.entities})
            A.ST["individual"]["observations"].structure(A.ST["scene"], A.ST["entities"])
        # 実課題の入口・第二段のpresentを使わない。予測の再生記録にも書かない。
        saved = dict(R.ST)
        R.ST.update(f=io.StringIO(), replay=None)
        try: return prepared_predict(ai, state, config, rng)
        finally: R.ST.clear(); R.ST.update(saved)
    C.CFG["inner_predict"] = probe_predict
    original_probe = C.probe
    def probe(state, items, config):
        # 個々の問いの公開指示を、予測の窓口へだけ渡す。
        class Items:
            def __iter__(self):
                for item in items:
                    CTX["probe_item"] = item
                    yield item
        try: return original_probe(state, Items(), config)
        finally: CTX.pop("probe_item", None)
    C.probe = probe

    path = Path(side_dir) / f"seed{task['seed']:03d}.collective-runtime.jsonl.gz"
    replay = task.get("sme_replay")
    if replay is not None:
        import gzip
        expected = Path(replay).with_name(Path(replay).name.replace(".sme.states.jsonl.gz", ".collective-runtime.jsonl.gz"))
        ST["replay"] = gzip.open(expected, "rt", encoding="utf-8")
    ST["stream"] = S._text_gzip(path)
    def record(phase, trial):
        from v311c_fingerprint import canonical
        row = dict(phase=phase, trial=trial, state=canonical(runtime_record()))
        if "replay" in ST and json.loads(next(ST["replay"])) != row:
            raise RuntimeError((trial, phase, "追加された注意・問いの再生が不一致"))
        ST["stream"].write(json.dumps(row, ensure_ascii=False) + "\n")
    real_predict = loop.predict
    def predict(ai, state, config, rng):
        record("pre", C.CTX["t"])
        return real_predict(ai, state, config, rng)
    loop.predict = predict
    real_record = loop._ledger_record
    def ledger_record(agent_id, trial, *args, **kw):
        result = real_record(agent_id, trial, *args, **kw)
        record("post", trial.trial)
        return result
    loop._ledger_record = ledger_record


def close():
    ST["stream"].close()
    if "replay" in ST:
        if next(ST["replay"], None) is not None:
            raise RuntimeError("追加状態の再生に読み残しがある")
        ST["replay"].close()

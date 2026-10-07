"""順序を失わない記録と、その記憶から予測・更新を再生する検査。

既存の台帳の正準形は並びを並べ直すので、引数と席の四列は別の記録で保つ。
このファイルの記録を模型の選びに読ませない。再生の旗の時だけ保存記憶を渡す。
"""
from dataclasses import fields, is_dataclass
from enum import Enum
import importlib
import json
from collections.abc import Mapping

ST: dict = {}

# 保存済みのA・C・D・λ=0の全状態で確認した模型の型だけを読む。
# モジュールの接頭辞では許可せず、型名との組を完全一致で確認する。
ALLOWED_TYPES = frozenset({
    ("abm.agent_runtime", "PendingState"),
    ("abm.definition", "Constituent"),
    ("abm.definition", "EmbedState"),
    ("abm.definition", "ExceptionAccumulator"),
    ("abm.definition", "FrequencyTable"),
    ("abm.definition", "FrozenPrice"),
    ("abm.definition", "MeritAccumulator"),
    ("abm.definition", "NamedDefinition"),
    ("abm.domains", "Abstain"),
    ("abm.domains", "AgentConfig"),
    ("abm.domains", "AgentInput"),
    ("abm.domains", "AgentOutput"),
    ("abm.domains", "CorrectionMode"),
    ("abm.domains", "EdgePrediction"),
    ("abm.domains", "Entity"),
    ("abm.domains", "Prototype"),
    ("abm.domains", "Relation"),
    ("abm.domains", "RelationGraph"),
    ("abm.domains", "RepairScope"),
    ("abm.domains", "VerbatimTrace"),
    ("smeshared", "SharedAlignment"),
    ("v38", "MeritAccumulatorV38"),
    ("v39", "AgentStateV39"),
    ("v39", "SeatRec"),
})


def encode(value):
    if isinstance(value, Enum):
        return {"tag": "enum", "module": type(value).__module__, "name": type(value).__name__, "value": value.value}
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if is_dataclass(value):
        return {"tag": "dataclass", "module": type(value).__module__, "name": type(value).__name__,
                "fields": {f.name: encode(getattr(value, f.name)) for f in fields(value)}}
    if isinstance(value, Mapping):
        return {"tag": "mapping", "items": [[encode(k), encode(v)] for k, v in value.items()]}
    if isinstance(value, (tuple, list, frozenset, set)):
        tag = type(value).__name__
        values = sorted(value, key=repr) if isinstance(value, (set, frozenset)) else value
        return {"tag": tag, "items": [encode(x) for x in values]}
    raise TypeError((type(value), "再生の記録で扱わない型"))


_SCALAR_TYPES = (type(None), str, int, float, bool)


def _fast_encode(value):
    """組み込みのスカラーだけを先に返す。同じ型・順・欄を記録する。"""
    if type(value) in _SCALAR_TYPES:
        return value
    # IntEnum・strのEnumはスカラーの派生なので、Enumを先に扱う。
    if isinstance(value, Enum):
        return {"tag": "enum", "module": type(value).__module__, "name": type(value).__name__, "value": value.value}
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if is_dataclass(value):
        return {"tag": "dataclass", "module": type(value).__module__, "name": type(value).__name__,
                "fields": {f.name: _fast_encode(getattr(value, f.name)) for f in fields(value)}}
    if isinstance(value, Mapping):
        return {"tag": "mapping", "items": [[_fast_encode(k), _fast_encode(v)] for k, v in value.items()]}
    if isinstance(value, (tuple, list, frozenset, set)):
        tag = type(value).__name__
        values = sorted(value, key=repr) if isinstance(value, (set, frozenset)) else value
        return {"tag": tag, "items": [_fast_encode(x) for x in values]}
    raise TypeError((type(value), "再生の記録で扱わない型"))


def decode(value):
    if not isinstance(value, dict):
        return value
    tag = value["tag"]
    if tag == "mapping":
        return {decode(k): decode(v) for k, v in value["items"]}
    if tag in ("tuple", "list", "set", "frozenset"):
        return {"tuple": tuple, "list": list, "set": set, "frozenset": frozenset}[tag](decode(x) for x in value["items"])
    module, name = value["module"], value["name"]
    if (module, name) not in ALLOWED_TYPES:
        raise ValueError("再生で認めていない型のモジュールと名前")
    if module == "v39" and name == "AgentStateV39":
        cls = importlib.import_module("v39")._state_class()
    elif module == "v38" and name == "MeritAccumulatorV38":
        # v38.install内で作られる既存の型を使う。模型の包みを再登録しない。
        import inspect
        import abm.loop as loop
        cls = inspect.getclosurevars(loop.update_merit).nonlocals.get(name)
        if not isinstance(cls, type) or (cls.__module__, cls.__name__) != (module, name):
            raise ValueError("再生に必要な既存v38の型が登録されていない")
    else:
        cls = getattr(importlib.import_module(module), name)
    if tag == "enum":
        return cls(value["value"])
    if tag == "dataclass":
        return cls(**{k: decode(v) for k, v in value["fields"].items()})
    raise ValueError(tag)


def install(path, *, replay=None, fast_encode=False):
    import gzip
    import abm.loop as loop
    import smeshared
    encoder = _fast_encode if fast_encode else encode
    ST.clear()
    ST.update(f=smeshared._text_gzip(path), trial=None, predictions=0, updates=0,
              replay=gzip.open(replay, "rt", encoding="utf-8") if replay is not None else None)
    real_ai = loop._agent_input

    def agent_input(trial, before):
        ST["trial"] = trial.trial
        return real_ai(trial, before)

    loop._agent_input = agent_input
    real_predict = loop.predict

    def predict(agent_input, state, config, rng):
        pre = {"kind": "pre", "trial": ST["trial"], "state": encoder(state), "input": encoder(agent_input),
               "config": encoder(config), "rng": encoder(rng.getstate())}
        expected = None
        if ST["replay"] is not None:
            saved = json.loads(next(ST["replay"]))
            if saved != pre:
                raise RuntimeError(f"再生：試行{ST['trial']}の予測前の記憶・提示・設定・乱数が違う")
            # 保存した記憶の別の実体から、本番の予測を計算する。
            state = decode(saved["state"])
            expected = json.loads(next(ST["replay"]))
        ST["f"].write(json.dumps(pre, ensure_ascii=False) + "\n")
        output, pending = real_predict(agent_input, state, config, rng)
        prediction = {"kind": "prediction", "trial": ST["trial"], "output": encoder(output), "pending": encoder(pending)}
        if expected is not None and expected != prediction:
            raise RuntimeError(f"再生：試行{ST['trial']}の対応・答え・保留状態が違う")
        ST["f"].write(json.dumps(prediction, ensure_ascii=False) + "\n")
        ST["predictions"] += 1
        return output, pending

    loop.predict = predict
    real_record = loop._ledger_record

    def ledger_record(agent_id, trial, config, output, score, coin, state, *a, **kw):
        post = {"kind": "post", "trial": trial.trial, "state": encoder(state)}
        if ST["replay"] is not None:
            saved = json.loads(next(ST["replay"]))
            if saved != post:
                raise RuntimeError(f"再生：試行{trial.trial}の学習・忘却後の記憶が違う")
        ST["f"].write(json.dumps(post, ensure_ascii=False) + "\n")
        ST["updates"] += 1
        return real_record(agent_id, trial, config, output, score, coin, state, *a, **kw)

    loop._ledger_record = ledger_record


def close():
    ST["f"].close()
    if ST["replay"] is not None:
        if next(ST["replay"], None) is not None:
            raise RuntimeError("再生：読み残した試行がある")
        ST["replay"].close()
    return {"predictions": ST["predictions"], "updates": ST["updates"], "replayed": ST["replay"] is not None}

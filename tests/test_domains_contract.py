"""凍結ゲートテスト — BUILD ORDER 第1段 (domains.py) / SPEC §3.2・§12・C2。

このファイルは**契約**であって実装ではない。実装エージェント（Codex / Fugu）は
このテストを通すように domains.py を書く。**このテストを編集して通すことは禁止**
（AGENTS.md §5）。ゆえに検査するのは挙動の近道でなく「型の構造的性質」だけ。

検査する性質:
  1. AgentInput / AgentState / AgentConfig が oracle 由来の情報を**フィールドとして持てない**
     （G_star / held_out_edge / target_type / seed_id / Feedback / OracleView）。
  2. それらの**型注釈が** OracleView / Feedback を参照しない（別名で潜り込ませる迂回の封鎖）。
  3. OracleView 側には oracle 情報が**載っている**（分離が名ばかりでない確認）。
  4. AgentInput が immutable な DTO である（frozen dataclass か NamedTuple）。

import 規約: 実装は `abm.domains` から公開される前提。パッケージ解決は repo 側で
（pyproject の pythonpath か `pip install -e .`）。
"""

import dataclasses
import pytest

domains = pytest.importorskip(
    "abm.domains",
    reason="第1段未実装。domains.py を実装すると本テストが採点を始める。",
)


# --- ヘルパ（正規化して別名・大小文字・アンダースコアの揺れを吸収） ----------------

def _norm(s: str) -> str:
    return str(s).lower().replace("_", "")


def _field_specs(cls):
    """{フィールド名: 型注釈の文字列} を返す。dataclass でも素のクラスでも動く。"""
    specs = {}
    if dataclasses.is_dataclass(cls):
        for f in dataclasses.fields(cls):
            specs[f.name] = str(f.type)
    else:
        for k, v in getattr(cls, "__annotations__", {}).items():
            specs[k] = str(v)
    return specs


def _get(name):
    obj = getattr(domains, name, None)
    if obj is None:
        pytest.fail(f"abm.domains に `{name}` が公開されていない（SPEC §3.2 の型）。")
    return obj


# oracle 由来＝エージェント側の型が決して持ってはいけないトークン（部分一致で検査）。
ORACLE_TOKENS = {"gstar", "heldoutedge", "targettype", "seedid", "feedback",
                 "oracleview", "oracle"}

# エージェント側の型が、注釈として参照してはいけない型名。
FORBIDDEN_ANNOTATION_TOKENS = {"oracleview", "feedback"}

# 各型に最低限あるべきフィールド（SPEC §3.2）。
REQUIRED = {
    "AgentInput": {"basegraph", "targetgraphpartial", "observablemask"},
    "AgentState": {"prototype", "publichistory", "rngstate"},
    "AgentConfig": {"threshold", "correctionmode"},
}


@pytest.mark.parametrize("type_name", ["AgentInput", "AgentState", "AgentConfig"])
def test_agent_side_types_have_no_oracle_fields(type_name):
    """エージェント側の型に oracle 由来フィールドが無いこと（C2・leakage の構造封鎖）。"""
    cls = _get(type_name)
    specs = _field_specs(cls)
    for fname in specs:
        nf = _norm(fname)
        hit = [t for t in ORACLE_TOKENS if t in nf]
        assert not hit, (
            f"{type_name}.{fname} が oracle 由来の名前 {hit} を含む。"
            f" エージェント側は答え（OracleView系）に到達してはならない（SPEC §3.2・C2）。"
        )


@pytest.mark.parametrize("type_name", ["AgentInput", "AgentState", "AgentConfig"])
def test_agent_side_annotations_do_not_reference_oracle_types(type_name):
    """別名フィールドに OracleView/Feedback 型を潜り込ませる迂回を封鎖（§9.2）。"""
    cls = _get(type_name)
    specs = _field_specs(cls)
    for fname, ann in specs.items():
        na = _norm(ann)
        hit = [t for t in FORBIDDEN_ANNOTATION_TOKENS if t in na]
        assert not hit, (
            f"{type_name}.{fname} の型注釈 `{ann}` が禁止型 {hit} を参照している。"
            f" 名前を変えても型で答えに到達すれば leakage（SPEC §3.2・§9.2）。"
        )


@pytest.mark.parametrize("type_name", ["AgentInput", "AgentState", "AgentConfig"])
def test_required_fields_present(type_name):
    """SPEC §3.2 が定める最低限のフィールドが存在すること。"""
    cls = _get(type_name)
    have = {_norm(k) for k in _field_specs(cls)}
    missing = {r for r in REQUIRED[type_name] if not any(r in h for h in have)}
    assert not missing, f"{type_name} に必須フィールド {missing} が無い（SPEC §3.2）。"


def test_oracleview_actually_holds_oracle_info():
    """分離が名ばかりでないこと: OracleView 側に oracle 情報が載っている。"""
    cls = _get("OracleView")
    have = {_norm(k) for k in _field_specs(cls)}
    for tok in ("gstar", "heldoutedge", "targettype", "seedid"):
        assert any(tok in h for h in have), (
            f"OracleView に `{tok}` 相当が無い。oracle 情報は AgentInput でなく"
            f" OracleView に集約されるべき（SPEC §3.2）。"
        )


def test_agent_input_is_immutable_dto():
    """AgentInput は immutable DTO（frozen dataclass か NamedTuple）であること（SPEC §3.2）。"""
    cls = _get("AgentInput")
    is_frozen_dc = (
        dataclasses.is_dataclass(cls)
        and getattr(cls, "__dataclass_params__", None) is not None
        and cls.__dataclass_params__.frozen
    )
    is_namedtuple = isinstance(cls, type) and issubclass(cls, tuple) and hasattr(cls, "_fields")
    assert is_frozen_dc or is_namedtuple, (
        "AgentInput は immutable DTO であるべき（frozen=True の dataclass か NamedTuple）。"
        " 可変だと state/closure 経由で oracle 由来値が後から混入しうる（SPEC §3.2）。"
    )

"""凍結ゲートテスト — BUILD ORDER 第3段 (roles.py) / SPEC §3.2b・§12・C11。

§12 緑判定は「型分離（domains）」だけでなく「権限分割（roles）」も型/シグネチャで
成立することを要求する。よって本テストも最初から凍結しておく。`abm.roles` が無い間は
skip し、実装されると採点を始める。**このテストを編集して通すことは禁止**（AGENTS.md §5）。

検査する性質（SPEC §3.2b の入力契約をシグネチャで静的に確認）:
  - ModelScorer / BaselinePredictor は OracleView・G_star・held_out_edge・Feedback を受けない。
  - QuadrantClassifier は target_type・seed_id・OracleView を受けない（ラベル依存分類の遮断）。
  - OracleEvaluator は agent / state（AgentState）を参照しない（事後評価器が状態へ戻さない）。

注意: これは静的検査であり「必要だが不十分」（SPEC §9.2）。本丸の防御は §3 の構造分離で、
それは test_domains_contract.py が担う。本テストは権限分割の取りこぼしを拾う補助線。
"""

import inspect
import pytest

roles = pytest.importorskip(
    "abm.roles",
    reason="第3段未実装。roles.py を実装すると本テストが採点を始める。",
)


def _norm(s: str) -> str:
    return str(s).lower().replace("_", "")


def _resolve(*candidates):
    """ロールを名前の揺れ（PascalCase / snake_case）に強く解決する。"""
    for name in candidates:
        obj = getattr(roles, name, None)
        if obj is not None:
            return name, obj
    pytest.fail(f"abm.roles に {candidates} のいずれも見つからない（SPEC §3.2b のロール）。")


def _param_specs(obj):
    """関数でもクラスでも、(正規化したパラメタ名, 正規化した注釈文字列) の列を返す。"""
    targets = []
    if inspect.isfunction(obj) or inspect.ismethod(obj):
        targets = [obj]
    elif inspect.isclass(obj):
        targets = [m for _, m in inspect.getmembers(
            obj, predicate=lambda x: inspect.isfunction(x) or inspect.ismethod(x))]
    elif callable(obj):
        targets = [obj.__call__]

    specs = []
    for t in targets:
        try:
            sig = inspect.signature(t)
        except (ValueError, TypeError):
            continue
        for pname, p in sig.parameters.items():
            if pname in ("self", "cls"):
                continue
            ann = "" if p.annotation is inspect._empty else str(p.annotation)
            specs.append((_norm(pname), _norm(ann)))
    return specs


def _assert_clean(role_name, obj, *, ann_tokens, param_names):
    """注釈に ann_tokens を含まず、パラメタ名（完全一致）が param_names に該当しないこと。"""
    for pname, ann in _param_specs(obj):
        bad_ann = [t for t in ann_tokens if t in ann]
        assert not bad_ann, (
            f"{role_name}: パラメタ `{pname}` の注釈が禁止型 {bad_ann} を参照"
            f"（SPEC §3.2b・C11）。"
        )
        assert pname not in param_names, (
            f"{role_name}: パラメタ名 `{pname}` は禁止（SPEC §3.2b・C11）。"
        )


def test_model_scorer_has_no_oracle():
    name, obj = _resolve("ModelScorer", "model_scorer")
    _assert_clean(name, obj,
                  ann_tokens={"oracleview", "gstar", "heldoutedge", "feedback"},
                  param_names={"oracleview", "gstar", "heldoutedge", "feedback"})


def test_baseline_predictor_has_no_oracle():
    name, obj = _resolve("BaselinePredictor", "baseline_predictor")
    _assert_clean(name, obj,
                  ann_tokens={"oracleview", "gstar", "heldoutedge"},
                  param_names={"oracleview", "gstar", "heldoutedge"})


def test_quadrant_classifier_has_no_labels_or_oracle():
    name, obj = _resolve("QuadrantClassifier", "quadrant_classifier")
    _assert_clean(name, obj,
                  ann_tokens={"targettype", "seedid", "oracleview"},
                  param_names={"targettype", "seedid", "oracleview"})


def test_oracle_evaluator_does_not_touch_agent_state():
    name, obj = _resolve("OracleEvaluator", "oracle_evaluator")
    # "agent" を部分一致で禁止すると AgentOutput（許容）を誤検出するので、
    # 注釈は AgentState 型のみ、パラメタ名は完全一致で agent/state を禁止する。
    _assert_clean(name, obj,
                  ann_tokens={"agentstate"},
                  param_names={"agent", "state", "agentstate"})

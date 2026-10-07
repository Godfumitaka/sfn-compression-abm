"""研究者の記録の隔離、較正の分母、正へ条件づける前の重みを小例で検査する。"""
from collections import Counter
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
import io
import json
import sys
import unittest

sys.path[:0] = [str(Path(__file__).resolve().parents[1] / "tools"), str(Path(__file__).resolve().parents[1])]
import calibration
import calibration_summary as summary
import smeonline
import v310be
import v39
from test_v39_budget import setup, definition, row, state, rec


def prepare():
    setup(price=100)
    v310be.STATS.clear()
    v310be.STATS.update(retire_candidate_evals=0, zero_release=0)
    v310be.CTX.clear()
    v39._candidates = v310be.candidates
    stream = io.StringIO()
    calibration.ST.clear()
    calibration.ST.update(f=stream, world=2, seed=1, trials=0)
    return stream


def test_no_forget_keeps_negative_seats_and_records_reference_once():
    stream = prepare()
    d = definition(row(0, "fold", ("x", "y")), row(1, v39.ERASED, ("y", "z"), alive=False))
    st = state([d], {("R_x", 0): {"fold": 1}, ("R_x", 1): {"lock": 1}},
               {("R_x", 0): rec("F", sf=3, sh=1, su=2), ("R_x", 1): rec("H", sh=2, su=1)})
    expected = v310be.candidates(st, d, 10, v39.code_lengths(st.p_hat), 1)
    v39.CFG["no_forget_exec"] = True
    out, events, before, after, ties, boundary = v39.run_conversions(st, 10)
    assert out is st and events == [] and before == after and ties == 0 and boundary is None
    values = json.loads(stream.getvalue())["candidates"]
    assert Counter((v["kind"], v["reference"]) for v in values) == Counter({("FH", False): 1, ("HU", False): 1, ("HU", True): 1})
    for candidate in expected:
        assert calibration.value_row(candidate) in values
    assert len([r for r in values if r["sign"] == "negative"]) == 2


def test_reference_empty_history_does_not_fill_lost_name_or_mutate_stats():
    stream = prepare()
    d = definition(row(0, "fold", ("x", "y")))
    st = state([d], {}, {("R_x", 0): rec("F", sh=1, su=2)})
    lengths = v39.code_lengths(st.p_hat)
    pools = {d.name: v310be.candidates(st, d, 10, lengths, 1)}
    stats = dict(v39.STATS), dict(v310be.STATS), dict(v310be.CTX)
    calibration.collect(st, 10, pools, lengths)
    assert st.slot_history == {} and st.definitions[d.name].constituents[0].alive
    assert (v39.STATS, v310be.STATS, v310be.CTX) == stats
    value = next(x for x in json.loads(stream.getvalue())["candidates"] if x["reference"])
    shadow, _ = v39._convert(st, "FH", d.name, 0, 10)
    assert shadow.slot_history[(d.name, 0)] == {}
    actual = next(c for c in v310be.candidates(shadow, shadow.definitions[d.name], 10, lengths, 1) if c[1] == "HU")
    assert value == calibration.value_row(actual, reference=True)


def test_positive_conditioning_follows_equal_world_seed_weighting():
    # 候補を単純に混ぜる、又は各世界を正の候補だけで等重みにする誤りを区別する。
    groups = {(1, 1): [{"V": 1, "kind": "FH"}] * 9 + [{"V": -1, "kind": "HU"}],
              (2, 1): [{"V": 100, "kind": "HU"}] + [{"V": 0, "kind": "FH"}] * 99}
    result = summary.summarize(groups)
    assert result["prices"]["L90"] == 1
    assert result["fractions"]["positive"] == .455
    assert result["fractions"]["negative"] == .05
    assert result["fractions"]["zero"] == .495


def test_generalized_inverse_includes_exact_cdf_boundary_and_ties():
    groups = {(1, 1): [{"V": v, "kind": "FH"} for v in (1, 1, 2, 3)]}
    assert summary.summarize(groups)["prices"] == dict(L25=1, L50=1, L75=2, L90=3)


def test_absence_of_positive_values_stops_without_fallback():
    with unittest.TestCase().assertRaisesRegex(ValueError, "正のVが無い"):
        summary.summarize({(1, 1): [{"V": 0, "kind": "FH"}]})
    with unittest.TestCase().assertRaisesRegex(ValueError, "必要な有効候補"):
        summary.summarize({(1, 1): []})


def test_seed_pair_removal_and_collapsed_price_grid():
    groups = {(w, s): [{"V": 2, "kind": k} for k in ("FH", "HU")]
              for w in (1, 2) for s in (41, 42)}
    result = summary.report(groups)
    assert len(result["leave_seed_pair_out"]) == 2
    assert result["collapsed_grid"] and result["price_grid"] == [2]
    assert not result["extend_to_41_60"]


def test_correctness_is_added_only_to_researcher_rows():
    held = SimpleNamespace(predicate="fold", arguments=("a", "b"))
    row0 = dict(prediction={"predicate": "lock", "arguments": ["a", "b"]},
                candidates=[dict(prediction={"predicate": "fold", "arguments": ["a", "b"]}, gate_passed=True)])
    output = smeonline.finish_row(row0, held, False)
    assert output["classification"] == "選び間違い"
    assert output["correct_gate_passed"] and output["original_hit"] is False
    output["candidates"][0]["gate_passed"] = False
    assert smeonline.finish_row(output, held, False)["classification"] == "区別の喪失"
    output["prediction"] = {"abstain_reason": "below_tau"}
    assert smeonline.finish_row(output, held, False)["classification"] == ""


if __name__ == "__main__":
    # この機械の標準ライブラリだけで走らせる。元の候補関数は検査後に戻す。
    original = v39._candidates
    def restore():
        v39._candidates = original
        v39.CFG.pop("no_forget_exec", None)
    suite = unittest.TestSuite(unittest.FunctionTestCase(fn, tearDown=restore)
                               for name, fn in sorted(globals().copy().items()) if name.startswith("test_"))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    raise SystemExit(not result.wasSuccessful())

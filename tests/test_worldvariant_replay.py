"""世界の旗の後づけ復元を検査する。予測の正解方向は検査しない。"""
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "tools"), str(ROOT)]

from abm.seed import load_seed
from extrap_reader import reconstruct_world, world_cue_probability


@pytest.mark.parametrize("header,flags,expected", [
    ({}, {}, None), ({}, {"world_cue": None}, None),
    ({}, {"world_cue": 0.8}, 0.8), ({}, {"world_cue": 0}, 0.0),
    ({"world_cue": True, "world_cue_p": 0.3}, {}, 0.3),
    ({"world_cue": 0.3}, {"world_cue": 0.3}, 0.3),
])
def test_recorded_probability(header, flags, expected):
    assert world_cue_probability(header, flags) == expected


def test_conflicting_probability_stops():
    with pytest.raises(ValueError, match="確率が違う"):
        world_cue_probability({"world_cue": 0.3}, {"world_cue": 0.8})


def test_plain_and_variant_replay_restore_hooks():
    import abm.world as w
    import abm.loop as loop
    import abm.ledger as ledger
    import worldvariant as variant
    seed = load_seed(ROOT / "seeds/U-011_seed_v3a2.json")
    header = dict(run_seed=1, trial_count=30, agent_ids=["agent"], arm_holdout_second_order=True)
    plain = w.generate_world(1, 30, ["agent"], seed=seed, holdout_include_second_order=True)
    hooks = w.generate_trial, loop._ledger_record, ledger.Ledger.append
    saved = [dict(d) for d in (variant.INFO, variant.CFG, variant.STATS)]
    for probability in (0.8, 0.3, 0.8):
        replay = reconstruct_world(header, {"world_cue": probability}, seed)
        assert [dict(d) for d in (variant.INFO, variant.CFG, variant.STATS)] == saved
        expected = [variant.variant_trial(hooks[0], 1, t, ["agent"], seed=seed,
                    holdout_include_second_order=True, p_a=probability) for t in range(30)]
        # 手で同じ包みを適用した完全な場面、提示、伏せ辺との一致を検査する。
        assert list(replay.trials) == expected
        for d, old in zip((variant.INFO, variant.CFG, variant.STATS), saved):
            d.clear()
            d.update(old)
        assert (w.generate_trial, loop._ledger_record, ledger.Ledger.append) == hooks
        assert reconstruct_world(header, {}, seed) == plain


def test_restoration_when_generation_fails(monkeypatch):
    import abm.world as w
    import abm.loop as loop
    import abm.ledger as ledger
    import worldvariant as variant
    hooks = w.generate_trial, loop._ledger_record, ledger.Ledger.append
    saved = [dict(d) for d in (variant.INFO, variant.CFG, variant.STATS)]
    def fail(*args, **kwargs):
        raise RuntimeError("検査用の失敗")
    monkeypatch.setattr(w, "generate_world", fail)
    with pytest.raises(RuntimeError, match="検査用の失敗"):
        reconstruct_world(dict(run_seed=1, trial_count=30), {"world_cue": 0.8}, None)
    assert (w.generate_trial, loop._ledger_record, ledger.Ledger.append) == hooks
    assert [dict(d) for d in (variant.INFO, variant.CFG, variant.STATS)] == saved

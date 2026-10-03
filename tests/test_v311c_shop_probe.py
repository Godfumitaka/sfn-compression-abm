"""二集団の試験を作る段の構造検査（学習の走行はしない）。"""
from collections import Counter
from pathlib import Path
from random import Random
from types import SimpleNamespace

import pytest
import test_v311c as C
import v311c
import shopworld
from abm.domains import Abstain

SEED = Path(__file__).resolve().parents[1] / "tools/shop/U-011_seed_shop.json"


@pytest.mark.parametrize("run", (1, 2, 3))
def test_shop_fixed_twenty(run):
    old_ids = dict(shopworld.IDS)
    items = v311c.probe_shop_items(SEED, run, False, world=2)
    assert items == v311c.probe_shop_items(SEED, run, False, world=2)
    assert len(items) == 20
    assert shopworld.IDS == old_ids
    counts = Counter((it["shop_type"], it["shop_cue"], it["held_out_is_door"]) for it in items)
    for typ in ("甲", "乙"):
        for cue in ("n", "e"):
            assert counts[typ, cue, True] == 3
            assert counts[typ, cue, False] == 2
            trials = [it["trial"] for it in items if (it["shop_type"], it["shop_cue"]) == (typ, cue)]
            assert trials == sorted(trials)
    for it in items:
        names = {r[1] for r in it["scene"]["rels"]}
        assert ("sig_e" if it["shop_cue"] == "e" else "sig_n") in names
        assert "attach" in names


def test_shortage_does_not_redraw():
    with pytest.raises(ValueError, match="不足"):
        v311c.probe_shop_items(SEED, 1, False, world=2, exc=0)


def test_probe_keeps_state_and_main_rng():
    C.setup()
    state = C.state()
    rng = Random(123)
    before = repr(state), rng.getstate()
    v311c.CFG.update(audit=True, inner_predict=lambda ai, st, cfg, r: (SimpleNamespace(prediction=Abstain("probe")), None))
    v311c.probe(state, v311c.probe_shop_items(SEED, 3, False, world=2), SimpleNamespace())
    assert before == (repr(state), rng.getstate())

"""飾りの操作の構造だけを検査する。正誤や期待した誤答方向は検査しない。"""
from pathlib import Path
from io import StringIO
import json
import subprocess
import sys
import types
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "tools")]

from abm.seed import load_seed
from abm.world import generate_trial, opaque_id
import shopworld as sw

BASE = "3380344add7f85ce2c3608656de5805995dcf971"
original = types.ModuleType("baseline_shopworld")
exec(compile(subprocess.check_output(["git", "-C", str(ROOT), "show", f"{BASE}:tools/shopworld.py"]),
             "baseline_shopworld.py", "exec"), original.__dict__)
SEED = load_seed(ROOT / "tools/shop/U-011_seed_shop.json")


def scene(trial, level, world=2, cue="n"):
    base = generate_trial(1, trial, ("agent",), seed=SEED)
    with patch.dict(sw.CFG, {"deco": level}, clear=True):
        return sw.build(base, 1, trial, cue=cue, world=world)


def test_off_and_current_match_baseline():
    for trial in (0, 1, 5, 8, 18):
        base = generate_trial(1, trial, ("agent",), seed=SEED)
        for world in (1, 2):
            for cue in ("n", "e"):
                expected = original.build(base, 1, trial, world=world, cue=cue)
                for level in (None, "current"):
                    assert scene(trial, level, world, cue) == expected


def test_skeleton_removes_only_glue_and_reroutes_only_glue_targets():
    for trial in range(64):
        current, _ = scene(trial, None)
        out, info = scene(trial, "skeleton")
        deco = info["deco"]
        glue = {opaque_id(1, trial, f"relation:glue:{i}") for i in range(3)}
        removed = {r.relation_id for r in current.G_star.relations if r.relation_id in glue}
        assert {r["id"] for r in deco["removed"]} == removed
        assert out.G_star.relations == tuple(r for r in current.G_star.relations if r.relation_id not in glue)
        assert out.G_star.entities == current.G_star.entities
        assert out.u_coins == current.u_coins
        assert not deco["added"]
        door = opaque_id(1, trial, "relation:tree:0.0.0")
        if current.held_out_edge.relation_id in glue:
            entities = {e.entity_id for e in current.G_star.entities}
            excluded = {door, opaque_id(1, trial, "relation:role_unary"), opaque_id(1, trial, "relation:shop:sig")}
            candidates = {r.relation_id for r in out.G_star.relations if r.relation_id not in excluded
                          and all(a in entities for a in r.arguments)}
            assert out.held_out_edge.relation_id in candidates
            assert len(candidates) in (8, 9)
            assert deco["rerouted"]
        else:
            assert out.held_out_edge == current.held_out_edge
            assert not deco["rerouted"]
        assert out.held_out_edge.relation_id not in removed
        assert info["held_out_is_door"] == (out.held_out_edge.relation_id == door)


def test_plus_levels_share_first_four_relations_and_keep_original_targets():
    for trial in (0, 1, 5, 8, 18):
        current, _ = scene(trial, None)
        four, fi = scene(trial, "plus4")
        eight, ei = scene(trial, "plus8")
        assert four.G_star.relations[:-4] == current.G_star.relations
        assert eight.G_star.relations[:-8] == current.G_star.relations
        assert four.G_star.relations[-4:] == eight.G_star.relations[-8:-4]
        assert fi["deco"]["added"] == ei["deco"]["added"][:4]
        assert four.held_out_edge == eight.held_out_edge == current.held_out_edge
        assert four.G_star.entities == eight.G_star.entities == current.G_star.entities
        assert len({r.predicate for r in eight.G_star.relations[-8:]}) == 8
        for r in eight.G_star.relations[-8:]:
            assert r.predicate in sw.DECO_PREDICATES and len(r.arguments) == 1
            assert r.arguments[0] in {e.entity_id for e in current.G_star.entities}
            assert r.relation_id != eight.held_out_edge.relation_id


def test_dictionary_appends_full_pool_only_for_plus_levels():
    start = {p: i for i, p in enumerate(SEED.data["marginal"])}
    for level in (None, "current", "skeleton", "plus4", "plus8"):
        v39 = types.SimpleNamespace(CFG={"dict_index": dict(start)})
        with patch.dict(sys.modules, {"v39": v39}), patch.dict(sw.CFG, {"deco": level}, clear=True):
            sw.extend_dictionary()
        idx = v39.CFG["dict_index"]
        assert all(idx[p] == i for p, i in start.items())
        assert v39.CFG["D"] == (92 if level in ("plus4", "plus8") else 80)
        assert all((p in idx) == (level in ("plus4", "plus8")) for p in sw.DECO_PREDICATES)


def test_research_entity_counts_follow_visible_reachability_without_changing_scene():
    for level in sw.DECO_LEVELS:
        sink = StringIO()
        with patch.dict(sw.CFG, {"world": 1, "exc": 0.2, "deco": level}, clear=True), \
             patch.dict(sw.CTX, {"entities_f": sink, "deco_level": level}, clear=True):
            out = sw.shop_trial(generate_trial, 1, 4, ("agent",), seed=SEED)
        row = json.loads(sink.getvalue())
        assert row["level"] == level and row["trial"] == 4
        assert row["run_seed"] == 1 and row["graph_id"] == out.G_star.graph_id
        assert row["full_entity_count"] == len(out.G_star.entities) == 3
        assert row["public_entity_count"] == len(out.target_graph_partial.entities)
        assert row["public_entity_count"] == (2 if level == "skeleton" else 3)
        if level == "current":
            cue = "e" if sw.cue_rng(1, 4).random() < 0.2 else "n"
            assert (out, sw.INFO[out.G_star.graph_id]) == original.build(
                generate_trial(1, 4, ("agent",), seed=SEED), 1, 4, world=1, cue=cue)

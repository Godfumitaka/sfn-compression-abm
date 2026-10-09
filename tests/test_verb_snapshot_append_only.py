"""指示17の構造検査。世界・学習模型を起動しない。"""
import ast
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import probeworld as pw
from verb_snapshot import AppendOnlyDict, AppendOnlyMark, AppendOnlyViolation, install


@pytest.fixture
def world(monkeypatch):
    w = SimpleNamespace(INFO={"a": {"past": True, "name": "V01"}}, IDS={"n": "name"}, STATS={"trials": 1})
    other = SimpleNamespace(INFO={"x": {"n": 1}}, IDS={"x": "link"})
    monkeypatch.setitem(sys.modules, "verbworld", w)
    monkeypatch.setitem(sys.modules, "other_snapshot", other)
    monkeypatch.setattr(pw, "SNAP_MODULES", ("verbworld", "other_snapshot"))
    monkeypatch.setattr(pw, "SNAP_ATTRS", ("INFO", "IDS", "STATS"))
    return w, other


def old_snapshot(world):
    return [(d, {k: dict(v) if isinstance(v, dict) else list(v) if isinstance(v, list) else v
                 for k, v in d.items()})
            for w in world for a in pw.SNAP_ATTRS if isinstance(d := getattr(w, a, None), dict)]


def test_off_uses_original_full_copies(world):
    w, _ = world
    expected = old_snapshot(world)
    actual = pw._snapshot_modules()
    assert actual == expected
    assert all(type(saved) is dict for _, saved in actual)
    w.INFO["a"]["name"] = "changed"
    w.INFO["b"] = {"name": "new"}
    del w.IDS["n"]
    pw._restore_modules(actual)
    assert w.INFO == {"a": {"past": True, "name": "V01"}} and w.IDS == {"n": "name"}


def test_on_restores_content_and_order_like_original_copy(world):
    w, other = world
    original = old_snapshot(world)
    stats = w.STATS
    install(w)
    snap = pw._snapshot_modules()
    assert [type(saved) for _, saved in snap] == [AppendOnlyMark, AppendOnlyMark, dict, dict, dict]
    assert w.STATS is stats and type(other.INFO) is dict and type(other.IDS) is dict
    w.INFO["b"] = {"past": False, "name": "V02"}
    w.IDS.update({"b1": "name", "b2": "link"})
    w.STATS["trials"] += 1
    other.INFO["x"]["n"] = 7
    pw._restore_modules(snap)
    for current, (_, saved) in zip((w.INFO, w.IDS, w.STATS, other.INFO, other.IDS), original):
        assert list(current.items()) == list(saved.items())


@pytest.mark.parametrize("action", [
    lambda d: d.__setitem__("a", {"name": "changed"}),
    lambda d: d.__delitem__("a"),
    lambda d: d.clear(), lambda d: d.pop("a"), lambda d: d.popitem(),
    lambda d: d.update({"new": {"name": "new"}, "a": {"name": "changed"}}),
    lambda d: d.__ior__({"a": {"name": "changed"}}),
])
def test_existing_info_change_or_delete_stops_before_mutation(world, action):
    w, _ = world
    install(w)
    snap = pw._snapshot_modules()
    with pytest.raises(AppendOnlyViolation):
        action(w.INFO)
    assert list(w.INFO.items()) == [("a", {"past": True, "name": "V01"})]
    pw._restore_modules(snap)


@pytest.mark.parametrize("action", [
    lambda d: d.__setitem__("name", "changed"), lambda d: d.__delitem__("name"),
    lambda d: d.clear(), lambda d: d.pop("name"), lambda d: d.popitem(),
    lambda d: d.update(name="changed"), lambda d: d.__ior__({"name": "changed"}),
    lambda d: d.setdefault("new", "new"),
])
def test_existing_info_value_change_stops(world, action):
    w, _ = world
    install(w)
    snap = pw._snapshot_modules()
    with pytest.raises(AppendOnlyViolation):
        action(w.INFO["a"])
    assert w.INFO["a"] == {"past": True, "name": "V01"}
    pw._restore_modules(snap)


@pytest.mark.parametrize("action", [lambda d: d.__setitem__("n", "link"), lambda d: d.__delitem__("n")])
def test_ids_change_or_delete_stops(world, action):
    w, _ = world
    install(w)
    snap = pw._snapshot_modules()
    with pytest.raises(AppendOnlyViolation):
        action(w.IDS)
    assert w.IDS == {"n": "name"}
    pw._restore_modules(snap)


def test_nested_windows_restore_last_added_items_in_order(world):
    w, _ = world
    install(w)
    outer = pw._snapshot_modules()
    w.INFO["b"] = {"name": "V02"}
    inner = pw._snapshot_modules()
    w.INFO["c"] = {"name": "V03"}
    with pytest.raises(AppendOnlyViolation):
        w.INFO["b"]["name"] = "changed"
    pw._restore_modules(inner)
    assert list(w.INFO) == ["a", "b"]
    pw._restore_modules(outer)
    assert list(w.INFO) == ["a"]
    w.INFO["a"]["name"] = "outside"
    assert w.INFO["a"]["name"] == "outside"


def test_out_of_order_restore_stops():
    d = AppendOnlyDict({"a": "name"})
    a, b = d.snapshot(), d.snapshot()
    with pytest.raises(AppendOnlyViolation):
        d.restore(a)
    d.restore(b)
    d.restore(a)


def test_mutable_info_child_is_not_silently_allowed():
    with pytest.raises(AppendOnlyViolation):
        AppendOnlyDict({"a": {"nested": []}}, info=True)


def test_snapshot_holds_only_length_without_iterating_entries():
    class NoItems(AppendOnlyDict):
        def items(self):
            raise AssertionError("控えで全項目を読まない")
    d = NoItems({"a": "name"})
    mark = d.snapshot()
    assert mark.length == 1 and mark.owner is d
    d["b"] = "link"
    d.restore(mark)
    assert list(d) == ["a"]


def test_install_is_not_repeated(world):
    w, _ = world
    install(w)
    with pytest.raises(AppendOnlyViolation):
        install(w)


def test_install_preserves_existing_snapshot_membership(world, monkeypatch):
    w, _ = world
    monkeypatch.setattr(pw, "SNAP_MODULES", ("other_snapshot",))
    modules, attrs = pw.SNAP_MODULES, pw.SNAP_ATTRS
    install(w)
    assert pw.SNAP_MODULES is modules and pw.SNAP_ATTRS is attrs
    assert all(not isinstance(saved, AppendOnlyMark) for _, saved in pw._snapshot_modules())


def test_flag_default_off_and_on_is_explicit():
    tree = ast.parse((Path(__file__).resolve().parents[1] / "tools/v3_run.py").read_text())
    calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call) and n.args
             and isinstance(n.args[0], ast.Constant) and n.args[0].value == "--verb-snap-append-only"]
    assert len(calls) == 1
    options = {k.arg: ast.literal_eval(k.value) for k in calls[0].keywords}
    assert options["default"] == "off" and options["choices"] == ("off", "on")

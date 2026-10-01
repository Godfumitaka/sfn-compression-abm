"""履歴キーの読みを再利用しても、試行ごとの名前と回数を取り違えないこと。"""
import ast
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "tools"), str(ROOT)]
from roletarget_recompute import _restore_hist, _HISTORY_KEYS


def reference(hist, name):
    return {ast.literal_eval(k): dict(v) if isinstance(v, dict) else frozenset(v)
            for k, v in hist.items() if ast.literal_eval(k)[0] == name}


def test_keys_reused_contents_refreshed_and_copied():
    _HISTORY_KEYS.clear()
    name = "R_'quoted\\name"
    hist = {str((name, 2)): {"hold": 1}, str(("R_other", 2)): {"pull": 5},
            str((name, 7)): ["wrap", "hold"]}
    assert _restore_hist(hist, name) == reference(hist, name)
    size = len(_HISTORY_KEYS)
    hist[str((name, 2))]["hold"] = 9
    hist[str((name, 7))] = ["break"]
    replay = _restore_hist(hist, name)
    assert replay == reference(hist, name)
    assert len(_HISTORY_KEYS) == size
    replay[(name, 2)]["hold"] = 100
    assert hist[str((name, 2))]["hold"] == 9

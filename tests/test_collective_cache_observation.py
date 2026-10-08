"""指示9。各体のP10観測先の分離と、既存単独の場所を検査する。"""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from v3_run import _cache_prune_path


def test_collective_eight_paths_are_distinct_and_under_real_output(tmp_path):
    root = tmp_path / 'output'
    paths = [_cache_prune_path(dict(v311c={'agent':i},cell='one',seed=1+1000*i),root)
             for i in range(8)]
    assert len(set(paths)) == 8
    assert all(p.parent == root/'cache_prune/one' for p in paths)
    assert all(not p.exists() for p in paths)
    other = _cache_prune_path(dict(v311c={'agent':0},cell='one',seed=1),tmp_path/'other')
    assert other not in paths


def test_single_process_keeps_upstream_observation_path(tmp_path):
    assert _cache_prune_path({'seed':1},tmp_path/'output') == tmp_path/'p10_cache_guard.jsonl.gz'

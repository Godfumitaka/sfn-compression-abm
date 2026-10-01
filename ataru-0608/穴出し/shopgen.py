"""お店の世界の場面を、走行と同じ作り方で作り直す（読むだけの道具。走行はしない）。
tools/shopworld.py を入れてから abm.world.generate_trial を呼ぶ（tools/v3_run.py と同じ順）。種ファイルは tools/shop/U-011_seed_shop.json。"""
import os
import sys

REPO = os.path.expanduser("~/sfn/sfn-compression-abm")
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.join(REPO, "tools"))
SC = "/tmp/claude-1000/-home-tatsu-sfn/46945c76-63c2-47d5-81fa-9b12440cb938/scratchpad"


def setup(world):
    import abm.seed as seedmod
    import shopworld
    fo = open(os.path.join(SC, "shopgen_fo.jsonl"), "w")
    shopworld.install(fo, world=int(world), exc=0.2, keep_cue=False, side_path=os.path.join(SC, "shopgen_side.jsonl"))
    seed = seedmod.load_seed(os.path.join(REPO, "tools/shop/U-011_seed_shop.json"))
    return seed


def trials(run_seed, n, seed, hos=False):
    import abm.world as w
    for t in range(n):
        yield t, w.generate_trial(run_seed, t, ("agent",), seed=seed, holdout_include_second_order=hos)

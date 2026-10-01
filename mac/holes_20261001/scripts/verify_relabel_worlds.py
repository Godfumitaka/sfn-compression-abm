"""付け替えた入力を元の名へ戻し、公開入力・正解・乱数の一致を調べる。"""
import importlib.util
import json
import pathlib
import sys
ROOT = pathlib.Path(__file__).resolve().parent
SOURCE = ROOT / 'source'
sys.path[:0] = [str(SOURCE / 'tools'), str(SOURCE)]
spec = importlib.util.spec_from_file_location('relabel', SOURCE / 'tools/holes_20261001/relabel_shop_run.py')
relabel = importlib.util.module_from_spec(spec)
spec.loader.exec_module(relabel)
import abm.world as w
from abm.seed import load_seed
import shopworld

SALT = 'codex-hole2-20261001'
folder = ROOT / 'input_gate'
folder.mkdir(exist_ok=True)
old_seed = load_seed(SOURCE / 'tools/shop/U-011_seed_shop.json')
mp = relabel.prepare(SOURCE / 'tools/shop/U-011_seed_shop.json', folder / 'seed_relabeled.json', SALT)
new_seed = load_seed(folder / 'seed_relabeled.json')
assert list(new_seed.data['marginal']) == [mp[p] for p in old_seed.data['marginal']]
originals = {}
for seed in range(1, 21):
    base = w.generate_world(seed, 1740, ('agent',), seed=old_seed)
    for world in (1, 2):
        originals[world, seed] = tuple(shopworld.build(t, seed, t.trial, cue='e' if shopworld.cue_rng(seed, t.trial).random() < 0.2 else 'n', world=world)[0] for t in base.trials)
ids = relabel.install_names(mp, SALT)
checked = 0
for seed in range(1, 21):
    base = w.generate_world(seed, 1740, ('agent',), seed=new_seed)
    for world in (1, 2):
        for old, t in zip(originals[world, seed], base.trials, strict=True):
            new = shopworld.build(t, seed, t.trial, cue='e' if shopworld.cue_rng(seed, t.trial).random() < 0.2 else 'n', world=world)[0]
            undone = relabel.undo_trial(new, {v:k for k,v in mp.items()}, {v:k for k,v in ids.items()})
            assert undone == old, (world, seed, t.trial)
            checked += 1
    print(f'入力の逆写し 種{seed} 世界1・2 各1740試行一致', flush=True)
result = dict(salt=SALT, trials=checked, seeds=list(range(1,21)), worlds=[1,2], predicates=mp, entity_count=len(ids),
              marginal_order_unchanged=True, relation_ids_unchanged=True, inputs_truth_coins_equal=True)
(folder / 'checks.json').write_text(json.dumps(result, ensure_ascii=False, indent=1) + '\n')
print(json.dumps(dict(trials=checked, mismatches=0), ensure_ascii=False))

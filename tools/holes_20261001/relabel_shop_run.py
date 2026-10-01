"""候補2の計測。述語と物の名だけを付け替え、本番の処理は直さない。"""
from __future__ import annotations
import argparse
import dataclasses
import json
import sys
from hashlib import blake2b, sha256
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(SOURCE / 'tools'), str(SOURCE)]
from tools.histrole_checks.relabel_run import Inline, SKIP


def prepare(seed_source, destination, salt):
    from abm.seed import seed_hash
    import shopworld
    raw = json.loads(Path(seed_source).read_text())
    names = list(raw['marginal'])
    names += [p for p in shopworld.NEW_PREDICATES if p not in names]
    mapping = {p: 'p' + sha256(f'{salt}\x1f{p}'.encode()).hexdigest()[:12] for p in names}
    assert len(set(mapping.values())) == len(mapping)
    def rename(value):
        if isinstance(value, dict):
            return {mapping.get(k, k): rename(v) for k, v in value.items()}
        if isinstance(value, list):
            return [rename(v) for v in value]
        return mapping.get(value, value) if isinstance(value, str) else value
    relabeled = {k: v if k in SKIP else rename(v) for k, v in raw.items()}
    relabeled['sha256'] = seed_hash(relabeled)
    Path(destination).write_text(json.dumps(relabeled, ensure_ascii=False, indent=1) + '\n')
    return mapping


def install_names(mapping, salt):
    import abm.world as w
    import shopworld
    original = w.opaque_id
    ids = {}
    inverse = {}
    def opaque_id(run_seed, trial_index, role_name):
        old = original(run_seed, trial_index, role_name)
        if not role_name.startswith('entity:'):
            return old
        new = blake2b(f'{salt}\x1fentity\x1f{old}'.encode(), digest_size=8).hexdigest()
        assert new not in inverse or inverse[new] == old
        ids[old] = new
        inverse[new] = old
        return new
    w.opaque_id = opaque_id
    for name in ('SIG_N', 'SIG_E', 'ATTACH', 'X', 'Y'):
        setattr(shopworld, name, mapping[getattr(shopworld, name)])
    shopworld.NEW_PREDICATES = tuple(mapping[p] for p in shopworld.NEW_PREDICATES)
    return ids


def undo_trial(trial, predicate_inverse, entity_inverse):
    def relation(r):
        return dataclasses.replace(r, predicate=predicate_inverse.get(r.predicate, r.predicate),
                                   arguments=tuple(entity_inverse.get(a, a) for a in r.arguments))
    def graph(g):
        return dataclasses.replace(g, entities=tuple(dataclasses.replace(e, entity_id=entity_inverse.get(e.entity_id, e.entity_id)) for e in g.entities),
                                   relations=tuple(relation(r) for r in g.relations))
    return dataclasses.replace(trial, G_star=graph(trial.G_star), target_graph_partial=graph(trial.target_graph_partial),
                               held_out_edge=relation(trial.held_out_edge))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('salt')
    parser.add_argument('config')
    parser.add_argument('output')
    parser.add_argument('rest', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    assert args.rest[0] == '--'
    output = Path(args.output).resolve()
    assert output.is_relative_to(SOURCE.parent) and not output.exists()
    destination = output / 'relabel'
    destination.mkdir(parents=True)
    config = json.loads((SOURCE / args.config).read_text())
    mapping = prepare(SOURCE / config['seed_file'], destination / 'seed_relabeled.json', args.salt)
    config['seed_file'] = str(destination / 'seed_relabeled.json')
    (destination / 'config_relabeled.json').write_text(json.dumps(config, ensure_ascii=False, indent=1) + '\n')
    ids = install_names(mapping, args.salt)
    import v3_run
    v3_run.ProcessPoolExecutor = Inline
    sys.argv = ['tools/v3_run.py', str(destination / 'config_relabeled.json'), str(output), *args.rest[1:]]
    try:
        v3_run.main()
    finally:
        (destination / 'map.json').write_text(json.dumps(dict(salt=args.salt, predicates=mapping, entities=ids,
                                                           relation_ids='unchanged'), ensure_ascii=False, indent=1) + '\n')


if __name__ == '__main__':
    main()

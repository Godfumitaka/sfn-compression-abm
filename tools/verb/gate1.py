"""段1：抽選・場面・辞書・既定Uの前提だけを調べる。模型の学習走行はしない。"""
import argparse
import json
import sys
from collections import Counter
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "tools"), str(ROOT)]
import verbworld as vw  # noqa: E402
import probeworld as pw  # noqa: E402
import abm.world as w  # noqa: E402
from abm.seed import load_seed, higher_order_predicates  # noqa: E402


def inspect_default_u(tr, info, draws):
    """入力分布から作った検査用の頻度表。模型の学習結果ではない。"""
    import v39
    from abm.definition import Constituent, FrequencyTable, FrozenPrice, NamedDefinition
    from abm.filling import _predicate_has_signature, slot_signature
    from abm.domains import RelationGraph
    from abm.abstraction import _structural_relation_ids
    n = sum(draws.values())
    # 全入力で変わらない骨組みを n 回、名前と過去形は抽選の出現数だけ。
    counts = Counter({r.predicate: 0 for r in tr.G_star.relations})
    for r in tr.G_star.relations:
        if r.relation_id not in (info["past_id"], info["name_id"]):
            counts[r.predicate] += n
    for item in vw.training_items():
        counts[item.past] += draws[item.name]
        counts[item.name] += draws[item.name]
    ph = FrequencyTable(dict(counts), sum(counts.values()), .1, frozenset(p for p, c in counts.items() if c > 0))
    price = FrozenPrice(1.0, 0, 0.0, 3)
    structural_ids = _structural_relation_ids(tr.G_star)
    structural = [r for r in tr.G_star.relations if r.relation_id in structural_ids]
    rows = tuple(Constituent(i, 0, replace(r, predicate=v39.ERASED) if r.relation_id == info["past_id"] else r,
                             price, r.relation_id != info["past_id"]) for i, r in enumerate(structural))
    d = NamedDefinition("R_inspection", rows, len(rows) - 1, 0)
    row = next(c for c in rows if c.relation.relation_id == info["past_id"])
    scene = pw._partial(tr.G_star, info["past_id"])
    dg = RelationGraph("definition", relations=tuple(c.relation for c in rows))
    hop = higher_order_predicates(load_seed(ROOT / "tools/verb/U-011_seed_verb.json")) | {"attach"}
    sig = slot_signature(row.relation, dg)
    pool = v39._order_pool(frozenset(p for p in ph.alive_vocab if _predicate_has_signature(p, sig, scene, dg)), d, row, hop)
    old = dict(v39.CFG)
    try:
        v39.CFG["u_abstain"] = False
        answer, reason = v39.u_answer(d, row, scene, ph, hop)
    finally:
        v39.CFG.clear()
        v39.CFG.update(old)
    maximum = max(counts[p] for p in pool)
    return dict(table="固定場面の完全入力を抽選分布で重ねた検査用。学習はしていない", answer=answer, reason=reason,
                signature=sig, regular_count=counts["REG"], largest_irregular_count=max(counts[f"IRR_{k}"] for k in range(1, 9)),
                maxima={p: counts[p] for p in sorted(pool) if counts[p] == maximum},
                binary_structural_counts={p: counts[p] for p in sorted(pool) if p in ("push", "carry", "lift", "steer", "reach")},
                REG_is_global_max=counts["REG"] == maximum)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("output")
    ap.add_argument("--draws", type=int, default=100000)
    args = ap.parse_args()
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    sd = load_seed(ROOT / "tools/verb/U-011_seed_verb.json")
    original = load_seed(ROOT / "tools/shop/U-011_seed_shop.json")
    assert sd.data["motif_structure"]["M1"] == original.data["motif_structure"]["M1"]
    items = vw.training_items()
    counts = Counter(vw.draw_verb(1, t, items).name for t in range(args.draws))
    rows = [dict(verb_name=v.name, verb_class=v.verb_class, correct_past=v.past, expected=v.probability,
                 count=counts[v.name], observed=counts[v.name] / args.draws,
                 deviation_pp=100 * (counts[v.name] / args.draws - v.probability)) for v in items]
    assert all(abs(row["deviation_pp"]) <= .5 for row in rows)
    irregular = sum(counts[v.name] for v in items if v.verb_class == "irregular") / args.draws
    assert abs(irregular - .70) <= .005
    assert not set(counts) & set(vw.NOVEL_NAMES)
    assert max(v.probability for v in items if v.verb_class == "irregular") < .30
    base = w.generate_trial(1, 0, ("agent",), seed=sd)
    samples = []
    tr = info = None
    for item in (items[0], items[32], vw.Verb("V41", "novel", "REG", 0)):
        tr, info = vw.build(base, 1, 0, verb=item)
        paths, _ = pw._paths(sd.data, 1, 0, "M1")
        aliases = {r[0]: path for path, r in paths.items()}
        aliases.update({w.opaque_id(1, 0, "entity:a"): "a", w.opaque_id(1, 0, "entity:b"): "b",
                        info["name_id"]: "verb_name", info["link_id"]: "verb_link"})
        sample = dict(verb_name=item.name, verb_class=item.verb_class, nominal_past=item.past,
                      novel_truth_is_placeholder=item.verb_class == "novel", past_path="0.0.0",
                      relations=[dict(seat=aliases.get(r.relation_id, r.relation_id), predicate=r.predicate,
                                      arguments=[aliases.get(a, a) for a in r.arguments]) for r in tr.G_star.relations])
        samples.append(sample)
        print(json.dumps(sample, ensure_ascii=False))
    # 学習なしで、伏せ辺と乱数の保存を種1〜20・各100場面で調べる。
    past_queries = 0
    for rs in range(1, 21):
        for t in range(100):
            old = w.generate_trial(rs, t, ("agent",), seed=sd)
            new, ni = vw.build(old, rs, t, verb=vw.draw_verb(rs, t, items))
            assert old.held_out_edge.relation_id == new.held_out_edge.relation_id
            assert old.u_coins == new.u_coins
            assert len(new.G_star.relations) == len(old.G_star.relations) + 2
            past_queries += ni["held_out_is_past"]
    regular_tr, regular_info = vw.build(base, 1, 0, verb=items[0])
    result = dict(seed=1, draws=args.draws, rows=rows, irregular_expected=.70, irregular_observed=irregular,
                  max_abs_deviation_pp=max(abs(row["deviation_pp"]) for row in rows),
                  most_frequent_irregular_expected=items[32].probability,
                  most_frequent_irregular_observed=counts["V33"] / args.draws, regular_expected=.30,
                  every_irregular_less_than_REG=True, sampled_seeds=list(range(1, 21)),
                  holdout_checks=2000, held_out_is_past=past_queries,
                  past_probability_default=w.one_minus_h(sd.data["pi_A"]["M1"], len(w._first_order_paths(sd.data, "M1"))),
                  default_U_check=inspect_default_u(regular_tr, regular_info, counts))
    # one_minus_h は「見える率」なので、過去形を問う既定率に戻す。
    result["past_probability_default"] = 1 - result["past_probability_default"]
    (out / "draws.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    (out / "samples.json").write_text(json.dumps(samples, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({key: value for key, value in result.items() if key != "rows"}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

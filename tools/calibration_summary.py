"""世界×種を正への条件づけ前に等重みにする、λ較正の集計。走行は始めない。"""
from __future__ import annotations

from collections import Counter
from fractions import Fraction
from pathlib import Path
import argparse
import gzip
import json
import math

QUANTILES = {"L25": Fraction(1, 4), "L50": Fraction(1, 2),
             "L75": Fraction(3, 4), "L90": Fraction(9, 10)}


def summarize(groups, *, kind=None):
    if not groups or any(not rows for rows in groups.values()):
        raise ValueError("世界×種の必要な有効候補が無い")
    weighted = []
    counts = Counter()
    for rows in groups.values():
        weight = Fraction(1, len(groups) * len(rows))
        for row in rows:
            if kind is not None and row["kind"] != kind:
                continue
            value = row["V"]
            if not math.isfinite(value):
                raise ValueError("較正のVが有限でない")
            weighted.append((value, weight))
            counts["positive" if value > 0 else "negative" if value < 0 else "zero"] += 1
    mass = sum((w for _, w in weighted), Fraction())
    signs = {name: sum((w for v, w in weighted if (v > 0 if name == "positive" else
                                                v < 0 if name == "negative" else v == 0)), Fraction())
             for name in ("negative", "zero", "positive")}
    positive = sorted((v, w) for v, w in weighted if v > 0)
    if not positive:
        raise ValueError("正のVが無い：" + str(kind))
    prices = {}
    for name, quantile in QUANTILES.items():
        cumulative = Fraction()
        limit = quantile * signs["positive"]
        for value, weight in positive:
            cumulative += weight
            if cumulative >= limit:
                prices[name] = value
                break
    return dict(counts=dict(counts), fractions={k: float(v / mass) for k, v in signs.items()},
                positive_mass_before_conditioning=float(signs["positive"]), prices=prices,
                method="weighted-generalized-inverse", weighting="equal-world-seed-before-positive")


def report(groups, *, expanded=False):
    seeds = sorted({s for _, s in groups})
    if set(groups) != {(w, s) for w in (1, 2) for s in seeds}:
        raise ValueError("各種の両世界の組が揃っていない")
    main = summarize(groups)
    checks = []
    unstable = False
    for seed in seeds:
        subset = {key: rows for key, rows in groups.items() if key[1] != seed}
        omitted = summarize(subset)
        ratios = {name: omitted["prices"][name] / main["prices"][name]
                  for name in ("L25", "L50", "L90")}
        outside = any(v > 1.25 or v < 1 / 1.25 for v in ratios.values())
        unstable |= outside
        checks.append(dict(omitted_seed=seed, prices=omitted["prices"], ratios=ratios, outside=outside))
    grid = sorted(set(main["prices"][name] for name in ("L25", "L50", "L90")))
    return dict(main=main, by_kind={k: summarize(groups, kind=k) for k in ("FH", "HU")},
                by_seed={str(s): summarize({key: rows for key, rows in groups.items() if key[1] == s})
                         for s in seeds},
                leave_seed_pair_out=checks, unstable=unstable,
                extend_to_41_60=unstable and not expanded, expanded_once=expanded,
                price_grid=grid, collapsed_grid=len(grid) < 3,
                counts_by_world_seed={f"w{w}_s{s}": len(rows) for (w, s), rows in groups.items()})


def load(manifest, *, expanded=False):
    items = json.loads(Path(manifest).read_text())
    expected = {(w, s) for w in (1, 2) for s in range(41, 61 if expanded else 49)}
    keys = [(item["world"], item["seed"]) for item in items]
    # ファイルを開く前に、確認用の種や無関係な走行への参照を拒む。
    if len(keys) != len(set(keys)) or set(keys) != expected:
        raise ValueError("較正の世界×種の組が指定の範囲と違う")
    groups, exclusions = {}, {}
    for item in items:
        key = item["world"], item["seed"]
        values, omitted, trials = [], Counter(), []
        with gzip.open(item["path"], "rt", encoding="utf-8") as stream:
            for line in stream:
                row = json.loads(line)
                if (row["world"], row["seed"]) != key:
                    raise ValueError("記録の世界か種が表と違う")
                trials.append(row["trial"])
                values.extend(row["candidates"])
                omitted.update(x["reason"] for x in row["excluded"])
        if trials != list(range(1740)):
            raise ValueError("較正の全1740試行が揃っていない")
        if any(r["denominator"] <= 0 or r["V"] != r["numerator"] / r["denominator"] for r in values):
            raise ValueError("較正の分母か比が不正")
        groups[key] = values
        exclusions[f"w{key[0]}_s{key[1]}"] = dict(omitted)
    return groups, exclusions


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest")
    parser.add_argument("output")
    parser.add_argument("--expanded", action="store_true")
    args = parser.parse_args()
    groups, exclusions = load(args.manifest, expanded=args.expanded)
    result = report(groups, expanded=args.expanded)
    result["excluded_counts"] = exclusions
    with Path(args.output).open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(result, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    main()

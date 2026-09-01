#!/usr/bin/env python3
"""
build_battery.py — 電池（Sel 評価用の場面集合）を走行前に生成する

出所
  依頼K返答_fable（2026-08-21）§2   電池・はしご・Sel の定義
  依頼L返答_Fable（2026-08-28）§4-2 層の壊し方
  統合決定台帳 T-041                  Sel・電池・収量は保留。★ 採否は未判断
  統合決定台帳 T-043                  λ_mix は掃引軸ではない

★ このスクリプトを走らせることは「Sel を採る」ことを意味しない
  走行後に Sel を使う選択肢を残すための事前登録である（規範13）
  採らなければ、生成した電池を使わないだけ

Sel の定義（依頼K返答_fable §2）
  Sel(R, t) = log2 [ P(照合成立 | λ=1) / P(照合成立 | λ=0) ]  （ビット）

はしご（依頼L返答 §4-2）
  L0  λ=1   実生成（W1〜W7）。伏せ辺も適用する
  L1  共起   述語の出現を独立に引く。場面の骨格・アリティ・伏せ辺の規則は保つ
  L2  構造   共起は保ち、引数共有を壊す
  L3  役割   共起も引数共有も保ち、役割ユナリーとの対応だけ壊す

使い方
  python build_battery.py --out battery_v1.json --n 3000 --seed 20260829
  python build_battery.py --verify battery_v1.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path
from random import Random

sys.path.insert(0, str(Path(__file__).resolve().parent))

from abm.domains import Entity, Relation, RelationGraph
from abm.seed import load_seed
from abm.world import generate_trial

BATTERY_VERSION = "battery-v2"
LAYERS = ("L0_real", "L1_cooccurrence", "L2_argument_sharing", "L3_role_correspondence")


# --------------------------------------------------------------------------
# 事前登録する規約（★ 走行後に変えないこと）
# --------------------------------------------------------------------------
PREREGISTERED = {
    "match_criterion": "mapping",
    # 「照合成立」＝ 写像の成立（tau_acc を通ること）を主とする。
    # 構成素の充足を基準にした副版も同じ電池から出せるので、両方を台帳に残す
    # （T-038 と同型）。出所: 依頼L返答 §3-4 の Fable 案 ／ 2026-08-28 アストラさん承認
    "match_criterion_secondary": "satisfaction",
    "sel_sign": "signed",
    # Sel は符号つきで読む。絶対値にしない。
    # 理由: 共有述語の設計により D_dep が負になる def が存在しうる
    #       （Fable 実測: M4 の m=3 で −0.58 bit）。
    #       負は「世界より狭く共起している」という別の現象であり、絶対値にすると潰れる
    "tau_acc": 0.67,
    "battery_run_seed_offset": 900_000,
    # ★ 電池の場面は本走行の世界列と重ならない run_seed 帯から作る
}


# --------------------------------------------------------------------------
# 層ごとの壊し方
# --------------------------------------------------------------------------
def shuffle_L1(scenes: list[RelationGraph], rng: Random) -> list[RelationGraph]:
    """共起を壊す。述語を大域プールから引き直す。骨格・アリティ・伏せ辺の規則は保つ。

    ★ アリティ別のプールから引くこと。混ぜると照合器が引数の本数の不一致で例外を投げる
      （2026-08-28 に実測で確認）
    """
    pool: dict[int, list[str]] = {}
    for graph in scenes:
        for relation in graph.relations:
            pool.setdefault(len(relation.arguments), []).append(relation.predicate)
    out = []
    for graph in scenes:
        relations = tuple(
            Relation(r.relation_id, rng.choice(pool[len(r.arguments)]), r.arguments)
            for r in graph.relations
        )
        out.append(RelationGraph(graph.graph_id, graph.entities, relations))
    return out


def shuffle_L2(graph: RelationGraph, rng: Random) -> RelationGraph:
    """引数共有を壊す。共起（述語の顔ぶれ）は保つ。

    実体引数を場面内で置換し、関係参照（高階の引数）を場面内の一階関係へ張り直す
    """
    entity_ids = [e.entity_id for e in graph.entities]
    permuted = entity_ids[:]
    rng.shuffle(permuted)
    entity_map = dict(zip(entity_ids, permuted))
    relation_ids = {r.relation_id for r in graph.relations}
    first_order = [
        r.relation_id for r in graph.relations
        if all(a not in relation_ids for a in r.arguments)
    ]
    out = []
    for r in graph.relations:
        args = []
        for a in r.arguments:
            if a in entity_map:
                args.append(entity_map[a])
            elif a in relation_ids:
                args.append(rng.choice(first_order) if first_order else a)
            else:
                args.append(a)
        out.append(Relation(r.relation_id, r.predicate, tuple(args)))
    return RelationGraph(graph.graph_id, graph.entities, tuple(out))


def shuffle_L3(scenes: list[RelationGraph], rng: Random) -> list[RelationGraph]:
    """役割ユナリーとの対応だけ壊す。共起も引数共有も保つ。

    ★ v2 の変更（2026-08-29）：プールからの引き直しを ★ 場面間の置換 に改めた。

    v1 は `rng.choice(role_pool)` で一様抽出していた。実世界の役割ユナリーは
    偶然ちょうど一様（モチーフが 4 試行ブロックで均等に並ぶ設計の帰結）なので
    期待値は一致していたが、標本ゆらぎのぶん周辺が保たれなかった
    （実測：n=600 で最大差 0.0019、n=3000 で 0.0015。理論的な標本誤差の範囲）。

    実在するユナリー述語を場面間で置換すれば、周辺は ★ 厳密に 保たれる（実測 0.0000）。
    実世界が一様でなくなったときにも壊れない。
    """
    pool = [r.predicate for g in scenes for r in g.relations if len(r.arguments) == 1]
    permuted = pool[:]
    rng.shuffle(permuted)
    supply = iter(permuted)
    out = []
    for graph in scenes:
        relations = tuple(
            Relation(r.relation_id, next(supply), r.arguments) if len(r.arguments) == 1 else r
            for r in graph.relations
        )
        out.append(RelationGraph(graph.graph_id, graph.entities, relations))
    return out


# --------------------------------------------------------------------------
# 生成
# --------------------------------------------------------------------------
def _graph_to_dict(g: RelationGraph) -> dict:
    return {
        "graph_id": g.graph_id,
        "entities": [e.entity_id for e in g.entities],
        "relations": [
            {"relation_id": r.relation_id, "predicate": r.predicate,
             "arguments": list(r.arguments)}
            for r in g.relations
        ],
    }


def build(n: int, rng_seed: int) -> dict:
    seed = load_seed()
    offset = PREREGISTERED["battery_run_seed_offset"]

    trials = [generate_trial(offset, i, ["battery"], seed=seed) for i in range(n)]
    real = [t.target_graph_partial for t in trials]
    motifs = [t.motif for t in trials]

    layers = {
        "L0_real": real,
        "L1_cooccurrence": shuffle_L1(real, Random(rng_seed + 1)),
        "L2_argument_sharing": [shuffle_L2(g, Random(rng_seed + 2000 + i))
                                for i, g in enumerate(real)],
        "L3_role_correspondence": shuffle_L3(real, Random(rng_seed + 3000)),
    }

    # 周辺が保たれているかの自己検査（★ L1 は述語を引き直すので保たれない）
    def marginals(gs):
        c = Counter(r.predicate for g in gs for r in g.relations)
        total = sum(c.values())
        return {k: v / total for k, v in c.items()}

    checks = {}
    m0 = marginals(real)
    for name in LAYERS:
        m = marginals(layers[name])
        keys = set(m0) | set(m)
        checks[name] = {
            "relation_count": sum(len(g.relations) for g in layers[name]),
            "max_marginal_diff": max(abs(m.get(k, 0.0) - m0.get(k, 0.0)) for k in keys),
            "scene_size_mean": sum(len(g.relations) for g in layers[name]) / len(layers[name]),
        }

    payload = {
        "version": BATTERY_VERSION,
        "n_scenes": n,
        "rng_seed": rng_seed,
        "battery_run_seed": offset,
        "seed_file_sha256": hashlib.sha256(
            Path("U-011_seed_v1.json").read_bytes()).hexdigest(),
        "preregistered": PREREGISTERED,
        "motifs": motifs,
        "layers": {name: [_graph_to_dict(g) for g in layers[name]] for name in LAYERS},
        "self_checks": checks,
    }
    return payload


def write(payload: dict, out: Path) -> str:
    body = json.dumps(payload, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":")).encode()
    digest = hashlib.sha256(body).hexdigest()
    out.write_bytes(body)
    (out.parent / (out.name + ".sha256")).write_text(digest + "\n")
    return digest


def verify(path: Path) -> None:
    body = path.read_bytes()
    digest = hashlib.sha256(body).hexdigest()
    expect = (path.parent / (path.name + ".sha256")).read_text().strip()
    payload = json.loads(body)
    print(f"電池   {path}")
    print(f"  sha256   {digest}")
    print(f"  記録値   {expect}   {'一致' if digest == expect else '★ 不一致'}")
    print(f"  版       {payload['version']}   場面数 {payload['n_scenes']}")
    print(f"  種       {payload['seed_file_sha256'][:16]}…")
    print("\n  事前登録した規約")
    for k, v in payload["preregistered"].items():
        print(f"    {k:<28}{v}")
    print(f"\n  {'層':<26}{'関係の総数':>12}{'場面の平均長':>14}{'周辺の最大差':>14}")
    for name in LAYERS:
        c = payload["self_checks"][name]
        print(f"    {name:<24}{c['relation_count']:>12}"
              f"{c['scene_size_mean']:>14.3f}{c['max_marginal_diff']:>14.4f}")
    print("""
  読み方
    ★ L2・L3 は周辺を厳密に保つので、最大差は 0.0000 でなければならない
      （v1 の L3 は一様抽出だったので 0.0015 程度のゆらぎが出ていた。v2 で置換に改めた）
    L1 は述語を大域プールから引き直すので、標本ゆらぎのぶんだけ差が出る（0.01 未満が目安）
    場面の平均長は全層で同じはず（骨格を保つため）
""")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="battery_v1.json")
    ap.add_argument("--n", type=int, default=3000)
    ap.add_argument("--seed", type=int, default=20260829)
    ap.add_argument("--verify", default=None)
    args = ap.parse_args()

    if args.verify:
        verify(Path(args.verify))
        return

    out = Path(args.out)
    if out.exists():
        raise SystemExit(f"★ {out} が既にあります。上書きしません（事前登録した成果物のため）")
    payload = build(args.n, args.seed)
    digest = write(payload, out)
    print(f"電池を書きました  {out}  ({out.stat().st_size/1e6:.1f} MB)")
    print(f"  sha256  {digest}")
    print(f"\n★ この sha256 を走行台帳の run ヘッダへ入れること（委任A F3）")
    print(f"★ 生成後は編集しないこと。作り直すときは版を上げる（battery_v2）")
    verify(out)


if __name__ == "__main__":
    main()

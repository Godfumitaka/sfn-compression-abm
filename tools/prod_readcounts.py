"""★ tools/v32_readcounts.py の写し（2026-09-26 夜）。本番の流れ（tools/prod_post_one.py）で使うため、どこでも動くようにした：
   コードの場所をこのファイルの置き場所から決め、通過群 L の表を --lsweep で渡す。数え方は元と同じ。
本番の前の確かめ（2026-09-26 夜、アストラさんの指示）：読むだけで数える。★ 判定しない。模型と台帳は変えない。
台帳ごとに
  誕生 ＝ reg_del_events の registration で was_extension＝False の数（生まれた定義の数）。
  写し ＝ 生まれた定義のうち、生まれた時点で、すでにある生きた定義と同じ中身だったもの。
    ★ 定義：誕生の試行で入った行（registered_at＝t）のグラフが、その試行の前（t−1 の後）に生きていた別の定義の生きている行のグラフと、
      行の数と述語の組が同じで、写し（名前の順番の直しあり、tools/fixorder.py）の点が両方の自己の点と等しい
      （全部の行が同じ述語どうしで、引数のつながりも矛盾なく対になる）もの。
    ★ 生まれた試行のうちに消えて（m_live＝0）比べられなかった定義は「比べられず」に数える（写しにも写しでないにも入れない）。
  話した定義 ＝ 一度でも R_used で棄権しなかった（coverage＝1）定義の数。割合の分母は、その台帳で生まれた定義の数。
  L3・L6 ＝ 中心的過程（通過群 L）を通った定義の数（analysis_pred_2026-09-22/lsweep_<腕>.json の pass）。
状態は解析の組み立て直し（recon_removed、版 6・7 の走査と同じ）で作る。
使い方  python3.12 tools/prod_readcounts.py <腕名> <走行根（ledgers）> <出力 json> [workers] [--lsweep <lsweep の json>]"""
import collections, concurrent.futures, glob, gzip, json, os, pathlib, sys, time
CODE = pathlib.Path(__file__).resolve().parent.parent
for p in (CODE, CODE / "analysis_v3a2cf_2026-09-17", CODE / "analysis_sbe_2026-09-19", CODE / "tools"):
    sys.path.insert(0, str(p))
from abm.seed import load_seed
from abm.domains import Entity, RelationGraph
from abm.abstraction import _definition_graph
import abm.sme as sme
import fixorder
fixorder.install()
from recon_removed import MultisetReconstructorWithRemoval

_a = [x for x in sys.argv[1:]]
LSW = None
if "--lsweep" in _a:
    i = _a.index("--lsweep"); LSW = pathlib.Path(_a[i + 1]); _a = _a[:i] + _a[i + 2:]
ARM, RD, OUT = _a[0], _a[1], pathlib.Path(_a[2])
WK = int(_a[3]) if len(_a) > 3 else 4
SEEDP = str(CODE / "seeds/U-011_seed_v3a2.json")


def graph_of(relations, all_ids, gid):
    ents = sorted({a for r in relations for a in r.arguments if a not in all_ids})
    return RelationGraph(graph_id=gid, entities=tuple(Entity(e) for e in ents), relations=tuple(relations))


def self_score(g, cache, key):
    if key not in cache:
        cache[key] = sme.map_graphs(g, g).alignment.total_score
    return cache[key]


def one(p):
    t0 = time.time()
    cell = os.path.basename(os.path.dirname(p)); seed = os.path.basename(p).replace(".jsonl.gz", "")
    with gzip.open(p, "rt", encoding="utf-8") as f:
        h = json.loads(next(f))
    REC = MultisetReconstructorWithRemoval(h, seed=load_seed(SEEDP))
    births = copies = lost = 0
    born, spoke = set(), set()
    with gzip.open(p, "rt", encoding="utf-8") as f:
        next(f)
        for line in f:
            r = json.loads(line)
            if r.get("record_type") != "trial":
                continue
            t = r["prediction_order"]
            prev = REC.state
            newnames = [e["R"] for e in (r.get("reg_del_events") or ())
                        if e.get("kind") == "registration" and not e.get("was_extension")]
            REC.consume(r, verify_world=False)
            if r.get("R_used") is not None and r.get("coverage") == 1:
                spoke.add(r["R_used"])
            for R in newnames:
                births += 1; born.add(R)
                d = REC.state.definitions.get(R)
                rows = [c for c in d.constituents if c.registered_at == t] if d is not None else []
                if not rows:
                    lost += 1; continue
                gnew = graph_of([c.relation for c in rows], {c.relation.relation_id for c in d.constituents}, "new")
                pn = sorted(r_.predicate for r_ in gnew.relations)
                snew = sme.map_graphs(gnew, gnew).alignment.total_score
                cache = {}
                hit = False
                for D in prev.definitions.values():
                    if D.m_live == 0 or D.name == R:
                        continue
                    live = [c.relation for c in D.constituents if c.alive]
                    if sorted(x.predicate for x in live) != pn:
                        continue
                    gold = _definition_graph(D, mode="live")
                    sold = self_score(gold, cache, D.name)
                    s = sme.map_graphs(gnew, gold).alignment.total_score
                    if abs(s - snew) < 1e-9 and abs(s - sold) < 1e-9:
                        hit = True; break
                copies += hit
    return dict(cell=cell, seed=seed, 誕生=births, 写し=copies, 比べられず=lost, 生まれた定義=len(born),
                話した定義=len(spoke & born), 話した定義_全部=len(spoke), 秒=round(time.time() - t0, 1))


def main():
    fs = sorted(glob.glob(f"{RD}/cells/*/seed*.jsonl.gz")); assert fs, RD
    with concurrent.futures.ProcessPoolExecutor(max_workers=WK) as ex:
        res = list(ex.map(one, fs))
    ls = LSW if LSW is not None else CODE / f"analysis_pred_2026-09-22/lsweep_{ARM}.json"
    if ls.exists():
        L = {(x["cell"], x["seed"]): x["定義"] for x in json.load(open(ls, encoding="utf-8"))["台帳"]}
        for x in res:
            dd = L.get((x["cell"], x["seed"]), {})
            x["L3"] = sum(1 for v in dd.values() if 3 in v.get("pass", []))
            x["L6"] = sum(1 for v in dd.values() if 6 in v.get("pass", []))
    json.dump({"腕": ARM, "走行根": RD, "lsweep": str(ls) if ls.exists() else None, "台帳": res},
              open(OUT, "w"), ensure_ascii=False, indent=1)
    print("->", OUT)


if __name__ == "__main__":
    main()

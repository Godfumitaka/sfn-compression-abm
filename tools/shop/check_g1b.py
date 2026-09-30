"""関門 1-b：お店の世界の旗を付けた一本の確かめ。★ 読むだけ。
使い方  python3.12 tools/shop/check_g1b.py <走行根> <種> <世界 1|2> <例外の割合>
世界を tools/shopworld.py の包みで作り直し（世界の指紋を台帳と比べる）、試行ごとに次を数える：
  台帳の 4 欄（shop_type・shop_cue・door_pred・held_out_is_door）があり、作り直した世界の値と同じ／シールと link が完全な場面と提示の両方にある／
  ドアの述語が表のとおり／シールと link が伏せられていない／例外の割合。あわせて side の shop.jsonl・probe.jsonl の行の種類を数える。"""
import glob, gzip, json, os, sys
from collections import Counter
W = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path[:0] = [os.path.join(W, "tools"), W]
import abm.world as w
from abm.seed import load_seed
import shopworld as sw
root, seed, world, exc = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), float(sys.argv[4])
fl = json.load(open(os.path.join(root, "flag.json")))
cfg = json.load(open(os.path.join(W, fl["config"])))
sd = load_seed(os.path.join(W, cfg["seed_file"]))
sw.CFG.update(world=world, exc=exc)
orig = w.generate_trial
w.generate_trial = lambda rs, i, a, *, seed, holdout_include_second_order=False: sw.shop_trial(orig, rs, i, a, seed=seed, holdout_include_second_order=holdout_include_second_order)
p = glob.glob(os.path.join(root, f"ledgers/cells/*/seed{seed:03d}.jsonl.gz"))[0]
c = Counter()
with gzip.open(p, "rt", encoding="utf-8") as f:
    h = json.loads(next(f))
    W_ = w.generate_world(h["run_seed"], h["trial_count"], ["agent"], seed=sd, holdout_include_second_order=bool(h.get("arm_holdout_second_order")))
    c["世界の指紋が同じ"] = int(W_.world_hash == h["world_hash"])
    for line, tr in zip(f, W_.trials):
        r = json.loads(line)
        if r.get("record_type", "trial") != "trial":
            continue
        c["試行"] += 1
        info = sw.INFO[tr.G_star.graph_id]
        c["台帳の 4 欄がある"] += all(k in r for k in ("shop_type", "shop_cue", "door_pred", "held_out_is_door"))
        c["台帳の 4 欄が作り直しと同じ"] += all(r.get(k) == info[k] for k in ("shop_type", "shop_cue", "door_pred", "held_out_is_door"))
        g = {x.relation_id: x for x in tr.G_star.relations}
        v = {x.relation_id: x for x in tr.target_graph_partial.relations}
        c["シールと link が完全な場面にある"] += info["sig_id"] in g and info["link_id"] in g
        c["シールと link が提示にある"] += info["sig_id"] in v and info["link_id"] in v
        c["シールと link が伏せられた"] += tr.held_out_edge.relation_id in (info["sig_id"], info["link_id"])
        c["観測の提示が台帳と同じ"] += [x.relation_id for x in tr.target_graph_partial.relations] == r["observable_mask_edges"]
        want = sw.door_pred(world, info["shop_type"], info["shop_cue"])
        c["ドアの述語が表のとおり"] += g[info["door_id"]].predicate == want
        c[f"型{info['shop_type']}・{info['shop_cue']}"] += 1
        c["例外"] += info["shop_cue"] == "e"
        c["ドアが伏せられた"] += bool(info["held_out_is_door"])
        if info["held_out_is_door"]:
            c["ドアが伏せられ、伏せ辺の述語が表のとおり"] += tr.held_out_edge.predicate == want == r["held_out_content"]["predicate"]
side = os.path.dirname(p).replace("/ledgers/cells/", "/side/")
for fn in ("shop.jsonl", "probe.jsonl"):
    q = os.path.join(side, f"seed{seed:03d}.{fn}")
    if os.path.exists(q):
        kinds = Counter()
        for l in open(q, encoding="utf-8"):
            d = json.loads(l)
            kinds[(d.get("which"), d.get("from"), d.get("to")) if fn == "shop.jsonl" else (d.get("shop_probe") or "既存")] += 1
        c[f"side {fn} の行"] = sum(kinds.values())
        print(fn, dict(kinds) if fn == "probe.jsonl" else dict(kinds.most_common(12)))
c["例外の割合（%）"] = round(100 * c["例外"] / c["試行"], 1)
print(json.dumps(dict(c), ensure_ascii=False, indent=0))

"""速報（2026-09-25）：群S と群N の 外÷内 の誤答率（水位-1 の測り方、suii_s1.py と同じ）を腕ごとに並べる。★ 判定しない。
★ 水準3（traj8）。群は t1739 生存の定義（rows2 の述語の 284 組のまたぎ）で S/N、新θ8（newlabelR）で P。
★ 誤答率 ＝（喋った − 的中）／喋った。比 ＝ 外の誤答率 ÷ 内の誤答率。
使い方  python3.12 tools/suii_v3.py <出力.md> <ラベル>:<腕名>:<種の上限> ..."""
import collections, io, json, statistics as st, sys
sys.path.insert(0, "/Users/tatsu-admin/sfn/sfn-compression-abm/analysis_pred_2026-09-22")
import grp  # noqa
B = "/Users/tatsu-admin/sfn/sfn-compression-abm"


def load(arm, smax):
    keep = {f"seed{i:03d}" for i in range(1, smax + 1)}
    r2 = {(x["cell"], x["seed"], x["R"]): sorted({r["pred"] for r in x["行"]})
          for x in json.load(io.open(f"{B}/analysis_sbe_2026-09-19/rows2_{arm}.json", encoding="utf-8"))["定義"] if x["seed"] in keep}
    nl = json.load(io.open(f"{B}/analysis_newlabel_2026-09-19/newlabelR_{arm}.json", encoding="utf-8"))
    P = set()
    for k, v in nl.items():
        if k.startswith("R|") and k.endswith("|新θ8") and v:
            rk, rn = k.split("|")[1], k.split("|")[2]; ce, se = rk.split("/"); P.add((ce, se, rn))
    lab = {k: ("P" if k in P else ("S" if grp.crossings(v) >= 1 else "N")) for k, v in r2.items()}
    per = collections.defaultdict(collections.Counter); tot = collections.defaultdict(collections.Counter)
    for x in json.load(io.open(f"{B}/analysis_sbe_2026-09-19/traj8_{arm}.json", encoding="utf-8"))["定義"]:
        g = lab.get((x["cell"], x["seed"], x["R"]))
        if g is None:
            continue
        for sd in ("内", "外"):
            for kk in ("喋った", "的中"):
                v = x.get(kk + "_" + sd, 0); per[(x["seed"], g)][kk + "_" + sd] += v; tot[g][kk + "_" + sd] += v
    return per, tot, sorted(keep), collections.Counter(lab.values())


def rates(c):
    ei = (c["喋った_内"] - c["的中_内"]) / c["喋った_内"] if c["喋った_内"] else None
    eo = (c["喋った_外"] - c["的中_外"]) / c["喋った_外"] if c["喋った_外"] else None
    return ei, eo, (eo / ei if (ei and eo is not None) else None)


out = sys.argv[1]
L = ["# 速報：群S・群N の外÷内の誤答率（水位-1 の測り方、水準3）　判定しない", "",
     "| ラベル | 腕 | 種 | 群 | 定義（t1739 生存） | 喋った 内／外 | 誤答率 内 | 誤答率 外 | **外÷内（合計）** | 外÷内（種ごとの中央値／出せた種） |",
     "|---|---|---|---|---:|---:|---:|---:|---:|---:|"]
f = lambda x, fmt: "—" if x is None else fmt.format(x)
for spec in sys.argv[2:]:
    lab, arm, smax = spec.split(":"); smax = int(smax)
    per, tot, seeds, cnt = load(arm, smax)
    for g in ("S", "N"):
        ei, eo, r = rates(tot[g])
        v = [rates(per[(s, g)])[2] for s in seeds]; v = [x for x in v if x is not None]
        med = f"{st.median(v):.3f} / {len(v)}" if v else f"— / 0"
        L.append(f"| {lab} | {arm} | 1〜{smax} | {g} | {cnt[g]:,} | {tot[g]['喋った_内']:,}／{tot[g]['喋った_外']:,} | "
                 f"{f(ei,'{:.4f}')} | {f(eo,'{:.4f}')} | {f(r,'{:.3f}')} | {med} |")
open(out, "w", encoding="utf-8").write("\n".join(L) + "\n")
print(f"-> {out}")

"""出どころ別の内と外の世界偽の率（2026-09-25 23 時、アストラさんの指示）。★ 数えるだけ。判定しない。
入力：tools/l2scan_spoke_s21.py の出力（l2s_<腕>.json）と、群を付けるための rows2・newlabelR（defs_table.py と同じ付け方）。
出どころ：源投影（投影）／源生充（生きている行の充填）／源墓充（墓石の充填）。
内外：旧（旧内 ＝ ①>=1、旧外 ＝ ①=0）と新（話内 ＝ t より前に話した場面の型、話外 ＝ そうでない）。
率 ＝ 世界偽 ÷（世界偽＋世界真）。世界不明は数えない。
使い方  python3.12 tools/spoke_src_rates.py <出力.md> <l2s のある場所> <腕> ..."""
import collections, io, json, sys
sys.path.insert(0, "/Users/tatsu-admin/sfn/sfn-compression-abm/analysis_pred_2026-09-22")
import importlib.util
_spec = importlib.util.spec_from_file_location("grp_pred", "/Users/tatsu-admin/sfn/sfn-compression-abm/analysis_pred_2026-09-22/grp.py")
grp = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(grp)
B = "/Users/tatsu-admin/sfn/sfn-compression-abm"
out, IN, arms = sys.argv[1], sys.argv[2], sys.argv[3:]
SRC = [("源投影", "投影"), ("源生充", "生きている行の充填"), ("源墓充", "墓石の充填")]
IO = [("旧内", "旧外", "旧（①≧1／①=0）"), ("話内", "話外", "新（話した）")]
L = ["# 出どころ別の内と外の世界偽の率（水準2、v2・s21）　判定しない", "",
     "★ 率 ＝ 世界偽 ÷（世界偽＋世界真）。括弧は 世界偽／（世界偽＋世界真）。群は defs_table.py と同じ付け方（t1739 生存は rows2 の述語・新θ8 で P、途中で消えた定義は最後に生きていた試行の述語で S/N）。", ""]
for arm in arms:
    d = json.load(open(f"{IN}/l2s_{arm}.json"))["台帳"]
    r2 = {(x["cell"], x["seed"], x["R"]): sorted({r["pred"] for r in x["行"]})
          for x in json.load(io.open(f"{B}/analysis_sbe_2026-09-19/rows2_{arm}.json", encoding="utf-8"))["定義"]}
    nl = json.load(io.open(f"{B}/analysis_newlabel_2026-09-19/newlabelR_{arm}.json", encoding="utf-8"))
    P8 = set()
    for k, v in nl.items():
        if k.startswith("R|") and k.endswith("|新θ8") and v:
            rk, rn = k.split("|")[1], k.split("|")[2]; ce, se = rk.split("/"); P8.add((ce, se, rn))
    tot = collections.defaultdict(collections.Counter)
    for x in d:
        for Rn, v in x["定義"].items():
            k = (x["cell"], x["seed"], Rn); alive = k in r2
            preds = r2[k] if alive else v.get("最後の生存述語", [])
            g = "P" if (alive and k in P8) else ("S" if grp.crossings(preds) >= 1 else "N")
            for gg in ("全", g):
                for key, val in v.items():
                    if key.startswith("源") and isinstance(val, int):
                        tot[gg][key] += val
    L += [f"## {arm}", "", "| 群 | 出どころ | 物差し | 内 | 外 | 外−内 |", "|---|---|---|---:|---:|---:|"]
    for gg in ("全", "S", "N"):
        c = tot[gg]
        for sk, slab in SRC:
            for ki, ko, lab in IO:
                def rate(k):
                    n = c[f"{sk}{k}_世界偽"] + c[f"{sk}{k}_世界真"]
                    return (c[f"{sk}{k}_世界偽"] / n if n else None), c[f"{sk}{k}_世界偽"], n
                ri, wi, ni = rate(ki); ro, wo, no = rate(ko)
                f = lambda r, w, n: "—" if r is None else f"{r:.4f}（{w:,}／{n:,}）"
                dd = "—" if (ri is None or ro is None) else f"{ro - ri:+.4f}"
                L.append(f"| {gg} | {slab} | {lab} | {f(ri, wi, ni)} | {f(ro, wo, no)} | {dd} |")
    L.append("")
open(out, "w", encoding="utf-8").write("\n".join(L) + "\n")
print(f"-> {out}")

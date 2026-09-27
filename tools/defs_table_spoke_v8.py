"""★★ 版 8（2026-09-27、委任書「v3.4」2）：定義の表を、走査の版 8（tools/l2scan_spoke_v8.py）の出力だけから作る。★ 判定しない。
版 7（tools/defs_table_spoke_v7.py）との違い
  ・一行 ＝ 定義の同一性（「名前@生まれた試行」）。defid ＝ <セル>/<種>/<名前>@<生まれた試行>。主張しなかった同一性も行にする（claimed＝0）。
  ・走行末に生きているか（alive）・走行末の生存述語・通過群 L=2〜6 は、走査の版 8 が同一性ごとに出したもの
    （版 7 は rows2・lsweep・newlabelR の名前ごとの値）。L は版 7 と同じく、走行末に生きている定義だけに付ける。
    群 P は、走行末に生きていて L=2 を通ったもの（newlabel_R の 新θ8 と同じ条件）。群 S・N は版 7 と同じ（またぎの組が 1 組以上か）。
  ・またぎの組の表は、引数 --pairs で渡す（世界ごと。tools/make_pairs.py で作る。v3a2 は analysis_sbe_2026-09-19/pairs252_v3a2.json と同じ集まり）。
  ・率は版 7 と同じく 世界偽 ÷（世界偽＋世界真）＝ 言い直しを除いた率。n_* も世界偽＋世界真（言い直しを含まない）。
    言い直しの数は右の rs_* の列（版 7 の列と同じ並び）。含めた率 ＝ wf ÷（n ＋ rs）。
  ・右に足した列：name born died claimed n_claims n_restate、rs_*（版 7 の各列の組に対応する言い直しの数）。
使い方  python3.12 tools/defs_table_spoke_v8.py <腕名> <l2s8.json> <出力csv> --pairs <またぎの組の表 json>"""
import csv, io, itertools, json, sys

a = list(sys.argv[1:])
i = a.index("--pairs"); PAIRSF = a[i + 1]; a = a[:i] + a[i + 2:]
ARM, L2S, OUT = a[:3]
PAIRS = {tuple(sorted(x)) for x in json.load(io.open(PAIRSF, encoding="utf-8"))}


def crossings(preds):   # analysis_pred_2026-09-22/grp.py:26-28 と同じ式
    return sum(1 for x, y in itertools.combinations(sorted(set(preds)), 2) if (x, y) in PAIRS)


d = json.load(io.open(L2S, encoding="utf-8"))["台帳"]


def pair(v, pi, po):
    ni = v.get(pi + "_世界偽", 0) + v.get(pi + "_世界真", 0); no = v.get(po + "_世界偽", 0) + v.get(po + "_世界真", 0)
    wi = v.get(pi + "_世界偽", 0); wo = v.get(po + "_世界偽", 0)
    return [ni, wi, no, wo, (wi / ni) if ni else "", (wo / no) if no else ""]


def src(v):
    out = []
    for sk in ("源投影", "源生充", "源墓充"):
        out += [v.get(sk + "_世界偽", 0) + v.get(sk + "_世界真", 0), v.get(sk + "_世界偽", 0)]
    return out


def four(v, P):
    out = []
    for k in (P + "見話", P + "見未話", P + "未見未話", P + "未見話"):
        nn = v.get(k + "_世界偽", 0) + v.get(k + "_世界真", 0); wf = v.get(k + "_世界偽", 0)
        out += [nn, wf, (wf / nn) if nn else ""]
    return out


RS_KEYS = [("in", "a"), ("out", "b"), ("in_spk", "話内"), ("out_spk", "話外"), ("in_fb", "開内"), ("out_fb", "開外"),
           ("proj", "源投影"), ("fill_live", "源生充"), ("fill_tomb", "源墓充"),
           ("in_all", "全話内"), ("out_all", "全話外"), ("in_late", "後話内"), ("out_late", "後話外"),
           ("in_old_late", "後a"), ("out_old_late", "後b"),
           ("seen_spoke", "四見話"), ("seen_quiet", "四見未話"), ("unseen", "四未見未話"), ("unseen_spoke", "四未見話"),
           ("seen2_spoke", "五見話"), ("seen2_quiet", "五見未話"), ("unseen2", "五未見未話"), ("unseen2_spoke", "五未見話"),
           ("in_cor", "訂正内"), ("out_cor", "訂正外"), ("in_cor_all", "全訂正内"), ("out_cor_all", "全訂正外"),
           ("in_cor_late", "後訂正内"), ("out_cor_late", "後訂正外")]
HEAD = ["arm", "seed", "defid", "alive", "grp", "matagi", "L2", "L3", "L4", "L5", "L6",
        "n_in", "wf_in", "n_out", "wf_out", "rate_in", "rate_out", "degree", "n_total",
        "n_in_spk", "wf_in_spk", "n_out_spk", "wf_out_spk", "rate_in_spk", "rate_out_spk",
        "n_in_fb", "wf_in_fb", "n_out_fb", "wf_out_fb", "rate_in_fb", "rate_out_fb",
        "n_proj", "wf_proj", "n_fill_live", "wf_fill_live", "n_fill_tomb", "wf_fill_tomb",
        "n_in_all", "wf_in_all", "n_out_all", "wf_out_all", "rate_in_all", "rate_out_all",
        "n_in_late", "wf_in_late", "n_out_late", "wf_out_late", "rate_in_late", "rate_out_late",
        "n_in_old_late", "wf_in_old_late", "n_out_old_late", "wf_out_old_late", "rate_in_old_late", "rate_out_old_late",
        "n_seen_spoke", "wf_seen_spoke", "rate_seen_spoke", "n_seen_quiet", "wf_seen_quiet", "rate_seen_quiet",
        "n_unseen", "wf_unseen", "rate_unseen", "n_unseen_spoke", "wf_unseen_spoke", "rate_unseen_spoke",
        "n_seen2_spoke", "wf_seen2_spoke", "rate_seen2_spoke", "n_seen2_quiet", "wf_seen2_quiet", "rate_seen2_quiet",
        "n_unseen2", "wf_unseen2", "rate_unseen2", "n_unseen2_spoke", "wf_unseen2_spoke", "rate_unseen2_spoke",
        "n_in_cor", "wf_in_cor", "n_out_cor", "wf_out_cor", "rate_in_cor", "rate_out_cor",
        "n_in_cor_all", "wf_in_cor_all", "n_out_cor_all", "wf_out_cor_all", "rate_in_cor_all", "rate_out_cor_all",
        "n_in_cor_late", "wf_in_cor_late", "n_out_cor_late", "wf_out_cor_late", "rate_in_cor_late", "rate_out_cor_late",
        "name", "born", "died", "claimed", "n_claims", "n_restate", *[f"rs_{k}" for k, _ in RS_KEYS]]
n = 0
with open(OUT, "w", newline="", encoding="utf-8") as fo:
    w = csv.writer(fo)
    w.writerow(HEAD)
    for x in d:
        for K, v in x["定義"].items():
            alive = int(v.get("走行末に生きている", 0))
            preds = v.get("走行末の生存述語") if alive else v.get("最後の生存述語", [])
            mat = 1 if crossings(preds or []) >= 1 else 0
            ps = set((v.get("系列") or {}).get("pass", []))
            g = "P" if (alive and 2 in ps) else ("S" if mat else "N")
            ni, wi, no, wo, ri, ro = pair(v, "a", "b")
            dg = (ro - ri) if (ni and no) else ""
            row = [ARM, x["seed"], f"{x['cell']}/{x['seed']}/{K}", alive, g, mat,
                   *[1 if (alive and L in ps) else 0 for L in (2, 3, 4, 5, 6)],
                   ni, wi, no, wo, ri, ro, dg, ni + no,
                   *pair(v, "話内", "話外"), *pair(v, "開内", "開外"), *src(v),
                   *pair(v, "全話内", "全話外"), *pair(v, "後話内", "後話外"), *pair(v, "後a", "後b"),
                   *four(v, "四"), *four(v, "五"),
                   *pair(v, "訂正内", "訂正外"), *pair(v, "全訂正内", "全訂正外"), *pair(v, "後訂正内", "後訂正外"),
                   v.get("名前"), v.get("生まれた試行"), v.get("消えた試行"), int(v.get("主張あり", 0)), v.get("主張_計", 0),
                   v.get("a_言い直し", 0) + v.get("b_言い直し", 0),
                   *[v.get(k + "_言い直し", 0) for _, k in RS_KEYS]]
            w.writerow(row); n += 1
print(f"  {ARM}  定義（同一性）{n:,} -> {OUT}")

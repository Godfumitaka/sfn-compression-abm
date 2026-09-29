"""v3.9（--v39）の腕ごとの記録の要約（仕様 9 節）と、委任書 4 の control/ の一行。★ 判断しない。模型は動かさない（台帳と side を読むだけ）。
数えるもの（腕の全走行の和。ばらつきの単位は走行なので、走行ごとの値も json に残す）
  1 全課題を分母にした正解・誤答・棄権（正解＝話して当たり、誤答＝話して外れ、棄権＝話さない）。発話時正解率も併記。
     ★ この模型に強制出力は無い（棄権できる）。数えるのは実際の発話だけ。
  2 生まれた型以外への実際の発話の割合と、そこでの誤答（件数と率）。型＝場面生成器の構造の種類（世界を作り直した各試行の motif）。
     話した定義の同一性と生まれた型は tools/def_origin.py の表（merged/defs_spoke8org_<腕>.csv の born_motif。誕生材料の二場面の型は base_motif と born_motif）。
  3 F・H・U の席の数（走行末の和、試行の平均）。
  4 変数（U の席）：選ばれた定義（R_used）に含まれた数、写しが決まった数、答えが決まった数（全体最頻の名が一つに決まる）、穴埋めした数、
     実際の発話になった数、親の行の穴埋めに使われた数。
  5 変換：V＜0 で手放した件数（F→H・H→U）、容量で手放した件数と空いたビット、同点、容量から決まる境目（最高削除点・最低保持点）、
     点がちょうど 0 の変換の段別の内訳（仕様 7 節 P3）、定義の退役、覚え直しと、そのあと H→U で手放された覚え直しの席。
  6 容量不適合で止まった走行。
使い方  python3.12 tools/v39_summary.py <腕の走行根> <腕名> <結果の作業場所> <HOST> [--no-push] [--line-only]
  結果の作業場所の <HOST>/<腕>/ に 予算の記録_<腕>.md と v39要約_<腕>.json を書いて上げる（tools/results_push.py）。標準出力の最後の行が control/ の一行。
"""
from __future__ import annotations

import collections
import csv
import glob
import gzip
import json
import os
import statistics
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))


def motifs(header, seedf):
    from abm.seed import load_seed
    from abm.world import generate_world
    ws = generate_world(header["run_seed"], header["trial_count"], ["agent"], seed=load_seed(seedf),
                        holdout_include_second_order=bool(header.get("arm_holdout_second_order") or False))
    assert ws.world_hash == header["world_hash"]
    return [tr.motif for tr in ws.trials]


def one_ledger(p, side, inc, seedf):
    C = collections.Counter()
    with gzip.open(p, "rt", encoding="utf-8") as f:
        h = json.loads(next(f))
        MOT = motifs(h, seedf)
        spoken_ids = {}
        child = {}
        for line in f:
            r = json.loads(line)
            if r.get("record_type", "trial") != "trial":
                continue
            t = r["prediction_order"]
            C["課題"] += 1
            if r.get("coverage") == 1:
                C["正解" if r.get("hit") == 1 else "誤答"] += 1
                R = r.get("R_used")
                if R is not None:
                    bm = None
                    for born, died, motif in inc.get(R, ()):
                        if born < t and (died is None or t <= died):
                            bm = motif
                            break
                    if bm is None:
                        C["発話_生まれた型が分からない"] += 1
                    elif bm != MOT[t]:
                        C["発話_生まれた型以外"] += 1
                        C["誤答_生まれた型以外"] += r.get("hit") != 1
                    else:
                        C["発話_生まれた型"] += 1
                        C["誤答_生まれた型"] += r.get("hit") != 1
                pe = r.get("predicted_edge") or {}
                spoken_ids[t] = pe.get("relation_id")
            else:
                C["棄権"] += 1
            # 親の行の穴埋めに使われた U の席：穴埋めの関係の引数に、別の穴埋めの関係の ID が入っている
            fills = [e for e in (r.get("predictions_all_slots") or []) if str(e.get("relation_id", "")).startswith("filling__")]
            used_as_child = {a for e in fills for a in e.get("arguments", []) if str(a).startswith("filling__")}
            if used_as_child:
                child[t] = used_as_child
    # side の v39 の記録
    first = last = None
    FHU_sum = collections.Counter()
    n_rec = 0
    bnd_hi, bnd_lo = [], []
    relearned = set()
    forgets = []   # ★ D：活性で手放した定義 (R, 生まれた試行, 手放した試行)
    zero_by_stage = collections.Counter()
    for line in open(side, encoding="utf-8"):
        if '"v39' not in line:
            continue
        d = json.loads(line)
        if d.get("kind") == "v39_unfit":
            C["容量不適合"] += 1
            continue
        if d.get("kind") != "v39":
            continue
        t = d["trial"]
        n_rec += 1
        last = d
        if first is None:
            first = d
        for k in ("F", "H", "U"):
            FHU_sum[k] += d[k]
        C["最大使用量"] = max(C["最大使用量"], d["bits_after"])
        for kind, R, slot, V, dC, why, tie_n in d.get("conv") or []:
            C[f"変換_{kind}_{why}"] += 1
            if why == "cap":
                C["容量で空いたビット"] += dC
            elif why == "price":
                C["λで空いたビット"] += dC        # ★ v3.10（B）：V が λ を下回った変換（0 ≦ V ＜ λ）
            else:
                C["V負で空いたビット"] += dC
            if tie_n > 1:
                C["同点で選んだ"] += 1
            if why == "cap" and V == 0 and tie_n > 1:
                C["容量_点0の同点"] += 1          # ★ v3.10（A）：容量で変換した件数のうち、点数 0 の同点から選んだもの
            if V == 0:
                zero_by_stage[kind] += 1
            if kind == "HU" and (R, slot) in relearned:
                C["覚え直しのあと H→U"] += 1
        C["退役"] += len(d.get("retire") or [])
        for R, reg, B in d.get("forget") or []:
            forgets.append((R, reg, t))
        b = d.get("boundary")
        if b:
            C["境目のある試行"] += 1
            if b.get("最高削除点") is not None:
                bnd_hi.append(b["最高削除点"])
            if b.get("最低保持点") is not None:
                bnd_lo.append(b["最低保持点"])
        m1 = d.get("m1") or {}
        for x in (m1.get("relearn_m1") or []) + ((d.get("acc") or {}).get("relearn") or []):
            C["覚え直し"] += 1
            relearned.add((x["R"], x["slot"]))
        # 変数（U の席）
        ans = d.get("answers")
        if ans:
            fill = {fid: st for fid, st in (d.get("fill") or [])}
            for slot, st, pos_ok, a, u_ans in ans:
                if st != "U":
                    continue
                C["U_選ばれた定義に含まれた"] += 1
                C["U_写しが決まった"] += bool(pos_ok)
                C["U_答えが決まった"] += u_ans is not None
            R = d.get("R_used")
            u_fill_ids = {fid for fid, st in fill.items() if st == "U"}
            C["U_穴埋めした"] += len(u_fill_ids)
            if spoken_ids.get(t) in u_fill_ids:
                C["U_実際の発話"] += 1
            ch = child.get(t, set())
            C["U_親の穴埋めに使われた"] += len(u_fill_ids & ch)
            _ = R
    # ★ D：覚え直し ＝ 活性で手放した定義の生まれた型（場面の型）で、手放したあとに新しい定義が生まれた回数。
    #   誕生は定義の表（def_origin の born_motif）から。一つの誕生は一度だけ数える（同じ型を二度以上手放していても）。
    births = sorted((born, motif, R) for R, xs in inc.items() for born, died, motif in xs)
    motif_of = {(R, born): motif for R, xs in inc.items() for born, died, motif in xs}
    C["活性で手放した"] = len(forgets)
    first_release = {}
    for R, reg, t in forgets:
        m = motif_of.get((R, reg))
        if m is None:
            C["活性で手放した_型が分からない"] += 1
            continue
        first_release[m] = min(first_release.get(m, t), t)
        C["手放したあと同じ型が生まれた"] += any(b > t and bm == m for b, bm, _ in births)
    C["覚え直し_同じ型の誕生"] = sum(1 for b, bm, _ in births if bm in first_release and b > first_release[bm])
    C = collections.Counter({k: v for k, v in C.items() if not k.startswith("_")})
    C["走行末_F"] = last["F"] if last else 0
    C["走行末_H"] = last["H"] if last else 0
    C["走行末_U"] = last["U"] if last else 0
    C["走行末_定義"] = last["defs"] if last else 0
    per = {"FHU_平均": {k: FHU_sum[k] / n_rec for k in FHU_sum} if n_rec else {},
           "境目_最高削除点_中央値": statistics.median(bnd_hi) if bnd_hi else None,
           "境目_最低保持点_中央値": statistics.median(bnd_lo) if bnd_lo else None,
           "点0の変換_段別": dict(zero_by_stage)}
    return C, per


def main():
    a = [x for x in sys.argv[1:] if not x.startswith("--")]
    root, arm, results, host = Path(a[0]), a[1], Path(a[2]), a[3]
    no_push = "--no-push" in sys.argv
    fl = json.load(open(root / "flag.json", encoding="utf-8"))
    cfg = json.load(open(REPO / fl["config"], encoding="utf-8"))
    seedf = str(REPO / cfg.get("seed_file", "seeds/U-011_seed_v3a2.json"))
    inc = collections.defaultdict(lambda: collections.defaultdict(list))
    csvp = root / "merged" / f"defs_spoke8org_{arm}.csv"
    if csvp.exists():
        for row in csv.DictReader(open(csvp, encoding="utf-8")):
            cell, seed, K = row["defid"].split("/")
            R, born = K.rsplit("@", 1)
            died = row.get("died")
            inc[(cell, seed)][R].append((int(born), int(died) if died not in (None, "") else None, row.get("born_motif") or None))
    runs = []
    tot = collections.Counter()
    for p in sorted(glob.glob(str(root / "ledgers/cells/*/seed*.jsonl.gz"))):
        cell = os.path.basename(os.path.dirname(p))
        sd = os.path.basename(p)[:7]
        if not os.path.exists(p[:-len(".jsonl.gz")] + ".done"):
            continue   # ★ 最後まで走らなかった走行（容量不適合など）は数えない（下の「容量不適合」に side から載せる）
        side = root / "side" / cell / f"{sd}.jsonl"
        C, per = one_ledger(p, side, dict(inc[(cell, sd)]), seedf)
        tot.update(C)
        runs.append({"cell": cell, "seed": sd, **{k: C[k] for k in sorted(C)}, **per})
    # 容量不適合で台帳が途中までの走行は side だけにある
    unfit = []
    for s in sorted(glob.glob(str(root / "side/*/seed*.jsonl"))):
        for line in open(s, encoding="utf-8"):
            if '"v39_unfit"' in line:
                unfit.append({"side": os.path.relpath(s, root), "detail": json.loads(line).get("detail")})
    n = tot["課題"]
    spk = tot["正解"] + tot["誤答"]
    out_spk = tot["発話_生まれた型以外"]
    FHU_end = (tot["走行末_F"], tot["走行末_H"], tot["走行末_U"])
    summary = {
        "腕": arm, "走行": len(runs), "旗": {k: fl.get(k) for k in ("v39", "v39_budget", "v39_init", "v39_a", "v39_u", "v39_decay", "v39_price", "v39_forget_actr", "nsim", "config")},
        "課題": n, "正解": tot["正解"], "誤答": tot["誤答"], "棄権": tot["棄権"],
        "正解率（全課題）": tot["正解"] / n if n else None, "誤答率（全課題）": tot["誤答"] / n if n else None,
        "棄権率（全課題）": tot["棄権"] / n if n else None, "発話時正解率": tot["正解"] / spk if spk else None,
        "生まれた型以外への発話": out_spk, "生まれた型以外への発話の割合": out_spk / spk if spk else None,
        "生まれた型以外での誤答": tot["誤答_生まれた型以外"],
        "生まれた型以外での誤答率": tot["誤答_生まれた型以外"] / out_spk if out_spk else None,
        "生まれた型での誤答": tot["誤答_生まれた型"], "発話_生まれた型が分からない": tot["発話_生まれた型が分からない"],
        "走行末の席 F・H・U": FHU_end, "走行末の定義": tot["走行末_定義"],
        "試行の平均の席 F・H・U（走行の和）": [round(sum((r.get("FHU_平均") or {}).get(k, 0) for r in runs), 2) for k in "FHU"],
        "変数": {k[2:]: tot[k] for k in sorted(tot) if k.startswith("U_")},
        "変換": {k: tot[k] for k in sorted(tot) if k.startswith("変換_")},
        "容量で手放した件数": tot["変換_FH_cap"] + tot["変換_HU_cap"], "容量で空いたビット": tot["容量で空いたビット"],
        "V負で手放した件数": tot["変換_FH_neg"] + tot["変換_HU_neg"], "V負で空いたビット": tot["V負で空いたビット"],
        "同点で選んだ": tot["同点で選んだ"], "境目のある試行": tot["境目のある試行"],
        "容量で変換した件数のうち点数0の同点": tot["容量_点0の同点"],
        "容量で変換した件数のうち点数0の同点の割合": (tot["容量_点0の同点"] / (tot["変換_FH_cap"] + tot["変換_HU_cap"])
                                          if (tot["変換_FH_cap"] + tot["変換_HU_cap"]) else None),
        "λを下回って変換した件数（段別、V＜0 を含む）": {"F→H": tot["変換_FH_neg"] + tot["変換_FH_price"],
                                              "H→U": tot["変換_HU_neg"] + tot["変換_HU_price"],
                                              "うち V＜0 の F→H": tot["変換_FH_neg"], "うち V＜0 の H→U": tot["変換_HU_neg"]},
        "λで空いたビット": tot["λで空いたビット"],
        "活性で手放した定義": tot["活性で手放した"],
        "覚え直し（手放した定義の生まれた型で、手放したあとに生まれた新しい定義の数。各誕生を一度）": tot["覚え直し_同じ型の誕生"],
        "手放したうち、あとで同じ型の新しい定義が生まれたもの": tot["手放したあと同じ型が生まれた"],
        "点0の変換_段別（走行の和）": dict(sum((collections.Counter(r.get("点0の変換_段別") or {}) for r in runs), collections.Counter())),
        "退役": tot["退役"], "覚え直し": tot["覚え直し"], "覚え直しのあと H→U": tot["覚え直しのあと H→U"],
        "最大使用量（走行ごとの最大の中央値）": statistics.median([r["最大使用量"] for r in runs]) if runs else None,
        "容量不適合": unfit,
        "走行ごと": runs,
    }
    extra = ""
    if fl.get("v39_forget_actr") is not None:
        extra = (f"／活性で手放した定義 {tot['活性で手放した']:,}（その後に同じ型の場面で新しい定義が生まれた回数 {tot['覚え直し_同じ型の誕生']:,}、"
                 f"手放したうち同じ型の新しい定義があとで生まれたもの {tot['手放したあと同じ型が生まれた']:,}）")
    elif fl.get("v39_price") is not None:
        lam = summary["λを下回って変換した件数（段別、V＜0 を含む）"]
        extra = (f"／λ を下回って変換した件数（段別）F→H {lam['F→H']:,}・H→U {lam['H→U']:,}"
                 f"（うち V＜0 は F→H {lam['うち V＜0 の F→H']:,}・H→U {lam['うち V＜0 の H→U']:,}）")
    elif summary["容量で手放した件数"]:
        r0 = summary["容量で変換した件数のうち点数0の同点の割合"]
        extra = f"／容量で変換した件数のうち点数 0 の同点 {tot['容量_点0の同点']:,}（{100 * r0:.1f}%）"
    head = (f"予算 {fl.get('v39_budget')}" + (f"、λ＝{fl.get('v39_price')}" if fl.get("v39_price") is not None else "")
            + f"、初期 {fl.get('v39_init')}、a＝{fl.get('v39_a')}" + (f"、U {fl.get('v39_u')}" if fl.get("v39_u") not in (None, "global") else "")
            + (f"、重み {fl.get('v39_decay')}" if fl.get("v39_decay") not in (None, "uniform") else "")
            + (f"、τ＝{fl.get('v39_forget_actr')}" if fl.get("v39_forget_actr") is not None else ""))
    line = (f"- {arm}（{head}、走行 {len(runs)}"
            f"{'、容量不適合 ' + str(len(unfit)) if unfit else ''}）："
            f"全課題 {n:,} のうち 正解 {tot['正解']:,}・誤答 {tot['誤答']:,}・棄権 {tot['棄権']:,}／"
            f"生まれた型以外への実際の発話 {out_spk:,}（発話の {100 * out_spk / spk if spk else 0:.1f}%）、そこでの誤答 {tot['誤答_生まれた型以外']:,}／"
            f"走行末の席 F {FHU_end[0]:,}・H {FHU_end[1]:,}・U {FHU_end[2]:,}／"
            f"変数の席：選ばれた定義に含まれた {tot['U_選ばれた定義に含まれた']:,}、実際に答えた {tot['U_実際の発話']:,}／"
            f"容量で手放した {summary['容量で手放した件数']:,} 件・空いた {tot['容量で空いたビット']:,} ビット"
            f"（V＜0 で手放した {summary['V負で手放した件数']:,} 件）／定義の退役 {tot['退役']:,}{extra}")
    dest = results / host / arm
    dest.mkdir(parents=True, exist_ok=True)
    (dest / f"v39要約_{arm}.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    md = [f"# {arm}：記憶予算・三段階の忘却（v3.9）の記録の要約（{host}）　判断しない", "",
          "tools/v39_summary.py（仕様 9 節）。数は走行の和。走行ごとの値は v39要約_<腕>.json の「走行ごと」。", "",
          "- " + line[2:], "",
          "| 項目 | 値 |", "|---|---:|"]
    for k, v in summary.items():
        if k in ("走行ごと", "旗"):
            continue
        md.append(f"| {k} | {json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list, tuple)) else v} |")
    md += ["", f"旗：{json.dumps(summary['旗'], ensure_ascii=False)}", ""]
    (dest / f"予算の記録_{arm}.md").write_text("\n".join(md), encoding="utf-8")
    if not no_push:
        subprocess.run([sys.executable, str(REPO / "tools/results_push.py"), str(results), host, arm,
                        f"結果：{host} の {arm} に v3.9 の記録の要約を足す（tools/v39_summary.py）"], check=True)
    print(line)


if __name__ == "__main__":
    main()

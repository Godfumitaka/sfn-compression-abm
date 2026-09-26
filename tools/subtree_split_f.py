"""読むだけ（2026-09-26 午後、アストラさんの指示）：部分木の分け（a）を f ごとに並べる。★ 判定しない。走らせ直しはしない。
腕：v3.1a・v3.1b、NSIM 0.8、f＝0（f00）・0.25（f025）・0.5（hide）・1.0（f10）。seed001〜020・4 セル（クラウドの走行）。
材料
  定義の表：analysis_cloud_v3_2026-09-25/D_spoke/tables/defs_spoke5_<腕>.csv（版 5 の列。世界偽の列だけで、課題〔伏せ辺を当てたか〕の列は無い）
  走行末の生きている行の述語：まとめ（pulled/<腕>*.tar.gz）の side の最後の行（alive_end・last_alive_preds）。hide は _r2（D-32 を直した後の走り直し）。
分け（a）：tools/subtree_split.py と同じ。述語 → 単位（T1〜T4・一番上）は種ファイルから。一つの単位に収まる／二つ以上にまたがる。
見ていない型（版 5）の世界偽の率 ＝ Σ（wf_unseen2 ＋ wf_unseen2_spoke）÷ Σ（n_unseen2 ＋ n_unseen2_spoke）を、分けの中の定義で合計。
外で当たる／外で外す：内（見た＝seen2_spoke＋seen2_quiet）の世界偽 ≤5%、内外とも主張 ≥20 の定義のうち、外（見ていない）≤5% ／ ≥50%。
使い方  python3.12 tools/subtree_split_f.py <出力.md>"""
import collections, csv, io, json, sys, tarfile
from pathlib import Path
B = Path("/Users/tatsu-admin/sfn/sfn-compression-abm")
PULL = B / "analysis_cloud_v3_2026-09-25/pulled"
TAB = B / "analysis_cloud_v3_2026-09-25/D_spoke/tables"
out = sys.argv[1]
seed = json.load(open(B / "seeds/U-011_seed_v3a2.json"))
UNIT = {}


def walk(tname, top):
    node = seed["subtrees"][tname]
    UNIT[node["higher"]] = top
    for c in node.get("subtrees", []):
        walk(c, top)
    for p in node.get("first_order", []):
        UNIT[p] = top


for m, row in seed["motif_structure"].items():
    UNIT[row["third"]] = "一番上"
    for t in row["subtrees"]:
        walk(t, t)

FS = [("f00", "0"), ("f025", "0.25"), ("hide", "0.5"), ("f10", "1.0")]


def pack_of(arm, f):
    name = f"{arm}_{f}_s1"
    cands = sorted(PULL.glob(f"{name}*.tar.gz"))
    cands = [c for c in cands if c.name in (f"{name}.tar.gz", f"{name}_r2.tar.gz")]
    return cands[-1], name          # ★ _r2 があればそれ（名前の並びで最後）


def num(x):
    try: return float(x)
    except (TypeError, ValueError): return 0.0


def alive_preds_of(pack, name):
    tf = tarfile.open(pack)
    sm = [m for m in tf.getmembers() if m.name.endswith("side.tar.gz")][0]
    side = tarfile.open(fileobj=io.BytesIO(tf.extractfile(sm).read()))
    res = {}
    nled = 0
    for m in side.getmembers():
        if not m.name.endswith(".jsonl"):
            continue
        parts = m.name.split("/"); cell, sd = parts[-2], parts[-1].replace(".jsonl", "")
        fin = None
        for line in side.extractfile(m).read().decode().splitlines():
            if '"kind": "final"' in line:
                fin = json.loads(line)
        if fin is None:
            continue
        nled += 1
        for R in fin["alive_end"]:
            res[(cell, sd, R)] = fin["last_alive_preds"].get(R, [])
    return res, nled


rows_out = []
L = ["# 部分木の分け（a）を f ごとに並べる（v3.1a・b、NSIM 0.8、seed001〜020・4 セル）　判定しない", "",
     "★ 分け：走行末の生きている行の述語が、一つの単位（T1〜T4・一番上）に収まる／二つ以上にまたがる。",
     "★ 見ていない型（版 5）の世界偽の率 ＝ 世界偽 ÷（世界偽＋世界真）を、分けの中の定義で合計（括弧は 世界偽／主張）。世界不明は数えない。",
     "★ 課題（伏せ辺を当てたか）の率は、この定義の表（defs_spoke5）に列が無いので出していない。",
     "★ 外で当たる／外で外す：内（見た型）の世界偽 ≤5%、内外とも主張 ≥20 の定義（対象）のうち、外（見ていない型）≤5% ／ ≥50%。",
     "★ 収まる割合 ＝ 通過群（L）の中で、走行末の生存の記録がある定義のうち「一つの部分木」の数 ÷ 全体。", ""]
for arm, lab in (("v31a_n80", "v3.1a"), ("v31b_n80", "v3.1b")):
    L += [f"## {lab}（NSIM 0.8）", ""]
    src = []
    per = {}
    for f, fv in FS:
        pack, name = pack_of(arm, f)
        csvp = TAB / f"defs_spoke5_{name}.csv"
        T = list(csv.DictReader(open(csvp, encoding="utf-8")))
        alive, nled = alive_preds_of(pack, name)
        src.append(f"f={fv}：{csvp.name}（{len(T):,} 定義）・{pack.name} の side（台帳 {nled}）")
        for Lx in (6, 3):
            C = collections.defaultdict(collections.Counter)
            miss = 0
            for r in T:
                if r[f"L{Lx}"] != "1":
                    continue
                cell, sd, R = r["defid"].split("/")
                preds = alive.get((cell, sd, R))
                if preds is None:
                    miss += 1; continue
                units = {UNIT.get(p, "構造外") for p in preds}
                k = "収まる" if len(units) == 1 else "またがる"
                if "構造外" in units:
                    k += "（構造外あり）"
                c = C[k]; c["定義"] += 1
                nu = num(r["n_unseen2"]) + num(r["n_unseen2_spoke"]); wu = num(r["wf_unseen2"]) + num(r["wf_unseen2_spoke"])
                ns = num(r["n_seen2_spoke"]) + num(r["n_seen2_quiet"]); ws = num(r["wf_seen2_spoke"]) + num(r["wf_seen2_quiet"])
                c["nu"] += nu; c["wu"] += wu; c["ns"] += ns; c["ws"] += ws
                c["主張あり"] += nu > 0
                if ns >= 20 and nu >= 20 and ws / ns <= 0.05:
                    c["対象"] += 1
                    ro = wu / nu
                    c["外で当たる"] += ro <= 0.05; c["外で外す"] += ro >= 0.5
            per[(f, Lx)] = (C, miss)
    L += ["材料：" + "／".join(src), ""]
    for Lx in (6, 3):
        L += [f"### L={Lx}", "",
              "| f | 通過（生存の記録あり） | 収まる | 収まる割合 | 見ていない型の世界偽の率：収まる | またがる | 見た型の世界偽の率：収まる | またがる | 外で当たる／外で外す／対象：収まる | またがる |",
              "|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
        for f, fv in FS:
            C, miss = per[(f, Lx)]
            a, s = C["収まる"], C["またがる"]
            other = sum(C[k]["定義"] for k in C if k not in ("収まる", "またがる"))
            tot = a["定義"] + s["定義"] + other
            def rate(c, w, n):
                return f"{c[w]/c[n]:.4f}（{int(c[w]):,}／{int(c[n]):,}）" if c[n] else "—"
            share = f"{a['定義']/tot:.3f}" if tot else "—"
            L.append(f"| {fv} | {tot:,}{'（記録なし ' + str(miss) + '）' if miss else ''} | {a['定義']:,} | {share} | "
                     f"{rate(a,'wu','nu')} | {rate(s,'wu','nu')} | {rate(a,'ws','ns')} | {rate(s,'ws','ns')} | "
                     f"{a['外で当たる']}／{a['外で外す']}／{a['対象']} | {s['外で当たる']}／{s['外で外す']}／{s['対象']} |")
            if other:
                L.append(f"| | ★ 構造外を含む定義 {other}（上の二つに入れていない） | | | | | | | | |")
            rows_out.append({"arm": lab, "f": fv, "L": Lx, "n_pass": tot, "n_contained": a["定義"], "n_spanning": s["定義"],
                             "wf_unseen_contained": int(a["wu"]), "n_unseen_contained": int(a["nu"]),
                             "wf_unseen_spanning": int(s["wu"]), "n_unseen_spanning": int(s["nu"]),
                             "wf_seen_contained": int(a["ws"]), "n_seen_contained": int(a["ns"]),
                             "wf_seen_spanning": int(s["ws"]), "n_seen_spanning": int(s["ns"]),
                             "hit_out_contained": a["外で当たる"], "miss_out_contained": a["外で外す"], "target_contained": a["対象"],
                             "hit_out_spanning": s["外で当たる"], "miss_out_spanning": s["外で外す"], "target_spanning": s["対象"],
                             "no_alive_record": miss})
        L.append("")
Path(out).write_text("\n".join(L) + "\n", encoding="utf-8")
with open(Path(out).with_suffix(".csv"), "w", newline="", encoding="utf-8") as fo:
    w = csv.DictWriter(fo, fieldnames=list(rows_out[0])); w.writeheader(); w.writerows(rows_out)
print("->", out)

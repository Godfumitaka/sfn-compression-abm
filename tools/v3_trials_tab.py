"""v3 の試し 5 版の並べ（2026-09-25 の委任書の項目）。★ 数を並べるだけ。判定しない。
使い方  python3.12 tools/v3_trials_tab.py <出力.md> <版名>:<走行根> ...   （走行根 ＝ analysis_v3_2026-09-25/v_<版名>）
★ 並べるもの
   1 台帳の時間と最大メモリ（manifest の elapsed_sec・peak_rss_mb）
   登録（誕生）と消滅（定義ごと）の数、走行末に生きている定義の数（side の記録）
   走行末の群 S／N／P：生きている定義の、走行末の生存述語（side の last_alive_preds）の 284 組のまたぎで S／N。
     P ＝ lsweep の L=2 を通った生存定義（lsweep.py の注：L=2 の所属は 新θ8 と一致する）。
   またぎを含む定義の割合（走行末に生きている定義のうち）
   中心的過程を通った定義の数（lsweep の L=2〜6、走行末に生きている定義）
   生まれたときの行数の分布（side の誕生の m_alloc）
   行どうしのつながり（台帳の誕生の登録イベントで、引数をほかの行と共有する行の割合）
   定義の土台（登録ごとに、何試行前の枚か、直前と同じモチーフか違うモチーフか）
   外していく生まれ方の記録（2 本未満で作らなかった回、はじめに外した子の無い高階の行）"""
import collections, concurrent.futures, glob, gzip, io, json, os, statistics as st, sys
from pathlib import Path
B = Path("/Users/tatsu-admin/sfn/sfn-compression-abm")
sys.path.insert(0, str(B)); sys.path.insert(0, str(B / "analysis_pred_2026-09-22"))
import grp  # noqa  crossings
from abm.world import _motif_for_trial
M = ("M1", "M2", "M3", "M4")


def share_one(p):
    out = []
    with gzip.open(p, "rt") as f:
        next(f)
        for line in f:
            r = json.loads(line)
            for e in r.get("reg_del_events") or ():
                if e.get("kind") == "registration" and not e.get("was_extension"):
                    cons = e["constituents"]; n = len(cons); s = 0
                    for i, c in enumerate(cons):
                        my = set(c["arguments"])
                        s += any(my & set(d["arguments"]) for j, d in enumerate(cons) if j != i)
                    out.append(s / n)
    return out


def q(xs, p):
    xs = sorted(xs); return xs[min(len(xs) - 1, int(p * (len(xs) - 1) + 0.5))] if xs else None


def main():
    out = Path(sys.argv[1]); specs = [a.split(":", 1) for a in sys.argv[2:]]
    rows = {}
    for name, root in specs:
        root = Path(root)
        man = [json.loads(l) for l in open(root / "manifest.jsonl")]
        el = [m["elapsed_sec"] for m in man if "elapsed_sec" in m]; mem = [m["peak_rss_mb"] for m in man if "peak_rss_mb" in m]
        births = removed = 0; alive_defs = []; bsize = collections.Counter(); age = collections.Counter(); same = diff = 0
        prune_none = prune_all = childless = 0; ledgers = 0
        for side in sorted(root.glob("side/*/seed*.jsonl")):
            cell = side.parent.name; seed_i = int(side.stem[4:]); ledgers += 1
            fin = None
            for line in open(side):
                d = json.loads(line); k = d["kind"]
                if k == "birth":
                    births += 1; bsize[d.get("m_alloc")] += 1
                if k in ("birth", "assim") and d.get("base_written_at") is not None:
                    a = d["trial"] - d["base_written_at"]; age[a] += 1
                    if _motif_for_trial(seed_i, d["trial"], M) == _motif_for_trial(seed_i, d["base_written_at"], M): same += 1
                    else: diff += 1
                if k == "prune":
                    prune_all += 1; prune_none += d.get("result") == "none"; childless += d.get("childless_dropped_at_start", 0)
                if k == "final":
                    fin = d
            removed += fin["removed_defs"]
            for R in fin["alive_end"]:
                alive_defs.append((cell, f"seed{seed_i:03d}", R, fin["last_alive_preds"].get(R, [])))
        lsf = B / f"analysis_pred_2026-09-22/lsweep_v3t_{name}.json"
        passes = {Lx: set() for Lx in (2, 3, 4, 5, 6)}
        if lsf.exists():
            for x in json.load(open(lsf))["台帳"]:
                for R, v in x["定義"].items():
                    for Lx in v.get("pass", []):
                        passes[Lx].add((x["cell"], x["seed"], R))
        alive_keys = {(c, s, R) for c, s, R, _ in alive_defs}
        grpc = collections.Counter(); mat = 0
        for c, s, R, preds in alive_defs:
            cr = grp.crossings(preds) >= 1; mat += cr
            grpc["P" if (c, s, R) in passes[2] else ("S" if cr else "N")] += 1
        ledgers_gz = sorted(glob.glob(str(root / "ledgers/cells/*/seed*.jsonl.gz")))
        with concurrent.futures.ProcessPoolExecutor(max_workers=8) as ex:
            shares = [x for lst in ex.map(share_one, ledgers_gz) for x in lst]
        rows[name] = dict(ledgers=ledgers, el=el, mem=mem, births=births, removed=removed, alive=len(alive_defs), grp=grpc,
                          mat=mat, central={Lx: len(passes[Lx] & alive_keys) for Lx in passes}, ls=lsf.exists(),
                          bsize=bsize, shares=shares, age=age, same=same, diff=diff,
                          prune=(prune_all, prune_none, childless))
    names = [n for n, _ in specs]
    L = ["# v3 の試し 5 版の並べ（判定しない）", "",
         "★ b2_hide_s1（f=0.5）の 4 セル（θ′ 2.1/2.3 × most_frequent/sample）× seed001〜005、各版 20 台帳。同じマック・並列 8・--lowmem（出力は同じ）。",
         "★ 版：allpairs2＝生まれ方は全部取る（--nohash --vt 0.3842）／main＝v3 の主（＋--greedy）／nsim08＝主で NSIM 0.8／vt1＝主で逐語 1 試行（v2 と同じ）／vt01432＝主で逐語 0.1432。", ""]
    L.append("| | " + " | ".join(names) + " |"); L.append("|---|" + "---:|" * len(names))
    def line(t, f): L.append(f"| {t} | " + " | ".join(f(rows[n]) for n in names) + " |")
    line("台帳", lambda r: f"{r['ledgers']}")
    line("1 台帳の時間 中央（最大）秒", lambda r: f"{st.median(r['el']):.0f}（{max(r['el']):.0f}）")
    line("1 台帳の最大メモリ 中央（最大）MB", lambda r: f"{st.median(r['mem']):.0f}（{max(r['mem']):.0f}）")
    line("登録（誕生）", lambda r: f"{r['births']:,}")
    line("消滅（定義ごと）", lambda r: f"{r['removed']:,}")
    line("走行末に生きている定義", lambda r: f"{r['alive']:,}")
    for g in ("S", "N", "P"):
        line(f"　群{g}", lambda r, g=g: f"{r['grp'][g]:,}")
    line("またぎを含む定義の割合（走行末に生存）", lambda r: f"{r['mat']/r['alive']:.3f}" if r['alive'] else "—")
    for Lx in (2, 3, 4, 5, 6):
        line(f"中心的過程 L={Lx}（走行末に生存）", lambda r, Lx=Lx: f"{r['central'][Lx]:,}" if r["ls"] else "（lsweep 無し）")
    line("生まれたときの行数 中央（p10〜p90）", lambda r: (lambda xs: f"{st.median(xs)}（{q(xs,.1)}〜{q(xs,.9)}）")([k for k, v in r['bsize'].items() for _ in range(v)]) if r['births'] else "—")
    line("引数を共有する行の割合（誕生時） 平均（中央）", lambda r: f"{st.mean(r['shares']):.3f}（{st.median(r['shares']):.3f}）" if r['shares'] else "—")
    line("土台の枚：何試行前 中央（最大）", lambda r: (lambda xs: f"{st.median(xs)}（{max(xs)}）")([k for k, v in r['age'].items() for _ in range(v)]))
    line("土台の枚：1 試行前の割合", lambda r: f"{r['age'][1]/sum(r['age'].values()):.3f}")
    line("土台と今の場面：同じモチーフの割合", lambda r: f"{r['same']/(r['same']+r['diff']):.3f}")
    line("外していく処理：回数／2 本未満で作らず／はじめに外した子の無い高階（延べ）", lambda r: f"{r['prune'][0]:,}／{r['prune'][1]:,}／{r['prune'][2]:,}")
    L.append(""); L.append("## 生まれたときの行数の分布（本数：定義の数）"); L.append("")
    for n in names:
        L.append(f"- {n}：" + "、".join(f"{k}:{v}" for k, v in sorted(rows[n]["bsize"].items())))
    L.append(""); L.append("## 土台の枚が何試行前か（試行差：登録の数）"); L.append("")
    for n in names:
        L.append(f"- {n}：" + "、".join(f"{k}:{v}" for k, v in sorted(rows[n]["age"].items())[:12]) + ("…" if len(rows[n]["age"]) > 12 else ""))
    L += ["", "★ 群は走行末の生存定義だけで数えた（途中で消えた定義は入れていない）。群 P は lsweep の L=2（新θ8 と一致）で、rows2・newlabelR は作っていない。",
          "★ 土台の「何試行前」は、枚の番号（書込番号）と登録試行の差。枚が毎試行一枚ずつ積まれるので、試行差と同じ。"]
    out.write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"-> {out}")


if __name__ == "__main__":
    main()

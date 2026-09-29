"""B＋E（--v310-be）の腕ごとの要約と control/ の一行（委任書「B＋E（書き直しの費用で結ぶ統合版）」の 3）。★ 判断しない。台帳と side を読むだけ。
一行に書くもの：
  全課題を分母にした正解・誤答・棄権（台帳の coverage・hit。tools/v39_summary.py と同じ数え方）
  誤答の出どころ（F の投影・F の穴埋め・H の穴埋め・U の穴埋め。tools/v39_miss_source.py と同じ決め方）
  生まれた型以外での発話と誤答（merged/defs_spoke8org_<腕>.csv の born_motif。tools/def_origin.py）
  走行末の定義の数（side の final の alive_end。20 本の和と中央値）・誕生と同化の数（side の birth・assim）
  型またぎの同化（同化した定義の生まれた型 ≠ 同化した試行の型）の数を、型の組（生まれた型→場面の型）ごとに
  不在が確かめられずに取消を数えなかった件数（採った候補の「取消の未確認」の席の和）・同化したが一致が 0 だった件数
  λC と R の走行末の値（C＝各試行の終わりの総費用、R＝採った候補の書換ビット r の累計＋B の採点の書換ビットの累計。20 本の中央値）
走行ごとの推移（試行・C・R_E の累計・R_B の累計・λC＋R）は <結果>/<機械>/<腕>/be推移_<腕>.csv.gz に書く。
使い方  python3.12 tools/v310be_summary.py <腕の走行根> <腕名> <結果の作業場所> <機械の名前>   （一行を標準出力の最後に出す）"""
import collections
import csv
import glob
import gzip
import json
import os
import statistics
import sys
from multiprocessing import Pool
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "tools"))
from v39_miss_source import one as miss_one  # noqa: E402
from v39_summary import motifs  # noqa: E402


def side_one(args):
    side, lam, seedf, header = args
    MOT = motifs(header, seedf)
    births = assims = 0
    born = {}                     # 名前 → 生まれた試行（いまの同一性）
    cross = collections.Counter()
    unconf = match0 = 0
    final_defs = None
    RE = RB = 0.0
    series = []
    for line in open(side, encoding="utf-8"):
        d = json.loads(line)
        k = d.get("kind")
        if k == "birth":
            births += 1
            born[d["R"]] = d["trial"]
        elif k == "assim":
            assims += 1
            b = born.get(d["R"])
            if b is not None and MOT[b] != MOT[d["trial"]]:
                cross[f"{MOT[b]}→{MOT[d['trial']]}"] += 1
        elif k == "final":
            final_defs = len(d.get("alive_end") or [])
        elif k == "v310be":
            RE += d.get("R_E") or 0.0
            RB += d.get("R_B") or 0.0
            c0 = (d.get("cands") or [None])[0]
            if d.get("chosen") is not None and c0 and c0[0] == d["chosen"]:
                unconf += c0[5].get("取消の未確認", 0)
                match0 += c0[5].get("一致") == 0
            if d.get("C_end") is not None:
                series.append((d["trial"], d["C_end"], RE, RB, lam * d["C_end"] + RE + RB))
    return {"births": births, "assims": assims, "cross": cross, "unconf": unconf, "match0": match0,
            "final_defs": final_defs, "C_end": series[-1][1] if series else None, "R_end": RE + RB, "RE": RE, "RB": RB,
            "series": series}


def main():
    root, arm, results, host = Path(sys.argv[1]), sys.argv[2], Path(sys.argv[3]), sys.argv[4]
    fl = json.load(open(root / "flag.json", encoding="utf-8"))
    lam = float(fl.get("v39_price") or 0.0)
    cfg = json.load(open(REPO / fl["config"], encoding="utf-8"))
    seedf = str(REPO / cfg.get("seed_file", "seeds/U-011_seed_v3a2.json"))
    inc = collections.defaultdict(lambda: collections.defaultdict(list))
    for row in csv.DictReader(open(root / "merged" / f"defs_spoke8org_{arm}.csv", encoding="utf-8")):
        cell, seed, K = row["defid"].split("/")
        R, b = K.rsplit("@", 1)
        died = row.get("died")
        inc[(cell, seed)][R].append((int(b), int(died) if died not in (None, "") else None, row.get("born_motif") or None))
    jobs, sjobs, keys = [], [], []
    tasks = collections.Counter()
    for p in sorted(glob.glob(str(root / "ledgers/cells/*/seed*.jsonl.gz"))):
        cell = os.path.basename(os.path.dirname(p))
        sd = os.path.basename(p)[:7]
        if not os.path.exists(p[:-len(".jsonl.gz")] + ".done"):
            continue
        side = str(root / "side" / cell / f"{sd}.jsonl")
        with gzip.open(p, "rt", encoding="utf-8") as f:
            header = json.loads(next(f))
        jobs.append((p, side, dict(inc[(cell, sd)]), seedf))
        sjobs.append((side, lam, seedf, header))
        keys.append((cell, sd))
        tasks[(cell, sd)] = header["trial_count"]
    with Pool(4) as pool:
        mres = pool.map(miss_one, jobs)
        sres = pool.map(side_one, sjobs)
    M = collections.Counter()
    for _, c in mres:
        M.update(c)
    n = sum(tasks.values())
    spk = sum(v for k, v in M.items() if k[0] == "発話")
    miss = sum(v for k, v in M.items() if k[0] == "誤答")
    src = ("F の投影", "F の穴埋め", "H の穴埋め", "U の穴埋め", "分からない")
    cross = collections.Counter()
    for s in sres:
        cross.update(s["cross"])
    tot = {k: sum(s[k] for s in sres) for k in ("births", "assims", "unconf", "match0")}
    defs = [s["final_defs"] for s in sres if s["final_defs"] is not None]
    Cend = [s["C_end"] for s in sres if s["C_end"] is not None]
    Rend = [s["R_end"] for s in sres]
    summary = {
        "腕": arm, "走行": len(sres), "λ": lam, "U": fl.get("v39_u"), "課題": n, "正解": spk - miss, "誤答": miss, "棄権": n - spk,
        "誤答の出どころ": {s: M.get(("誤答", s), 0) for s in src}, "発話の出どころ": {s: M.get(("発話", s), 0) for s in src},
        "生まれた型以外への発話": sum(M.get(("発話_生まれた型以外", s), 0) for s in src),
        "生まれた型以外での誤答": sum(M.get(("誤答_生まれた型以外", s), 0) for s in src),
        "生まれた型が分からない発話": sum(M.get(("発話_型が分からない", s), 0) for s in src),
        "走行末の定義の数（和）": sum(defs), "走行末の定義の数（中央値）": statistics.median(defs) if defs else None,
        "誕生": tot["births"], "同化": tot["assims"], "型またぎの同化": sum(cross.values()),
        "型またぎの同化（型の組ごと）": dict(sorted(cross.items())),
        "不在が確かめられず取消を数えなかった席": tot["unconf"], "同化したが一致が 0": tot["match0"],
        "C の走行末（中央値）": statistics.median(Cend) if Cend else None, "R の走行末（中央値）": statistics.median(Rend) if Rend else None,
        "λC＋R の走行末（中央値）": statistics.median([lam * c + r for c, r in zip(Cend, Rend)]) if Cend else None,
        "走行ごと": [{"セル": k[0], "種": k[1], **{x: s[x] for x in ("births", "assims", "final_defs", "C_end", "R_end", "RE", "RB",
                                                                 "unconf", "match0")}} for k, s in zip(keys, sres)],
    }
    dest = results / host / arm
    dest.mkdir(parents=True, exist_ok=True)
    (dest / f"be要約_{arm}.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    with gzip.open(dest / f"be推移_{arm}.csv.gz", "wt", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["cell", "seed", "trial", "C", "R_E_cum", "R_B_cum", "lamC_plus_R"])
        for k, s in zip(keys, sres):
            for row in s["series"]:
                w.writerow([k[0], k[1], *row])
    ms = summary["誤答の出どころ"]
    pairs = "・".join(f"{k} {v:,}" for k, v in summary["型またぎの同化（型の組ごと）"].items()) or "なし"
    line = (f"- {arm}（λ＝{lam}{'、U 棄権' if fl.get('v39_u') == 'abstain' else ''}、走行 {len(sres)}）："
            f"全課題 {n:,} のうち 正解 {summary['正解']:,}・誤答 {miss:,}・棄権 {summary['棄権']:,}／"
            f"誤答の出どころ F の投影 {ms['F の投影']:,}・F の穴埋め {ms['F の穴埋め']:,}・H の穴埋め {ms['H の穴埋め']:,}・U の穴埋め {ms['U の穴埋め']:,}"
            f"{'・分からない ' + format(ms['分からない'], ',') if ms['分からない'] else ''}／"
            f"生まれた型以外への発話 {summary['生まれた型以外への発話']:,}、そこでの誤答 {summary['生まれた型以外での誤答']:,}／"
            f"走行末の定義 和 {sum(defs):,}（中央値 {summary['走行末の定義の数（中央値）']}）／誕生 {tot['births']:,}・同化 {tot['assims']:,}／"
            f"型またぎの同化 {sum(cross.values()):,}（{pairs}）／不在が確かめられず取消を数えなかった席 {tot['unconf']:,}／"
            f"同化したが一致 0 {tot['match0']:,}／走行末（中央値）C {summary['C の走行末（中央値）']:,}・R {summary['R の走行末（中央値）']:,.1f}・"
            f"λC＋R {summary['λC＋R の走行末（中央値）']:,.1f}")
    print(line)


if __name__ == "__main__":
    main()

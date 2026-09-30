"""U の照合の直しの影響を軽く見る短い走行（2026-09-30 の委任書「U の照合の直し…」の 5）の腕ごとの一行。★ 数えるだけ。判断しない。
腕の走行根の、台帳（ledgers）・side（kind＝v39）・答えごとの記録（side/*.answers.csv）を読む。
  正解・誤答・棄権：台帳の coverage・hit（全課題を分母）。
  誤答の出どころ：答えごとの記録の source（F_proj・F_fill・H_fill・U_fill）。
  覚え直し：side の v39 の記録の acc.relearn（会計）と m1.relearn_m1（登録）の U→H。
    すぐ忘れた＝同じ試行の変換（conv）で、同じ席が H→U になったもの。10 試行以内＝覚え直しから 10 試行以内に H→U になったもの（同じ試行を含む）。
  支持の三分類の平均：答えごとの記録の sel_vis・sel_hid・sel_none・sel_vis_match（実際に答えた試行の、選ばれた定義）。
  門を通った回数：台帳の R_used が空でない試行。
使い方  python3.12 tools/histrole_checks/u_short_summary.py <腕の走行根> <腕名>   （一行を標準出力に。数は種の和）"""
import collections
import csv
import glob
import gzip
import json
import os
import sys


def main():
    root, arm = sys.argv[1], sys.argv[2]
    C = collections.Counter()
    tri = collections.Counter()
    nans = 0
    runs = 0
    for led in sorted(glob.glob(f"{root}/ledgers/cells/*/seed*.jsonl.gz")):
        if not os.path.exists(led[:-len(".jsonl.gz")] + ".done"):
            continue
        runs += 1
        cell = os.path.basename(os.path.dirname(led))
        sd = os.path.basename(led)[:-len(".jsonl.gz")]
        with gzip.open(led, "rt", encoding="utf-8") as f:
            next(f)
            for line in f:
                r = json.loads(line)
                if r.get("record_type", "trial") != "trial":
                    continue
                C["課題"] += 1
                C["正解" if r.get("coverage") == 1 and r.get("hit") == 1 else "誤答" if r.get("coverage") == 1 else "棄権"] += 1
                C["門を通った"] += r.get("R_used") is not None
        relearn, hu = [], collections.defaultdict(list)
        for line in open(f"{root}/side/{cell}/{sd}.jsonl", encoding="utf-8"):
            d = json.loads(line)
            if d.get("kind") != "v39":
                continue
            t = d["trial"]
            for ev in ((d.get("acc") or {}).get("relearn") or []) + (((d.get("m1") or {}).get("relearn_m1")) or []):
                relearn.append((t, ev["R"], ev["slot"]))
            for c in d.get("conv") or []:
                if c[0] == "HU":
                    hu[(c[1], c[2])].append(t)
        for t, R, s in relearn:
            C["覚え直し"] += 1
            later = [x for x in hu.get((R, s), []) if x >= t]
            C["覚え直し_同じ試行で忘れた"] += bool(later and later[0] == t)
            C["覚え直し_10試行以内に忘れた"] += bool(later and later[0] - t <= 10)
        af = f"{root}/side/{cell}/{sd}.answers.csv"
        if os.path.exists(af):
            for r in csv.DictReader(open(af, encoding="utf-8")):
                if r["hit"] != "1":
                    C[f"誤答_{r['source']}"] += 1
                if r.get("sel_vis", "") != "":
                    nans += 1
                    for k in ("sel_vis", "sel_hid", "sel_none", "sel_vis_match"):
                        tri[k] += int(r[k])
    g = C.get
    m = lambda k: (tri[k] / nans) if nans else 0.0  # noqa: E731
    line = (f"- {arm}（走行 {runs}）：全課題 {g('課題', 0):,} のうち 正解 {g('正解', 0):,}・誤答 {g('誤答', 0):,}・棄権 {g('棄権', 0):,}"
            f"／誤答の出どころ F の投影 {g('誤答_F_proj', 0):,}・F の穴埋め {g('誤答_F_fill', 0):,}・H の穴埋め {g('誤答_H_fill', 0):,}・U の穴埋め {g('誤答_U_fill', 0):,}"
            f"／覚え直し {g('覚え直し', 0):,}（同じ試行で忘れた {g('覚え直し_同じ試行で忘れた', 0):,}・10 試行以内に忘れた {g('覚え直し_10試行以内に忘れた', 0):,}）"
            f"／支持の三分類の平均（答えた試行 {nans:,}、選ばれた定義の F・H の席）見えている関係 {m('sel_vis'):.2f}・伏せられた位置 {m('sel_hid'):.2f}・対応先なし {m('sel_none'):.2f}"
            f"（見えている関係のうち名前が一致 {m('sel_vis_match'):.2f}）／門を通った {g('門を通った', 0):,}")
    print(line)


if __name__ == "__main__":
    main()

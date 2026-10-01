"""定義の本数と手放された定義（2026-10-01 夕方の返事の 1：腕ごとの記録）。★ 読むだけ。
試行ごとの定義の本数（各試行の終わりの状態。20 走行の全試行の中央値と最大）、手放された定義の数（前の試行の終わりにあって、次の試行の終わりに無い
（定義名・登録試行）の数）、走行の終わりの定義の本数。
腕 F で定義が積み上がる理由の確かめ：走行の終わりの定義を、守られた席（シール・link：tools/shopworld.py の IDS にある関係 ID の行）を
  持つか、そして守られた席以外の席がすべて U か（＝守られた席だけが U でない定義）で分けて数える。
  席の状態：F は生きている行、H は墓石で履歴の欄がある、U は墓石で欄が無い（tools/v39.py seat_state）。
使い方  python3.12 tools/defcount.py <出力の .json> <腕の根> …   （並列は環境変数 DC_WORKERS、既定 2）"""
import glob
import json
import os
import sys
from collections import Counter
from multiprocessing import Pool

W = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [os.path.join(W, "tools"), W]


def one(args):
    root, cell, seed = args
    from extrap_reader import iter_run
    import shopworld as sw
    counts, released, prev = [], 0, None
    last = None
    for tr in iter_run(root, cell, seed, check_hash=False):
        post = tr["post"]
        cur = {(d["name"], d["registered_at"]) for d in post["definitions"].values()}
        counts.append(len(cur))
        if prev is not None:
            released += len(prev - cur)
        prev = cur
        last = post
    hk = set(last["slot_history"])
    kinds = Counter()
    for d in last["definitions"].values():
        prot, other = [], []
        for c in d["constituents"]:
            st = "F" if c["alive"] else ("H" if str((d["name"], c["slot_index"])) in hk else "U")
            (prot if c["relation"]["relation_id"] in sw.IDS else other).append(st)
        if not prot:
            kinds["守られた席なし"] += 1
        elif all(s == "U" for s in other):
            kinds["守られた席あり・ほかの席はすべて U"] += 1
        else:
            kinds["守られた席あり・ほかに U でない席がある"] += 1
    return {"seed": seed, "counts": counts, "released": released, "end": counts[-1], "end_kinds": dict(kinds)}


def main():
    out = sys.argv[1]
    res = {}
    for root in sys.argv[2:]:
        jobs = [(root, os.path.basename(os.path.dirname(p)), int(os.path.basename(p)[4:7]))
                for p in sorted(glob.glob(os.path.join(root, "ledgers/cells/*/seed*.done"))) if 1 <= int(os.path.basename(p)[4:7]) <= 20]
        with Pool(int(os.environ.get("DC_WORKERS", "2"))) as pool:
            runs = pool.map(one, jobs)
        allc = sorted(c for r in runs for c in r["counts"])
        k = Counter()
        for r in runs:
            k.update(r["end_kinds"])
        res[os.path.basename(root)] = {"走行": len(runs), "試行ごとの定義の本数 中央値": allc[len(allc) // 2], "最大": allc[-1],
                                      "手放された定義（20 走行の和）": sum(r["released"] for r in runs),
                                      "走行の終わりの定義の本数（和）": sum(r["end"] for r in runs), "走行の終わりの定義の内訳": dict(k)}
        print(os.path.basename(root), json.dumps(res[os.path.basename(root)], ensure_ascii=False), flush=True)
    json.dump(res, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()

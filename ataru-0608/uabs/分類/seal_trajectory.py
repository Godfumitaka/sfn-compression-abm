"""段 3 の 3：シールの席の状態の推移（記録を読むだけ）。使い方：seal_trajectory.py <腕の置き場所> <試行ごとの表 trials.tsv.gz> …（組で渡す）
通常の定義：誕生の試行の場面と土台の場面が、どちらも甲・通常の日（試行ごとの表の shop_type＝甲・shop_cue＝n）の定義（仮の決定）。
  誕生の記録：side/<セル>/seed<種>.jsonl(.gz) の kind＝birth（試行・定義の名前・土台の試行）。定義は（名前, 生まれた試行）で見分ける。
シールの席の状態：side/<セル>/seed<種>.shop.jsonl の kind＝shop_seat・which＝sig の変化（生まれた・F→H・H→U・U→H・定義ごと消えた）。
  生まれた直後＝誕生の試行の終わりの状態（その試行の最後の変化の行き先）。走行の終わり＝最後の変化の行き先（定義ごと消えたなら「定義が消えた」）。
  シールの席が二つ以上ある定義は、席ごとに数える。シールの席が無い通常の定義は「シールの席なし」として別に数える。
  名前：F・H の席の名前は、shop.jsonl には無いので数えない（状態だけ）。"""
import glob
import gzip
import json
import os
import sys
from collections import Counter


def opn(p):
    return gzip.open(p, "rt", encoding="utf-8") if p.endswith(".gz") else open(p, encoding="utf-8")


args = sys.argv[1:]
print("| 腕 | 通常の定義 | シールの席なし | シールの席 | 生まれた直後 F・H・U・消えた | 走行の終わり F・H・U・定義が消えた |")
print("|---|---:|---:|---:|---|---|")
for root, tab in zip(args[::2], args[1::2]):
    arm = os.path.basename(root.rstrip("/"))
    TR = {}
    with gzip.open(tab, "rt", encoding="utf-8") as f:
        next(f)
        for line in f:
            x = line.rstrip("\n").split("\t")
            TR[(int(x[0]), int(x[1]))] = (x[6], x[7])
    n_def = n_noseal = 0
    first = Counter()
    last = Counter()
    for sp in sorted(glob.glob(f"{root}/side/*/seed*.shop.jsonl*")):
        seed = int(os.path.basename(sp)[4:7])
        sdir = os.path.dirname(sp)
        sj = next(p for p in (f"{sdir}/seed{seed:03d}.jsonl", f"{sdir}/seed{seed:03d}.jsonl.gz") if os.path.exists(p))
        births = set()
        for line in opn(sj):
            r = json.loads(line)
            if r.get("kind") == "birth":
                b = r.get("base_written_at")
                if TR[(seed, r["trial"])] == ("甲", "n") and b is not None and TR[(seed, b)] == ("甲", "n"):
                    births.add((r["R"], r["trial"]))
        ev = {}
        for line in opn(sp):
            r = json.loads(line)
            if r.get("kind") == "shop_seat" and r.get("which") == "sig":
                ev.setdefault((r["R"], r["reg"], r["slot"]), []).append((r["trial"], r["to"]))
        seated = {(k[0], k[1]) for k in ev}
        n_def += len(births)
        n_noseal += len(births - seated)
        for k, es in ev.items():
            if (k[0], k[1]) not in births:
                continue
            born = k[1]
            st0 = None
            for t, to in es:
                if t == born:
                    st0 = to
            first["消えた" if st0 not in ("F", "H", "U") else st0] += 1
            to = es[-1][1]
            last["定義が消えた" if to not in ("F", "H", "U") else to] += 1
    n = sum(first.values())

    def pc(c, keys):
        return "・".join(f"{c[k]:,}（{c[k] / n:.1%}）" if n else "0" for k in keys)
    print(f"| {arm} | {n_def:,} | {n_noseal:,} | {n:,} | {pc(first, ('F', 'H', 'U', '消えた'))} | {pc(last, ('F', 'H', 'U', '定義が消えた'))} |")

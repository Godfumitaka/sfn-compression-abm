"""仕組みの表（台帳 D-07τ の M1〜M6）を、一本の出力から作る。

使い方: python3 mtable.py <出力の根> [<出力の根> ...]
  出力の根の下に、side/<cell>/seedNNN.jsonl（又は .jsonl.gz）、stage2/<cell>/seedNNN.jsonl.gz、
  manifest.jsonl、time.log（あれば）がある形。
読むのは研究者の記録だけで、成績（hit・accuracy）は読まない。
"""
import glob
import gzip
import json
import os
import re
import sys


def _open(p):
    return gzip.open(p, "rt") if p.endswith(".gz") else open(p)


def _first(root, pattern):
    hits = sorted(glob.glob(os.path.join(root, pattern)))
    return hits[0] if hits else None


def _conv_def(item):
    if isinstance(item, dict):
        return item.get("R")
    if isinstance(item, (list, tuple)) and item:
        return item[0]
    return None


def one_run(root):
    out = {"root": root}
    side = _first(root, "side/*/seed*.jsonl") or _first(root, "side/*/seed*.jsonl.gz")
    defs_by_trial = {}
    births = 0
    retires = 0
    multi_conv = 0
    conv_total = 0
    if side:
        with _open(side) as f:
            for line in f:
                d = json.loads(line)
                k = d.get("kind")
                if k == "v39":
                    t = d["trial"]
                    defs_by_trial[t] = d.get("defs")
                    retires += len(d.get("retire") or [])
                    per_def = {}
                    for c in d.get("conv") or []:
                        r = _conv_def(c)
                        per_def[r] = per_def.get(r, 0) + 1
                        conv_total += 1
                    multi_conv += sum(1 for n in per_def.values() if n >= 2)
                elif k == "birth":
                    births += 1
    trials = sorted(defs_by_trial)
    after = [defs_by_trial[t] for t in trials if t >= 200 and defs_by_trial[t] is not None]
    out["M1_trials"] = len(trials)
    out["M1_frac_le1_from200"] = (sum(1 for v in after if v <= 1) / len(after)) if after else None
    if after:
        s = sorted(after)
        out["M1_defs_from200_min_med_max"] = [s[0], s[len(s) // 2], s[-1]]
    out["M1_defs_final"] = defs_by_trial[trials[-1]] if trials else None
    out["M1_defs_every100"] = [defs_by_trial[t] for t in trials if t % 100 == 99]
    out["M3_births"] = births
    out["M3_retirements"] = retires
    out["M4_same_def_multi_conv"] = multi_conv
    out["conversions_total"] = conv_total

    s2 = _first(root, "stage2/*/seed*.jsonl.gz")
    zero = neg = pos = 0
    disclosed = 0
    if s2:
        with _open(s2) as f:
            for line in f:
                d = json.loads(line)
                rows = d.get("rows") or []
                if rows:
                    disclosed += 1
                for r in rows:
                    x = r.get("delta")
                    if x is None:
                        continue
                    if abs(x) < 1e-12:
                        zero += 1
                    elif x < 0:
                        neg += 1
                    else:
                        pos += 1
    n = zero + neg + pos
    out["M2_disclosed_trials"] = disclosed
    out["M2_seats"] = n
    out["M2_zero_neg_pos"] = [round(zero / n, 4), round(neg / n, 4), round(pos / n, 4)] if n else None

    man = os.path.join(root, "manifest.jsonl")
    if os.path.exists(man):
        with open(man) as f:
            m = json.loads(f.readline())
        out["M5_elapsed_sec"] = m.get("elapsed_sec")
        out["final_def_count"] = m.get("final_def_count")
    tl = os.path.join(root, "time.log")
    if os.path.exists(tl):
        txt = open(tl).read()
        mm = re.search(r"Maximum resident set size \(kbytes\): (\d+)", txt)
        if mm:
            out["M5_peak_rss_mb"] = round(int(mm.group(1)) / 1024, 1)
    out["M6"] = "NA（本番では記録しない。較正の参考値を併記、R-07l）"
    return out


if __name__ == "__main__":
    for root in sys.argv[1:]:
        print(json.dumps(one_run(root), ensure_ascii=False))

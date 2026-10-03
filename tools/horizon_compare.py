"""時間の幅の旗の関門の比べ（委任書 2026-10-03）。★ 台帳と side を読むだけ。
関門 1：<a> と <b> の台帳（ledgers/cells/*/seed*.jsonl.gz を展開した中身）と side（side/ の下の全ファイル）が一字一句同じか。
関門 2：<b>（T＝1,740）と <c>（T＝3,480）の台帳の試行の行を、prediction_order が 0〜1,739 の範囲で比べる。食い違う欄を全部数えて書く
  （欄ごとの食い違いの行数と最初の試行）。見出しの行も欄ごとに比べる。
使い方  python3.12 tools/horizon_compare.py gate1 <a の根> <b の根>
        python3.12 tools/horizon_compare.py gate2 <b の根> <c の根> <T>"""
import glob
import gzip
import hashlib
import json
import os
import sys
from collections import Counter


def ledger(root):
    ps = sorted(glob.glob(os.path.join(root, "ledgers/cells/*/seed*.jsonl.gz")))
    assert len(ps) == 1, ps
    return ps[0]


def sha(path, gz=False):
    h = hashlib.sha256()
    with (gzip.open(path, "rb") if gz else open(path, "rb")) as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def gate1(a, b):
    out = {"台帳（展開した中身の sha256）": {}, "side": {}}
    la, lb = ledger(a), ledger(b)
    out["台帳（展開した中身の sha256）"] = {"a": sha(la, True), "b": sha(lb, True)}
    out["台帳が同じ"] = out["台帳（展開した中身の sha256）"]["a"] == out["台帳（展開した中身の sha256）"]["b"]
    fa = sorted(os.path.relpath(p, os.path.join(a, "side")) for p in glob.glob(os.path.join(a, "side", "**", "*"), recursive=True) if os.path.isfile(p))
    fb = sorted(os.path.relpath(p, os.path.join(b, "side")) for p in glob.glob(os.path.join(b, "side", "**", "*"), recursive=True) if os.path.isfile(p))
    out["side のファイルの並びが同じ"] = fa == fb
    diff = []
    for f in sorted(set(fa) | set(fb)):
        pa, pb = os.path.join(a, "side", f), os.path.join(b, "side", f)
        ha = sha(pa) if os.path.exists(pa) else None
        hb = sha(pb) if os.path.exists(pb) else None
        out["side"][f] = ha == hb
        if ha != hb:
            diff.append(f)
    out["side の食い違うファイル"] = diff
    out["side のファイルの数"] = len(set(fa) | set(fb))
    out["関門 1"] = out["台帳が同じ"] and not diff and out["side のファイルの並びが同じ"]
    return out


def rows(path, T):
    with gzip.open(path, "rt", encoding="utf-8") as f:
        head = json.loads(next(f))
        body = []
        for line in f:
            r = json.loads(line)
            if r.get("record_type", "trial") == "trial" and r["prediction_order"] >= T:
                break
            body.append((line, r))
    return head, body


def gate2(b, c, T):
    hb, rb = rows(ledger(b), T)
    hc, rc = rows(ledger(c), T)
    out = {"見出しの食い違う欄": sorted(k for k in set(hb) | set(hc) if hb.get(k) != hc.get(k)),
           "見出しの値": {k: [hb.get(k), hc.get(k)] for k in set(hb) | set(hc) if hb.get(k) != hc.get(k) and k not in ("world_hash",)},
           "行の数": [len(rb), len(rc)]}
    cnt, first = Counter(), {}
    same_text = 0
    for (lb, xb), (lc, xc) in zip(rb, rc):
        if lb == lc:
            same_text += 1
            continue
        for k in set(xb) | set(xc):
            if xb.get(k) != xc.get(k):
                cnt[k] += 1
                first.setdefault(k, xb.get("prediction_order"))
    out["一字一句同じ行"] = same_text
    out["食い違う欄（行数・最初の試行）"] = {k: [cnt[k], first[k]] for k in sorted(cnt, key=lambda k: first[k])}
    return out


def main():
    mode = sys.argv[1]
    if mode == "gate1":
        res = gate1(sys.argv[2], sys.argv[3])
    else:
        res = gate2(sys.argv[2], sys.argv[3], int(sys.argv[4]))
    print(json.dumps(res, ensure_ascii=False, indent=1, default=str))


if __name__ == "__main__":
    main()

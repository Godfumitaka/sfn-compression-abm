"""出どころ別の、見ていない型での誤りの率（2026-09-27 夜、アストラさんの指示 3）。★ 判断しない。台帳は読まない（走らせ直しも要らない）。
腕のまとめ（tools/prod_arm_done.py）が作った <腕の走行根>/merged/l2s8_<腕>.json（走査の版 8 の定義ごとの数）と、
定義の表 <腕の走行根>/merged/defs_spoke8_<腕>.csv から、定義ごとに列を足した表と、通過群の集計を作る。

足す列（出どころ s ＝ proj（投影）・fill_live（生きている行の穴埋め）・fill_tomb（墓石の穴埋め）ごと）
  n_unseen2_<s>   見ていない型（版 5 の「見ていない・話していない」＋「見ていない・話した」）の主張のうち、世界偽＋世界真（言い直しを除く）
  wf_unseen2_<s>  そのうち世界偽
  rate_unseen2_<s> wf ÷ n（n＝0 なら空）
  rs_unseen2_<s>  見ていない型の言い直しの数（v3.5 では 0 のはず）
  走査の版 8 の数え：出どころ × 版 5 の四つの分け × 世界偽・世界真・言い直し（キー「源投影五未見未話_世界偽」など、tools/l2scan_spoke_v8.py の sk+"五"+k5+"_"+tag）。
  世界不明は数えない（定義の表と同じ）。
集計（出どころ別_<腕>.md）：通過群 L＝6・L＝3（走行末に生きているかを問わない。control/判断_0927_1250.md の 3）ごと、出どころごとに、
  見ていない型の主張（出どころ s から）がある定義の数・合わせた率（Σwf ÷ Σn）・定義ごとの率の 10 の区切りの分布・その出どころの見ていない型の主張が無い定義の数。
出力（既にあれば作らない）：merged/defs_spoke8src_<腕>.csv・merged/出どころ別_<腕>.md。結果のブランチへは <機械>/<腕>/ に .csv.gz と .md を足して上げる（tools/results_push.py）。
使い方  python3.12 tools/src_unseen.py <腕の走行根> <腕名> <結果の作業場所> <機械の名前> [--no-push]"""
import collections, csv, gzip, json, pathlib, shutil, sys, time

REPO = pathlib.Path(__file__).resolve().parent.parent
arm_root, arm, resdir, host = pathlib.Path(sys.argv[1]).resolve(), sys.argv[2], pathlib.Path(sys.argv[3]), sys.argv[4]
PUSH = "--no-push" not in sys.argv
mg = arm_root / "merged"
l2s_p, defs_p = mg / f"l2s8_{arm}.json", mg / f"defs_spoke8_{arm}.csv"
out_csv, out_md = mg / f"defs_spoke8src_{arm}.csv", mg / f"出どころ別_{arm}.md"
SRC = (("proj", "源投影", "投影"), ("fill_live", "源生充", "生きている行の穴埋め"), ("fill_tomb", "源墓充", "墓石の穴埋め"))
UNSEEN = ("五未見未話", "五未見話")

if not (out_csv.exists() and out_md.exists()):
    l2s = json.load(open(l2s_p, encoding="utf-8"))["台帳"]
    V = {}
    for x in l2s:
        for K, v in x["定義"].items():
            V[f"{x['cell']}/{x['seed']}/{K}"] = v

    def cols(v):
        out = {}
        for s, sk, _ in SRC:
            wf = sum(v.get(f"{sk}{k}_世界偽", 0) for k in UNSEEN)
            wt = sum(v.get(f"{sk}{k}_世界真", 0) for k in UNSEEN)
            rs = sum(v.get(f"{sk}{k}_言い直し", 0) for k in UNSEEN)
            out.update({f"n_unseen2_{s}": wf + wt, f"wf_unseen2_{s}": wf, f"rate_unseen2_{s}": (wf / (wf + wt)) if wf + wt else "",
                        f"rs_unseen2_{s}": rs})
        return out

    rows = list(csv.DictReader(open(defs_p, encoding="utf-8")))
    ids = [r["defid"] for r in rows]
    if set(ids) != set(V) or len(ids) != len(V):
        sys.exit(f"★ 定義の表と走査の版 8 の定義が合わない（表 {len(ids)}・走査 {len(V)}・表だけ {len(set(ids) - set(V))}・走査だけ {len(set(V) - set(ids))}）")
    new_cols = list(cols({}).keys())
    tmp = out_csv.with_suffix(".csv.tmp")
    with open(tmp, "w", newline="", encoding="utf-8") as fo:
        w = csv.DictWriter(fo, fieldnames=list(rows[0].keys()) + new_cols)
        w.writeheader()
        for r in rows:
            w.writerow({**r, **cols(V[r["defid"]])})
    tmp.rename(out_csv)
    # 集計
    L_ = [f"# {arm}（{host}）：通過群の、出どころ別の見ていない型での誤りの率　判定しない", "",
          f"★ 元：merged/l2s8_{arm}.json（走査の版 8）と定義の表 defs_spoke8_{arm}.csv。作った時刻 {time.strftime('%Y-%m-%d %H:%M')}。道具 tools/src_unseen.py。",
          "★ 見ていない型 ＝ 版 5 の「見ていない・話していない」＋「見ていない・話した」。率 ＝ 世界偽 ÷（世界偽＋世界真）。言い直し・世界不明は分母に入れない。",
          "★ 通過群は、走行末に生きているかを問わない（定義の表の L3・L6 と同じ）。定義は「名前@生まれた試行」ごと。", ""]
    for L in (6, 3):
        grp = [r for r in rows if r.get(f"L{L}") == "1"]
        L_ += [f"## L＝{L}（定義 {len(grp):,}）", "",
               "| 出どころ | その出どころの見ていない型の主張がある定義 | 合わせた率（Σ世界偽／Σ（世界偽＋世界真）） | 言い直し | その主張が無い定義 |",
               "|---|---:|---:|---:|---:|"]
        hist = {}
        for s, _, name in SRC:
            n = wf = rs = has = 0; h = collections.Counter()
            for r in grp:
                c = cols(V[r["defid"]])
                rs += c[f"rs_unseen2_{s}"]
                if c[f"n_unseen2_{s}"]:
                    has += 1; n += c[f"n_unseen2_{s}"]; wf += c[f"wf_unseen2_{s}"]
                    h[min(int(c[f"rate_unseen2_{s}"] * 10), 9)] += 1
            hist[name] = h
            L_.append(f"| {name} | {has:,} | {(wf / n) if n else float('nan'):.4f}（{wf:,}／{n:,}） | {rs:,} | {len(grp) - has:,} |" if n else
                      f"| {name} | 0 | —（0／0） | {rs:,} | {len(grp):,} |")
        L_ += ["", "定義ごとの率の分布（10 の区切り。左を含み右を含まない。最後だけ 1.0 を含む。その出どころの見ていない型の主張がある定義だけ）", "",
               "| 出どころ | " + " | ".join(f"{i/10:.1f}〜" for i in range(10)) + " |", "|---|" + "---:|" * 10]
        for name, h in hist.items():
            L_.append(f"| {name} | " + " | ".join(str(h[i]) for i in range(10)) + " |")
        L_.append("")
    out_md.write_text("\n".join(L_) + "\n", encoding="utf-8")
    print(f"作った {out_csv.name}（{len(rows):,} 行）・{out_md.name}")
else:
    print(f"既にある（作り直さない）：{out_csv.name}・{out_md.name}")

dst = resdir / host / arm
if not dst.exists():
    sys.exit(f"★ 結果の置き場所 {dst} が無い（腕のまとめがまだ上がっていない）")
with open(out_csv, "rb") as fi, gzip.open(dst / f"{out_csv.name}.gz", "wb") as fo:
    shutil.copyfileobj(fi, fo)
shutil.copy(out_md, dst / out_md.name)
if PUSH:
    sys.path.insert(0, str(REPO / "tools"))
    from results_push import push_arm
    ok, lines = push_arm(resdir, host, arm, f"結果：{host} の {arm} に出どころ別の見ていない型の誤りの率を足す（tools/src_unseen.py）")
    print("\n".join(lines))
    sys.exit(0 if ok else 3)

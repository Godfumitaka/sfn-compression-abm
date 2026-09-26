"""本番の流れ（2026-09-26 夜）：腕が一つ終わったら、台帳ごとの解析をまとめ、表と図と README を作り、結果のブランチへ上げる。★ 判定しない。
まとめ（<腕の走行根>/merged/）：rows2・traj8・lsweep・l2s7・counts は「定義」／「台帳」の並びをつなぐ。newlabelR は定義ごとの鍵（R|…）だけを合わせる
  （腕全体の集計の鍵は台帳ごとの値なので、まとめには入れない）。
表：定義の表（tools/defs_table_spoke_v7.py、版 7 の列まで）、まとめ.md（台帳ごとの数え・物差しごとの世界偽の率・通過群の見ていない型の誤りの分布）。
図：tools/prod_arm_fig.R（Rscript があるときだけ。無ければ飛ばして README に書く）。
上げる物（台帳本体は上げない）：<結果>/<機械>/<腕>/ に defs_spoke7.csv.gz・まとめ.md・counts.json・sha256.jsonl・flag.json・図・README.md。
★ 上げる段は tools/results_push.py（コミットの失敗を記録し、はじかれたら pull --rebase して上げ直し、リモートにそろったかを確かめる。失敗なら終わりの番号 3）。
使い方  python3.12 tools/prod_arm_done.py <腕の走行根> <腕名> <結果の作業場所（results ブランチ）> <機械の名前> <旗の説明> [--no-push]"""
import collections, glob, gzip, json, os, pathlib, shutil, subprocess, sys, time

REPO = pathlib.Path(__file__).resolve().parent.parent
arm_root, arm, resdir, host, flagdesc = pathlib.Path(sys.argv[1]).resolve(), sys.argv[2], pathlib.Path(sys.argv[3]), sys.argv[4], sys.argv[5]
PUSH = "--no-push" not in sys.argv
posts = sorted(p.parent for p in arm_root.glob("post/*/seed*/POSTDONE"))
mg = arm_root / "merged"; mg.mkdir(exist_ok=True)


def load(p):
    return json.load(open(p, encoding="utf-8"))


def merge_list(name, key):
    out = None
    for p in posts:
        d = load(p / f"{name}.json")
        if out is None:
            out = {k: v for k, v in d.items() if k != key}; out[key] = []
        out[key] += d[key]
    json.dump(out, open(mg / f"{name}_{arm}.json", "w", encoding="utf-8"), ensure_ascii=False)
    return out


rows2 = merge_list("rows2", "定義"); traj8 = merge_list("traj8", "定義")
lsw = merge_list("lsweep", "台帳"); l2s = merge_list("l2s7", "台帳"); cnt = merge_list("counts", "台帳")
nl = {}
for p in posts:
    for k, v in load(p / "newlabelR.json").items():
        if k.startswith("R|"):
            nl[k] = v
json.dump(nl, open(mg / f"newlabelR_{arm}.json", "w", encoding="utf-8"), ensure_ascii=False)
sha = [load(p / "sha.json") for p in posts]
with open(mg / "sha256.jsonl", "w", encoding="utf-8") as f:
    for r in sha:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")
csv = mg / f"defs_spoke7_{arm}.csv"
r = subprocess.run([sys.executable, str(REPO / "tools/defs_table_spoke_v7.py"), arm, str(mg / f"rows2_{arm}.json"),
                    str(mg / f"newlabelR_{arm}.json"), str(mg / f"lsweep_{arm}.json"), str(mg / f"l2s7_{arm}.json"), str(csv)],
                   cwd=str(REPO), capture_output=True, text=True)
(mg / "defs_table.log").write_text(r.stdout + r.stderr, encoding="utf-8")
if r.returncode != 0:
    print("★ 定義の表が失敗", mg / "defs_table.log"); sys.exit(2)

# ---- まとめ.md ----
PASS = {L: set() for L in (3, 6)}
for x in lsw["台帳"]:
    for R, v in x["定義"].items():
        for L in (3, 6):
            if L in v.get("pass", []):
                PASS[L].add((x["cell"], x["seed"], R))


def rate(c, k):
    w, t = c.get(k + "_世界偽", 0), c.get(k + "_世界真", 0)
    return f"{w/(w+t):.4f}（{w:,}／{w+t:,}）" if w + t else "—"


L_ = [f"# {arm}（{host}）のまとめ　判定しない", "", f"★ 旗：{flagdesc}", f"★ 台帳 {len(posts)} 本（解析と控えが済んだもの）。作った時刻 {time.strftime('%Y-%m-%d %H:%M')}。",
      "★ 率 ＝ 世界偽 ÷（世界偽＋世界真）。世界不明は数えない。", "", "## 台帳ごとの数え（tools/prod_readcounts.py）", "",
      "| セル | 種 | 誕生 | 写し | 写しの割合 | 比べられず | 話した定義 | 話した割合 | L3 | L6 |", "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
tot = collections.Counter()
for x in sorted(cnt["台帳"], key=lambda x: (x["seed"], x["cell"])):
    b = x["誕生"]; L_.append(f"| {x['cell']} | {x['seed']} | {b} | {x['写し']} | {x['写し']/b:.3f} | {x['比べられず']} | "
                             f"{x['話した定義']} | {x['話した定義']/max(x['生まれた定義'],1):.3f} | {x.get('L3','—')} | {x.get('L6','—')} |" if b else
                             f"| {x['cell']} | {x['seed']} | 0 | 0 | — | 0 | {x['話した定義']} | — | {x.get('L3','—')} | {x.get('L6','—')} |")
    for k in ("誕生", "写し", "比べられず", "生まれた定義", "話した定義", "L3", "L6"):
        tot[k] += x.get(k, 0) or 0
L_ += [f"| 計 | | {tot['誕生']} | {tot['写し']} | {tot['写し']/max(tot['誕生'],1):.3f} | {tot['比べられず']} | {tot['話した定義']} | "
       f"{tot['話した定義']/max(tot['生まれた定義'],1):.3f} | {tot['L3']} | {tot['L6']} |", ""]
groups = {"全定義": lambda k: True, "L=6": lambda k: k in PASS[6], "L=3": lambda k: k in PASS[3]}
hist = {L: collections.Counter() for L in (3, 6)}; none = {3: 0, 6: 0}
agg = {g: collections.Counter() for g in groups}; nd = collections.Counter()
for x in l2s["台帳"]:
    for R, v in x["定義"].items():
        key = (x["cell"], x["seed"], R)
        for g, f in groups.items():
            if f(key):
                nd[g] += 1
                for k, n in v.items():
                    if isinstance(n, int):
                        agg[g][k] += n
        for L in (3, 6):
            if key in PASS[L]:
                w = v.get("五未見未話_世界偽", 0) + v.get("五未見話_世界偽", 0); t = v.get("五未見未話_世界真", 0) + v.get("五未見話_世界真", 0)
                if w + t == 0:
                    none[L] += 1
                else:
                    hist[L][min(int(w / (w + t) * 10), 9)] += 1
for g in groups:
    c = agg[g]
    cc = {"見た_世界偽": c["五見話_世界偽"] + c["五見未話_世界偽"], "見た_世界真": c["五見話_世界真"] + c["五見未話_世界真"],
          "見ていない_世界偽": c["五未見未話_世界偽"] + c["五未見話_世界偽"], "見ていない_世界真": c["五未見未話_世界真"] + c["五未見話_世界真"]}
    L_ += [f"## 物差しごとの世界偽の率：{g}（定義 {nd[g]:,}）", "", "| 物差し | 内 | 外 |", "|---|---:|---:|",
           f"| 見た／見ていない（版 5） | {rate(cc,'見た')} | {rate(cc,'見ていない')} |",
           f"| 話した（話内／話外） | {rate(c,'話内')} | {rate(c,'話外')} |",
           f"| 訂正された（訂正内／訂正外、版 7） | {rate(c,'訂正内')} | {rate(c,'訂正外')} |",
           f"| 旧（a：①≧1／b：①=0） | {rate(c,'a')} | {rate(c,'b')} |", "",
           "| 版 5 の四つの分け | 見た・話した | 見た・話していない | 見ていない・話していない | 見ていない・話した |", "|---|---:|---:|---:|---:|",
           f"| 世界偽の率 | {rate(c,'五見話')} | {rate(c,'五見未話')} | {rate(c,'五未見未話')} | {rate(c,'五未見話')} |", ""]
L_ += ["## 通過群の定義の、見ていない型での世界偽の率の分布（版 5、定義ごと、10 の区切り。左を含み右を含まない。最後だけ 1.0 を含む）", "",
       "| | " + " | ".join(f"{i/10:.1f}〜{(i+1)/10:.1f}" for i in range(10)) + " | 見ていない型の主張なし |", "|---|" + "---:|" * 11]
for L in (6, 3):
    L_.append(f"| L={L}（{len(PASS[L])}） | " + " | ".join(str(hist[L][i]) for i in range(10)) + f" | {none[L]} |")
(mg / "まとめ.md").write_text("\n".join(L_) + "\n", encoding="utf-8")

# ---- 図 ----
fig = None
if shutil.which("Rscript"):
    fig = mg / f"図_{arm}.png"
    r = subprocess.run(["Rscript", str(REPO / "tools/prod_arm_fig.R"), str(csv), str(fig), arm], capture_output=True, text=True)
    (mg / "fig.log").write_text(r.stdout + r.stderr, encoding="utf-8")
    if r.returncode != 0 or not fig.exists():
        fig = None

# ---- 結果へ ----
commit = subprocess.run(["git", "-C", str(REPO), "rev-parse", "--short", "HEAD"], capture_output=True, text=True).stdout.strip()
desc = subprocess.run(["git", "-C", str(REPO), "describe", "--tags", "--always"], capture_output=True, text=True).stdout.strip()
dst = resdir / host / arm; dst.mkdir(parents=True, exist_ok=True)
with open(csv, "rb") as fi, gzip.open(dst / f"defs_spoke7_{arm}.csv.gz", "wb") as fo:
    shutil.copyfileobj(fi, fo)
for p in (mg / "まとめ.md", mg / "sha256.jsonl"):
    shutil.copy(p, dst / p.name)
json.dump(cnt, open(dst / "counts.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
if (arm_root / "flag.json").exists():
    shutil.copy(arm_root / "flag.json", dst / "flag.json")
if fig:
    shutil.copy(fig, dst / fig.name)
kept = sorted({(r_["cell"], r_["seed"]) for r_ in sha if not r_["deleted"]})
(dst / "README.md").write_text("\n".join([
    f"# {arm}（{host}）", "",
    f"- 旗：{flagdesc}",
    f"- コード：{desc}（{commit}）",
    f"- 台帳：{len(posts)} 本（解析と sha の控えが済んだもの）。台帳本体は上げていない。本体の sha256 は sha256.jsonl。",
    f"- 残した台帳（seed001・002）：{len(kept)} 本（走らせた機械の {arm_root}/ledgers）",
    "- 表：defs_spoke7_*.csv.gz（定義の表、版 7 の列まで）、まとめ.md（台帳ごとの数え・物差しごとの世界偽の率・通過群の見ていない型の誤りの分布）、counts.json",
    f"- 図：{fig.name if fig else '無し（Rscript が無い、または描けなかった）'}",
    f"- 作った時刻：{time.strftime('%Y-%m-%d %H:%M')}", ""]), encoding="utf-8")
if PUSH:
    # ★ 2026-09-26 夜の直し：コミットの失敗を捨てず、はじかれたら取り直して上げ直し、最後にリモートにそろったかを確かめる（tools/results_push.py）。
    sys.path.insert(0, str(REPO / "tools"))
    from results_push import push_arm
    ok, lines = push_arm(resdir, host, arm, f"結果：{host} の {arm}（台帳 {len(posts)} 本、{desc}）")
    print("\n".join(lines))
    if not ok:
        print("★ 上げられなかった（結果の作業場所に残してある）", dst)
        sys.exit(3)
    print("上げた（確かめ済み）", dst)
print("->", dst)

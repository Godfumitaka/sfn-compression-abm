"""本番の流れ（2026-09-26 夜）：腕が一つ終わったら、台帳ごとの解析をまとめ、表と図と README を作り、結果のブランチへ上げる。★ 判定しない。
まとめ（<腕の走行根>/merged/）：rows2・traj8・lsweep・l2s8（v3.4 から。前は l2s7）・counts は「定義」／「台帳」の並びをつなぐ。newlabelR は定義ごとの鍵（R|…）だけを合わせる
  （腕全体の集計の鍵は台帳ごとの値なので、まとめには入れない）。
表：定義の表（v3.4：tools/defs_table_spoke_v8.py、走査の版 8 から）、まとめ.md（台帳ごとの数え・物差しごとの世界偽の率・通過群の見ていない型の誤りの分布）。
図：tools/prod_arm_fig.R（Rscript があるときだけ。無ければ飛ばして README に書く）。
上げる物（台帳本体は上げない）：<結果>/<機械>/<腕>/ に defs_spoke8.csv.gz・まとめ.md・counts.json・sha256.jsonl・flag.json・図・README.md。
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
lsw = merge_list("lsweep", "台帳"); l2s = merge_list("l2s8", "台帳"); cnt = merge_list("counts", "台帳")   # ★ v3.4：走査は版 8
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
# ★ v3.4：またぎの組の表は世界ごと（台帳の種ファイルの名前から。tools/make_pairs.py で作った worlds_2026-09-27/pairs_<種の名前>.json）
seedfs = sorted({r_.get("seed_file") or str(REPO / "seeds/U-011_seed_v3a2.json") for r_ in sha})
# ★ 2026-09-28 夜（マック）：同じ腕を二つの作業場所で続きから走らせると、種ファイルの場所（絶対パス）だけが違う。中身（sha256）と名前が同じなら一つとみる。
import hashlib as _hl
_seedkeys = {(pathlib.Path(x).name, _hl.sha256(open(x, "rb").read()).hexdigest() if os.path.exists(x) else x) for x in seedfs}
if len(_seedkeys) == 1 and len(seedfs) > 1:
    print("種ファイルの場所が二つ以上あるが、名前と中身が同じなので一つとみる：", seedfs)
    seedfs = seedfs[:1]
if len(seedfs) != 1:
    print("★ 一つの腕に種ファイルが二つ以上", seedfs); sys.exit(2)
pairsf = REPO / "worlds_2026-09-27" / f"pairs_{pathlib.Path(seedfs[0]).stem}.json"
if not pairsf.exists():
    print("★ またぎの組の表が無い", pairsf); sys.exit(2)
csv = mg / f"defs_spoke8_{arm}.csv"
r = subprocess.run([sys.executable, str(REPO / "tools/defs_table_spoke_v8.py"), arm, str(mg / f"l2s8_{arm}.json"), str(csv),
                    "--pairs", str(pairsf)], cwd=str(REPO), capture_output=True, text=True)
(mg / "defs_table.log").write_text(r.stdout + r.stderr, encoding="utf-8")
if r.returncode != 0:
    print("★ 定義の表が失敗", mg / "defs_table.log"); sys.exit(2)

# ---- まとめ.md（v3.4：走査の版 8。定義は「名前@生まれた試行」。率は言い直しを除いた率と含めた率の両方） ----
PASS = {L: set() for L in (3, 6)}
ALLDEF = {}
for x in l2s["台帳"]:
    for K, v in x["定義"].items():
        key = (x["cell"], x["seed"], K); ALLDEF[key] = v
        for L in (3, 6):
            if L in (v.get("系列") or {}).get("pass", []):
                PASS[L].add(key)


def rate(c, k):
    w, t, rs = c.get(k + "_世界偽", 0), c.get(k + "_世界真", 0), c.get(k + "_言い直し", 0)
    a_ = f"{w/(w+t):.4f}（{w:,}／{w+t:,}）" if w + t else "—"
    b_ = f"{w/(w+t+rs):.4f}（{w:,}／{w+t+rs:,}）" if w + t + rs else "—"
    return f"{a_} ／ {b_}"


L_ = [f"# {arm}（{host}）のまとめ　判定しない", "", f"★ 旗：{flagdesc}", f"★ 台帳 {len(posts)} 本（解析と控えが済んだもの）。作った時刻 {time.strftime('%Y-%m-%d %H:%M')}。",
      "★ 走査は版 8（tools/l2scan_spoke_v8.py）：主張は試行 t を取り込む前の状態で作る。定義は「名前@生まれた試行」ごと。",
      "★ 率は二つ並べる：言い直しを除いた率 ＝ 世界偽 ÷（世界偽＋世界真） ／ 含めた率 ＝ 世界偽 ÷（世界偽＋世界真＋言い直し）。世界不明は数えない。",
      "★ 言い直し ＝ 主張の中身（述語と引数の組）が、その試行の場面で見えている関係と同じもの。",
      f"★ またぎの組の表：{pairsf.name}（種 {pathlib.Path(seedfs[0]).name}）", "",
      "## 台帳ごとの数え（tools/prod_readcounts.py と走査の版 8）", "",
      "L3・L6 は走査の版 8 の同一性ごとの系列から（版 7 までの lsweep は名前ごと）。言い直しの割合の分母は主張（発話）の数。",
      "",
      "| セル | 種 | 誕生 | 写し | 写しの割合 | 比べられず | 話した定義 | 話した割合 | L3 | L6 | 主張 | 言い直し | 言い直しの割合 | 作り直し一致 | 作り直し不一致 | 名前の食い違い | 同じ名前で生まれ直した |",
      "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
S8 = {(x["cell"], x["seed"]): x for x in l2s["台帳"]}
tot = collections.Counter()
for x in sorted(cnt["台帳"], key=lambda x: (x["seed"], x["cell"])):
    s8 = S8.get((x["cell"], x["seed"]), {}); c8 = s8.get("計", {}); dd = s8.get("定義", {})
    l3 = sum(1 for v in dd.values() if 3 in (v.get("系列") or {}).get("pass", [])); l6 = sum(1 for v in dd.values() if 6 in (v.get("系列") or {}).get("pass", []))
    ncl = c8.get("発話", 0); nrs = c8.get("言い直し", 0)
    b = x["誕生"]
    L_.append(f"| {x['cell']} | {x['seed']} | {b} | {x['写し']} | {(x['写し']/b) if b else 0:.3f} | {x['比べられず']} | "
              f"{x['話した定義']} | {x['話した定義']/max(x['生まれた定義'],1):.3f} | {l3} | {l6} | {ncl} | {nrs} | {(nrs/ncl) if ncl else 0:.4f} | "
              f"{c8.get('発話の作り直し_一致',0)} | {c8.get('発話の作り直し_不一致',0)} | {c8.get('状態と記録の名前の食い違い',0)+c8.get('組み立て直しと記録の名前の食い違い',0)} | {c8.get('同じ名前で生まれ直した',0)} |")
    for k in ("誕生", "写し", "比べられず", "生まれた定義", "話した定義"):
        tot[k] += x.get(k, 0) or 0
    tot["L3"] += l3; tot["L6"] += l6; tot["主張"] += ncl; tot["言い直し"] += nrs
    for k in ("発話の作り直し_一致", "発話の作り直し_不一致", "状態と記録の名前の食い違い", "組み立て直しと記録の名前の食い違い", "同じ名前で生まれ直した"):
        tot[k] += c8.get(k, 0)
L_ += [f"| 計 | | {tot['誕生']} | {tot['写し']} | {tot['写し']/max(tot['誕生'],1):.3f} | {tot['比べられず']} | {tot['話した定義']} | "
       f"{tot['話した定義']/max(tot['生まれた定義'],1):.3f} | {tot['L3']} | {tot['L6']} | {tot['主張']} | {tot['言い直し']} | {tot['言い直し']/max(tot['主張'],1):.4f} | "
       f"{tot['発話の作り直し_一致']} | {tot['発話の作り直し_不一致']} | {tot['状態と記録の名前の食い違い']+tot['組み立て直しと記録の名前の食い違い']} | {tot['同じ名前で生まれ直した']} |", ""]
groups = {"全定義": lambda k: True, "L=6": lambda k: k in PASS[6], "L=3": lambda k: k in PASS[3]}
hist = {L: collections.Counter() for L in (3, 6)}; none = {3: 0, 6: 0}; never = {3: 0, 6: 0}; dead = {3: 0, 6: 0}
agg = {g: collections.Counter() for g in groups}; nd = collections.Counter(); ndc = collections.Counter()
for key, v in ALLDEF.items():
    for g, f in groups.items():
        if f(key):
            nd[g] += 1; ndc[g] += int(v.get("主張あり", 0))
            for k, n in v.items():
                if isinstance(n, int) and not isinstance(n, bool) and "_" in k:
                    agg[g][k] += n
    for L in (3, 6):
        if key in PASS[L]:
            dead[L] += int(not v.get("走行末に生きている"))   # ★ v3.5：通過群は生きているかを問わない。死んでいる数は別の列
            if not v.get("主張あり"):
                never[L] += 1; continue
            w = v.get("五未見未話_世界偽", 0) + v.get("五未見話_世界偽", 0); t = v.get("五未見未話_世界真", 0) + v.get("五未見話_世界真", 0)
            if w + t == 0:
                none[L] += 1
            else:
                hist[L][min(int(w / (w + t) * 10), 9)] += 1
for g in groups:
    c = agg[g]
    cc = {f"{a}_{t}": c[f"五{a2}話_{t}"] + c[f"五{a2}未話_{t}"] for a, a2 in (("見た", "見"), ("見ていない", "未見")) for t in ("世界偽", "世界真", "言い直し")}
    L_ += [f"## 物差しごとの世界偽の率：{g}（定義 {nd[g]:,}、うち主張あり {ndc[g]:,}）", "", "各欄 ＝ 言い直しを除いた率（世界偽／世界偽＋世界真） ／ 含めた率（世界偽／世界偽＋世界真＋言い直し）", "",
           "| 物差し | 内 | 外 |", "|---|---:|---:|",
           f"| 見た／見ていない（版 5） | {rate(cc,'見た')} | {rate(cc,'見ていない')} |",
           f"| 話した（話内／話外） | {rate(c,'話内')} | {rate(c,'話外')} |",
           f"| 訂正された（訂正内／訂正外、版 7） | {rate(c,'訂正内')} | {rate(c,'訂正外')} |",
           f"| 旧（a：①≧1／b：①=0） | {rate(c,'a')} | {rate(c,'b')} |", "",
           "| 版 5 の四つの分け | 見た・話した | 見た・話していない | 見ていない・話していない | 見ていない・話した |", "|---|---:|---:|---:|---:|",
           f"| 世界偽の率 | {rate(c,'五見話')} | {rate(c,'五見未話')} | {rate(c,'五未見未話')} | {rate(c,'五未見話')} |",
           f"| 言い直しの数 | {c['五見話_言い直し']:,} | {c['五見未話_言い直し']:,} | {c['五未見未話_言い直し']:,} | {c['五未見話_言い直し']:,} |", ""]
L_ += ["## 通過群の定義の、見ていない型での世界偽の率の分布（版 5、定義の同一性ごと、言い直しを除いた率、10 の区切り。左を含み右を含まない。最後だけ 1.0 を含む）", "",
       "「見ていない型の主張なし」＝ 主張はしたが、見ていない型の主張（言い直しを除く）が無い定義。「一度も主張しなかった」＝ 通過群なのに、走行中に一度も主張しなかった定義（版 8 で足した）。",
       "通過群は、走行末に生きているかを問わずに数える（v3.5、control/判断_0927_1250.md の 3。定義の表の L も同じ）。「うち走行末に生きていない」は通過群のうち走行末に生きていない定義の数（ほかの欄にも入っている）。", "",
       "| | " + " | ".join(f"{i/10:.1f}〜{(i+1)/10:.1f}" for i in range(10)) + " | 見ていない型の主張なし | 一度も主張しなかった | うち走行末に生きていない |", "|---|" + "---:|" * 13]
for L in (6, 3):
    L_.append(f"| L={L}（{len(PASS[L])}） | " + " | ".join(str(hist[L][i]) for i in range(10)) + f" | {none[L]} | {never[L]} | {dead[L]} |")
# ---- 死因（v3.7、2026-09-28：台帳ごとの post/*/death.json〔tools/death_cause.py〕をまとめる。全台帳にあるときだけ） ----
_dj = [p / "death.json" for p in posts]
if _dj and all(x.exists() for x in _dj):
    # ★ v3.8（2026-09-28 夕）：死因に「反証（D-11）」、罰も反証も無い死を「時間による減衰だけ」（v3.8 の記録がある台帳）。台帳にある死因だけを並べる
    _C_ALL = ("②", "①", "棄権", "反証（D-11）", "時間による減衰だけ", "参加率だけ")
    _C = tuple(c for c in _C_ALL if any(c in load(x)["要約"]["死因"] for x in _dj))
    _cnt = collections.Counter(); _z0 = collections.Counter(); _n = _zall = _seat = _withterms = 0
    _own = 0; _own_known = True
    _vals = {c: {"V": [], "P": [], "pt": []} for c in _C}
    for x in _dj:
        _d = load(x); _s = _d["要約"]
        _n += _s["削除"]; _zall += _s["寿命0"]; _seat += _s["席に①_穴埋めがあった行"]; _withterms += _s["項がある行"]
        if _s.get("死んだ試行に自分が伏せ辺だった行") is None:
            _own_known = False
        else:
            _own += _s["死んだ試行に自分が伏せ辺だった行"]
        for c in _C:
            _cnt[c] += _s["死因"].get(c, 0); _z0[c] += _s["寿命0の死因"].get(c, 0)
        for row in _d["行"]:
            _v = _vals.setdefault(row["cause"], {"V": [], "P": [], "pt": []}); _v["V"].append(row["V"])
            if row["P"] is not None:
                _v["P"].append(row["P"]); _v["pt"].append(row["participation_term"])

    def _med(xs):
        xs = sorted(xs)
        return f"{xs[len(xs) // 2] if len(xs) % 2 else (xs[len(xs) // 2 - 1] + xs[len(xs) // 2]) / 2:.4f}" if xs else "—"

    L_ += ["## 死因（deletion_event の kind＝deletion の行。tools/death_cause.py）", "",
           "死因は、その行が生きていたあいだ（登録から削除の試行まで）に受けた罰で一つに分ける：② ＞ ① ＞ 棄権（棄権課金）＞ 反証（D-11、v3.8）＞ "
           "罰も反証も無い（v3.8 は「時間による減衰だけ」、v3.7 までは「参加率だけ」）。"
           "①_穴埋め（席の履歴を減らす罰）は行の V に入らないので死因に数えない。V の項は side の death_terms（旗 --death-terms）から。", "",
           f"★ 削除 {_n:,} 本（台帳 {len(_dj)} 本）。寿命 0（生まれた試行のうちに死んだ行）{_zall:,} 本。V の項がある行 {_withterms:,} 本。"
           f"（参考）席に ①_穴埋め があった行 {_seat:,} 本。"
           + (f"死んだ試行に自分が伏せ辺だった行（その試行に使われた定義の行で、写しで具体化した関係が伏せ辺と同じ）{_own:,} 本。" if _own_known else ""), "",
           "| 死因 | 行 | 割合 | うち寿命 0 | 死んだときの V（中央値） | 参加率 P（中央値） | 参加率の項 P·a（中央値） |", "|---|---:|---:|---:|---:|---:|---:|"]
    for c in _C:
        L_.append(f"| {c} | {_cnt[c]:,} | {(_cnt[c] / _n if _n else 0):.3f} | {_z0[c]:,} | {_med(_vals[c]['V'])} | {_med(_vals[c]['P'])} | {_med(_vals[c]['pt'])} |")
    L_.append("")
    json.dump({"削除": _n, "死因": dict(_cnt), "寿命0": _zall, "寿命0の死因": dict(_z0), "席に①_穴埋めがあった行": _seat,
               "死んだ試行に自分が伏せ辺だった行": _own if _own_known else None,
               "台帳ごと": [dict(load(x)["要約"], 台帳=load(x)["台帳"]) for x in _dj]},
              open(mg / f"死因_{arm}.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
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
with open(csv, "rb") as fi, gzip.open(dst / f"defs_spoke8_{arm}.csv.gz", "wb") as fo:
    shutil.copyfileobj(fi, fo)
for p in (mg / "まとめ.md", mg / "sha256.jsonl") + ((mg / f"死因_{arm}.json",) if (mg / f"死因_{arm}.json").exists() else ()):
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
    f"- 残した台帳：{len(kept)} 本（走らせた機械の {arm_root}/ledgers）",
    "- 表：defs_spoke8_*.csv.gz（定義の表、走査の版 8。一行＝定義の同一性「名前@生まれた試行」。rs_* ＝ 言い直しの数）、まとめ.md（台帳ごとの数え・言い直し・発話の作り直し・物差しごとの世界偽の率〔言い直しを除いた率／含めた率〕・通過群の見ていない型の誤りの分布と一度も主張しなかった定義）、counts.json",
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

"""定義の生まれと型またぎ（2026-09-28 午後、委任書 v3.7 の追記）。★ 判断しない。模型は動かさない。台帳は読まない（消した腕にもかけられる）。
読むもの：<腕の走行根>/side/<セル>/seedNNN.jsonl（誕生・同化の記録 birth/assim と、v3.7 の --death-terms の death_terms、走行末 final）、
  merged/l2s8_<腕>.json（定義の同一性「名前@生まれた試行」と系列の mx・final）、merged/defs_spoke8_<腕>.csv（定義の表）、
  merged/sha256.jsonl（台帳ごとの試行数）、flag.json（設定 → 種ファイル。世界は sweep.py:150-152 と同じ手順で作り直す）。

定義の表に足す列（定義の同一性ごと）
  born_m_alloc   生まれたときの行数（side の birth の m_alloc）
  live_max / live_min / live_final   生きている行の数の、生まれてからの最大・最小・走行末（その同一性が消えた試行まで）。
      side から組み立てる：誕生の m_live から始め、同化で side の m_live に置き直し、death_terms（kind＝deletion）で 1 ずつ減らす。
      試行の中の順は模型と同じ（登録 → 削除）。最大・最小は、l2s8 の系列と同じく各試行の終わり（削除の後）の値で取る。death_terms が無い走行（--death-terms なし）では live_min は空、live_max・live_final は l2s8 の系列から。
  base_trial / base_motif   生まれたときの土台の場面の試行（side の base_written_at）と、その試行の型（世界の試行の motif）
  born_motif     生まれた試行の、いまの場面の型
  cross_birth    型またぎで生まれたか（base_motif ≠ born_motif なら 1）
台帳ごとの数（型またぎ_<腕>.md）：誕生・型またぎの誕生・同化・型またぎの同化（同化の土台の型 ≠ 同化した試行の型）。
確かめ：組み立てた live_max・live_final が l2s8 の系列の mx・final と合わない同一性の数を、まとめに出す（0 のはず）。
出力（既にあれば作らない）：merged/defs_spoke8org_<腕>.csv・merged/型またぎ_<腕>.md。結果のブランチの <機械>/<腕>/ に .csv.gz と .md を足して上げる（tools/results_push.py）。
使い方  python3.12 tools/def_origin.py <腕の走行根> <腕名> <結果の作業場所> <機械の名前> [--no-push]"""
import collections, csv, gzip, json, pathlib, shutil, sys, time

REPO = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
arm_root, arm, resdir, host = pathlib.Path(sys.argv[1]).resolve(), sys.argv[2], pathlib.Path(sys.argv[3]), sys.argv[4]
PUSH = "--no-push" not in sys.argv
mg = arm_root / "merged"
out_csv, out_md = mg / f"defs_spoke8org_{arm}.csv", mg / f"型またぎ_{arm}.md"

if not (out_csv.exists() and out_md.exists()):
    from abm.seed import load_seed
    from abm.world import generate_world
    flag = json.load(open(arm_root / "flag.json", encoding="utf-8"))
    cfgp = pathlib.Path(flag["config"]); cfgp = cfgp if cfgp.is_absolute() else REPO / cfgp
    cfg = json.load(open(cfgp, encoding="utf-8")); fixed = cfg["fixed"]
    seedf = cfg.get("seed_file"); seed_obj = load_seed(str(REPO / seedf)) if seedf else load_seed()
    ntrial = {}
    for l in open(mg / "sha256.jsonl", encoding="utf-8"):
        r = json.loads(l); ntrial[(r["cell"], r["seed"])] = r["n_body"]
    WORLD = {}

    def motifs(seed_i, n):
        if (seed_i, n) not in WORLD:
            w = generate_world(seed_i, n, tuple(cfg["agent_ids"]), seed=seed_obj,
                               holdout_include_second_order=fixed.get("holdout_include_second_order", False))
            WORLD[(seed_i, n)] = [t.motif for t in w.trials]
        return WORLD[(seed_i, n)]

    l2s = json.load(open(mg / f"l2s8_{arm}.json", encoding="utf-8"))["台帳"]
    S8 = {f"{x['cell']}/{x['seed']}/{K}": v for x in l2s for K, v in x["定義"].items()}
    COLS = {}; PER = []; mism = collections.Counter(); has_terms = True
    for (cell, seed_i), n in sorted(ntrial.items()):
        M = motifs(seed_i, n)
        ev = collections.defaultdict(lambda: {"reg": [], "del": []})
        for line in open(arm_root / "side" / cell / f"seed{seed_i:03d}.jsonl", encoding="utf-8"):
            d = json.loads(line); k = d.get("kind")
            if k in ("birth", "assim"):
                ev[d["trial"]]["reg"].append(d)
            elif k == "death_terms":
                for x in d["rows"]:
                    ev[d["trial"]]["del"].append(x)
        led_terms = any(e["del"] for e in ev.values())
        has_terms = has_terms and led_terms
        cur, info = {}, {}          # 名前 -> 同一性（名前@生まれた試行）／同一性 -> 数え
        cnt = collections.Counter()
        for t in range(n):
            e = ev.get(t)
            if e:
                touched = set()
                for d in e["reg"]:
                    R = d["R"]; bm = M[d["base_written_at"]] if d.get("base_written_at") is not None else None
                    cross = int(bm is not None and bm != M[t])
                    if d["kind"] == "birth":
                        K = f"{R}@{t}"; cur[R] = K; touched.add(K)
                        info[K] = {"born_m_alloc": d["m_alloc"], "m": d["m_live"], "live_max": None, "live_min": None,
                                   "base_trial": d.get("base_written_at"), "base_motif": bm, "born_motif": M[t], "cross_birth": cross}
                        cnt["誕生"] += 1; cnt["型またぎの誕生"] += cross
                    else:
                        cnt["同化"] += 1; cnt["型またぎの同化"] += cross
                        K = cur.get(R)
                        if K is not None:
                            info[K]["m"] = d["m_live"]; touched.add(K)
                for x in e["del"]:
                    K = cur.get(x["R"])
                    if K is not None:
                        info[K]["m"] -= 1; touched.add(K)
                for K in touched:      # ★ 試行の終わり（削除の後）の値で最大・最小を取る（l2s8 の系列と同じ）
                    i = info[K]
                    i["live_max"] = i["m"] if i["live_max"] is None else max(i["live_max"], i["m"])
                    i["live_min"] = i["m"] if i["live_min"] is None else min(i["live_min"], i["m"])
        for K, i in info.items():
            defid = f"{cell}/seed{seed_i:03d}/{K}"
            s8 = (S8.get(defid) or {}).get("系列") or {}
            if led_terms:
                if s8 and (i["live_max"] != s8.get("mx") or i["m"] != s8.get("final")):
                    mism["系列と合わない"] += 1
                row = {"born_m_alloc": i["born_m_alloc"], "live_max": i["live_max"], "live_min": i["live_min"], "live_final": i["m"]}
            else:
                row = {"born_m_alloc": i["born_m_alloc"], "live_max": s8.get("mx", ""), "live_min": "", "live_final": s8.get("final", "")}
            row.update({k: i[k] for k in ("base_trial", "base_motif", "born_motif", "cross_birth")})
            COLS[defid] = row
            mism["組み立てた同一性"] += 1
        PER.append((cell, seed_i, dict(cnt)))
    rows = list(csv.DictReader(open(mg / f"defs_spoke8_{arm}.csv", encoding="utf-8")))
    new = ["born_m_alloc", "live_max", "live_min", "live_final", "base_trial", "base_motif", "born_motif", "cross_birth"]
    miss = [r["defid"] for r in rows if r["defid"] not in COLS]
    tmp = out_csv.with_suffix(".csv.tmp")
    with open(tmp, "w", newline="", encoding="utf-8") as fo:
        w = csv.DictWriter(fo, fieldnames=list(rows[0].keys()) + new)
        w.writeheader()
        for r in rows:
            w.writerow({**r, **COLS.get(r["defid"], {k: "" for k in new})})
    tmp.rename(out_csv)
    tot = collections.Counter()
    for _, _, c in PER:
        tot.update(c)
    L_ = [f"# {arm}（{host}）：定義の生まれと型またぎ　判定しない", "",
          f"★ 元：side/（birth・assim・death_terms）・merged/l2s8_{arm}.json・defs_spoke8_{arm}.csv、世界は設定 {cfgp.name} から作り直した。道具 tools/def_origin.py。作った時刻 {time.strftime('%Y-%m-%d %H:%M')}。",
          "★ 型 ＝ 世界の試行の motif。型またぎ ＝ 土台の場面（base_written_at の試行）の型と、いまの場面（生まれた／同化した試行）の型が違う。",
          f"★ 定義の表の {len(rows):,} 行のうち、side から組み立てられなかった行 {len(miss):,}。"
          + (f"生きている行の数を side から組み立てた同一性 {mism['組み立てた同一性']:,} のうち、l2s8 の系列（mx・final）と合わないもの {mism['系列と合わない']:,}。"
             if has_terms else "★ side に death_terms が無い（--death-terms なしの走行）ので、live_min は空、live_max・live_final は l2s8 の系列から。"), "",
          f"| 計 | 誕生 {tot['誕生']:,} | 型またぎの誕生 {tot['型またぎの誕生']:,}（{tot['型またぎの誕生'] / max(tot['誕生'], 1):.3f}） | 同化 {tot['同化']:,} | 型またぎの同化 {tot['型またぎの同化']:,}（{tot['型またぎの同化'] / max(tot['同化'], 1):.3f}） |", "",
          "| セル | 種 | 誕生 | 型またぎの誕生 | 同化 | 型またぎの同化 |", "|---|---|---:|---:|---:|---:|"]
    for cell, seed_i, c in PER:
        L_.append(f"| {cell} | seed{seed_i:03d} | {c.get('誕生', 0)} | {c.get('型またぎの誕生', 0)} | {c.get('同化', 0)} | {c.get('型またぎの同化', 0)} |")
    out_md.write_text("\n".join(L_) + "\n", encoding="utf-8")
    print(f"作った {out_csv.name}（{len(rows):,} 行、組み立てられなかった {len(miss)}）・{out_md.name}　系列と合わない {mism['系列と合わない']}　計 {dict(tot)}")
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
    ok, lines = push_arm(resdir, host, arm, f"結果：{host} の {arm} に定義の生まれと型またぎを足す（tools/def_origin.py）")
    print("\n".join(lines))
    sys.exit(0 if ok else 3)

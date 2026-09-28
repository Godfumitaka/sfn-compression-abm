"""外れの中身と、定義ごとの表（2026-09-29 0 時ごろの依頼。★ 判断しない。模型は動かさない。台帳を読むだけ）。
一つの腕の全台帳から、次の二つの CSV を作る（既にあれば作らない）。
  misses_actual_<腕>.csv：実際の発話（R_used あり・coverage＝1）の外れ一本ずつ
    台帳（セル・種）・試行・話した定義（名前@生まれた試行）・生まれた型・場面の型・出どころ（prediction_path：projection／filling_live／filling_tombstone）・
    言った述語・正解の述語（世界を作り直した伏せ辺）・開示を受けたか（f_fired）・
    穴埋めなら席（予測の ID filling__<R>__<席>__<登録>）と、その席の履歴（回数）の
      外れの前（一つ前の試行のあとの状態）：一番多い述語とその回数・言った述語の回数・正解の述語の回数
      この試行のあと（開示を受けたなら開示のあと。① の穴埋めの減算と m1 の観察を含む状態）：同じ三つ
    ① の穴埋めの記録（charge_source の ①_穴埋め の 前・後。言った述語の回数）
  defs_actual_<腕>.csv：定義の同一性（名前@生まれた試行）ごと一行。走行末に生きているか（alive）の列があり、生きている定義はその行だけを使えばよい。
    エージェントの側で見える量：使われた回数（R_used）・話した回数（R_used かつ coverage＝1）・
      確認の率（参加率。走行末の状態の功績から、生きている行ごとに Σbasis ÷ Σeval_basis〔eval_basis が無ければ opportunity_basis〕の平均と最小）・
      生きている行の数・墓石の数（走行末の状態）・同化の回数（登録で was_extension＝True の数）・生まれてからの試行数（走行末または消えた試行まで）
    研究者の側の量：生まれた型・型またぎで生まれたか（tools/def_origin.py の defs_spoke8org）・
      同化で取り込んだ場面の型（同化した試行の場面の型ごとの回数、種類の数）
    結果：実際の発話の数と外れ・開示を受けた外れの数・最初の開示を受けた外れのあとの発話と外れ（場面の型を問わない）
使い方  python3.12 tools/miss_anatomy.py <腕の走行根> <腕名> [workers]"""
import collections, concurrent.futures, csv, glob, gzip, json, os, pathlib, sys

REPO = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))


def slot_view(sh, R, slot, said, correct):
    v = (sh or {}).get(str((R, slot)))
    if not isinstance(v, dict):
        v = {k: 1 for k in (v or [])}
    top = max(v.items(), key=lambda kv: (kv[1], kv[0])) if v else (None, None)
    return [top[0], top[1], v.get(said, 0), v.get(correct, 0)]


def one(args):
    p, seedf, incarn, orgrow = args
    from abm.loop import _apply
    from abm.seed import load_seed
    from abm.world import generate_world
    cell = os.path.basename(os.path.dirname(p)); seed = os.path.basename(p)[:7]
    misses = []
    D = collections.defaultdict(lambda: collections.Counter())
    AM = collections.defaultdict(collections.Counter)
    first_dm = {}
    with gzip.open(p, "rt", encoding="utf-8") as f:
        h = json.loads(next(f))
        T = h["trial_count"]
        ws = generate_world(h["run_seed"], T, ["agent"], seed=load_seed(seedf),
                            holdout_include_second_order=bool(h.get("arm_holdout_second_order") or False))
        assert ws.world_hash == h["world_hash"], p
        MOT = [tr.motif for tr in ws.trials]; HO = [tr.held_out_edge.predicate for tr in ws.trials]

        def ident_of(R, t, speaking=True):
            for born, died, _ in incarn.get(R, ()):
                if (born < t if speaking else born <= t) and (died is None or t <= died):
                    return f"{R}@{born}"
            return None
        snap = None
        for line in f:
            r = json.loads(line)
            if r.get("record_type") != "trial":
                continue
            t = r["prediction_order"]
            before_sh = dict(snap["slot_history"]) if snap is not None else {}
            s = r["state_snapshot"]
            if s["kind"] == "full":
                snap = s["value"]
            else:
                for k, ch in s["changes"].items():
                    snap[k] = _apply(snap[k], ch)
            for e in r.get("reg_del_events") or ():
                if e.get("kind") == "registration" and e.get("was_extension"):
                    K = ident_of(e["R"], t, speaking=False)
                    if K:
                        D[K]["同化"] += 1; AM[K][MOT[t]] += 1
            R = r.get("R_used")
            if R is None:
                continue
            K = ident_of(R, t)
            D[K]["使われた"] += 1
            if r.get("coverage") != 1:
                continue
            hit = bool(r.get("hit")); ff = bool(r.get("f_fired"))
            D[K]["話した"] += 1
            if K in first_dm and t > first_dm[K]:
                D[K]["開示外れの後_話した"] += 1; D[K]["開示外れの後_外れ"] += int(not hit)
            if hit:
                continue
            D[K]["外れ"] += 1
            if ff:
                D[K]["開示外れ"] += 1; first_dm.setdefault(K, t)
            pe = r.get("predicted_edge") or {}
            rid = pe.get("relation_id", ""); said = pe.get("predicate"); correct = HO[t]
            row = {"cell": cell, "seed": seed, "trial": t, "defid": K, "born_motif": (orgrow.get(K) or {}).get("born_motif"),
                   "scene_motif": MOT[t], "path": r.get("prediction_path"), "said": said, "correct": correct, "f_fired": int(ff)}
            if rid.startswith("filling__"):
                _, RR, sl, reg = rid.split("__"); sl = int(sl)
                b = slot_view(before_sh, RR, sl, said, correct); a = slot_view(snap["slot_history"], RR, sl, said, correct)
                c1 = [x for x in ((r.get("charge_source") or {}).get("①_穴埋め") or []) if x.get("R") == RR and x.get("slot_index") == sl]
                row.update({"slot": sl, "slot_reg": int(reg),
                            "before_top": b[0], "before_top_n": b[1], "before_said_n": b[2], "before_correct_n": b[3],
                            "after_top": a[0], "after_top_n": a[1], "after_said_n": a[2], "after_correct_n": a[3],
                            "c1fill_before": c1[0].get("前") if c1 else "", "c1fill_after": c1[0].get("後") if c1 else ""})
            misses.append(row)
    # 走行末の状態
    end = {}
    for name, d in (snap or {}).get("definitions", {}).items():
        K = ident_of(name, T - 1, speaking=False)
        cons = d.get("constituents") or []
        live = [c for c in cons if c.get("alive")]
        parts = []
        for c in live:
            m = snap["merit"].get(str((name, c["slot_index"], c["registered_at"])))
            if m:
                den = sum(m.get("eval_basis") or m.get("opportunity_basis") or [])
                parts.append(sum(m["basis"]) / den if den > 0 else 0.0)
        end[K] = {"alive": int(bool(live)), "live_rows": len(live), "tomb_rows": len(cons) - len(live),
                  "part_mean": (sum(parts) / len(parts)) if parts else "", "part_min": min(parts) if parts else "",
                  "assimilation_count": d.get("assimilation_count")}
    return cell, seed, misses, {k: dict(v) for k, v in D.items()}, {k: dict(v) for k, v in AM.items()}, end, T


def main():
    arm_root, arm = pathlib.Path(sys.argv[1]).resolve(), sys.argv[2]
    WK = int(sys.argv[3]) if len(sys.argv) > 3 else 4
    mg = arm_root / "merged"
    out_m, out_d = mg / f"misses_actual_{arm}.csv", mg / f"defs_actual_{arm}.csv"
    if out_m.exists() and out_d.exists():
        print("既にある（作り直さない）"); return
    fl = json.load(open(arm_root / "flag.json", encoding="utf-8"))
    seedf = str(REPO / json.load(open(REPO / fl["config"], encoding="utf-8")).get("seed_file", "seeds/U-011_seed_v3a2.json"))
    inc = collections.defaultdict(lambda: collections.defaultdict(list)); org = collections.defaultdict(dict)
    for row in csv.DictReader(open(mg / f"defs_spoke8org_{arm}.csv", encoding="utf-8")):
        cell, seed, K = row["defid"].split("/")
        R, born = K.rsplit("@", 1)
        died = row.get("died")
        inc[(cell, seed)][R].append((int(born), int(died) if died not in (None, "") else None, row.get("born_motif") or None))
        org[(cell, seed)][K] = {"born": int(born), "died": died, "born_motif": row.get("born_motif"), "cross_birth": row.get("cross_birth")}
    fs = sorted(glob.glob(str(arm_root / "ledgers/cells/*/seed*.jsonl.gz")))
    jobs = [(p, seedf, dict(inc[(os.path.basename(os.path.dirname(p)), os.path.basename(p)[:7])]),
             org[(os.path.basename(os.path.dirname(p)), os.path.basename(p)[:7])]) for p in fs]
    allm, rows = [], []
    with concurrent.futures.ProcessPoolExecutor(max_workers=WK) as ex:
        for cell, seed, misses, D, AM, end, T in ex.map(one, jobs):
            allm += misses
            for K, o in org[(cell, seed)].items():
                d = D.get(K, {}); e = end.get(K, {"alive": 0}); am = AM.get(K, {})
                last = (T - 1) if o["died"] in (None, "") else int(o["died"])
                rows.append({"arm": arm, "cell": cell, "seed": seed, "defid": f"{cell}/{seed}/{K}", "alive": e.get("alive", 0),
                             "used": d.get("使われた", 0), "spoke": d.get("話した", 0), "part_mean": e.get("part_mean", ""), "part_min": e.get("part_min", ""),
                             "live_rows": e.get("live_rows", ""), "tomb_rows": e.get("tomb_rows", ""), "assim": d.get("同化", 0),
                             "assimilation_count": e.get("assimilation_count", ""), "trials_since_birth": last - o["born"],
                             "born_motif": o["born_motif"], "cross_birth": o["cross_birth"],
                             "assim_motif_kinds": len(am), "assim_motifs": ";".join(f"{m}:{n}" for m, n in sorted(am.items())),
                             "misses": d.get("外れ", 0), "disclosed_misses": d.get("開示外れ", 0),
                             "spoke_after_first_disclosed_miss": d.get("開示外れの後_話した", 0), "misses_after_first_disclosed_miss": d.get("開示外れの後_外れ", 0)})
    mcols = ["cell", "seed", "trial", "defid", "born_motif", "scene_motif", "path", "said", "correct", "f_fired", "slot", "slot_reg",
             "before_top", "before_top_n", "before_said_n", "before_correct_n", "after_top", "after_top_n", "after_said_n", "after_correct_n",
             "c1fill_before", "c1fill_after"]
    with open(out_m, "w", newline="", encoding="utf-8") as fo:
        w = csv.DictWriter(fo, fieldnames=mcols); w.writeheader()
        for m in sorted(allm, key=lambda x: (x["seed"], x["cell"], x["trial"])):
            w.writerow(m)
    with open(out_d, "w", newline="", encoding="utf-8") as fo:
        w = csv.DictWriter(fo, fieldnames=list(rows[0].keys())); w.writeheader()
        for r in rows:
            w.writerow(r)
    print(f"{arm}：外れ {len(allm)} 本 -> {out_m.name}、定義 {len(rows)} 行（生きている {sum(r['alive'] for r in rows)}）-> {out_d.name}")


if __name__ == "__main__":
    main()

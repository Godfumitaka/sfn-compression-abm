"""実際の発話を、話した定義の生まれた型で分けて数える（2026-09-28 夜の依頼。★ 判断しない。模型は動かさない。台帳を読むだけ）。
腕ごと（全台帳の和）に：
  1 実際の発話（R_used があり coverage＝1）の数・当たり（hit＝1）・外れ
  2 外れのうち、話した定義が「その場面の型で生まれた定義」だったもの／違う型で生まれた定義だったもの
     話した定義の同一性：R_used の名前と、merged/defs_spoke8org_<腕>.csv（tools/def_origin.py）の、その名前の定義のうち
       生まれた試行 born ＜ t ≦ 消えた試行 died（died が空なら走行末まで）のもの。生まれた型はその行の born_motif。
     場面の型：台帳の見出しから世界を作り直した、その試行の motif（world_hash を突き合わせる）。
  3 外れた発話のうち開示を受けた（f_fired）もの。その後、同じ定義（同一性）が同じ場面の型で次に話したか：
     次に話した外れの数（＝次の発話があった外れ）、その次の発話の当たり・外れ、無かった外れの数。
     あわせて、開示を受けた外れのあと、同じ定義が同じ型で話した発話（重ならないように、定義と試行の組で一度ずつ）の数と当たり・外れ。
使い方  python3.12 tools/spoken_by_birthtype.py <腕の走行根> <腕名> [workers]   → 標準出力に json"""
import collections, concurrent.futures, csv, glob, gzip, json, os, pathlib, sys

REPO = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))


def one(args):
    p, seedf, incarn = args
    from abm.seed import load_seed
    from abm.world import generate_world
    C = collections.Counter()
    with gzip.open(p, "rt", encoding="utf-8") as f:
        h = json.loads(next(f))
        ws = generate_world(h["run_seed"], h["trial_count"], ["agent"], seed=load_seed(seedf),
                            holdout_include_second_order=bool(h.get("arm_holdout_second_order") or False))
        assert ws.world_hash == h["world_hash"], p
        MOT = [tr.motif for tr in ws.trials]
        spoken = []   # (t, 同一性, 場面の型, hit, f_fired, 生まれた型)
        for line in f:
            r = json.loads(line)
            if r.get("record_type") != "trial":
                continue
            R = r.get("R_used")
            if R is None or r.get("coverage") != 1:
                continue
            t = r["prediction_order"]
            ident = None; bm = None
            for born, died, motif in incarn.get(R, ()):
                if born < t and (died is None or t <= died):
                    ident = f"{R}@{born}"; bm = motif; break
            spoken.append((t, ident, MOT[t], int(r.get("hit") or 0), bool(r.get("f_fired")), bm))
    for t, ident, m, hit, ff, bm in spoken:
        C["発話"] += 1; C["当たり" if hit else "外れ"] += 1
        if not hit:
            if bm is None:
                C["外れ_生まれた型が分からない"] += 1
            elif bm == m:
                C["外れ_その型で生まれた定義"] += 1
            else:
                C["外れ_違う型で生まれた定義"] += 1
    after = set()
    for i, (t, ident, m, hit, ff, bm) in enumerate(spoken):
        if hit or not ff:
            continue
        C["外れ_開示あり"] += 1
        if ident is None:
            C["外れ_開示あり_同一性が分からない"] += 1; continue
        nxt = next(((t2, h2) for t2, i2, m2, h2, f2, b2 in spoken[i + 1:] if i2 == ident and m2 == m), None)
        if nxt is None:
            C["外れ_開示あり_その後同じ型で話さなかった"] += 1
        else:
            C["外れ_開示あり_次も同じ型で話した"] += 1
            C["その次の発話_当たり" if nxt[1] else "その次の発話_外れ"] += 1
        for t2, i2, m2, h2, f2, b2 in spoken[i + 1:]:
            if i2 == ident and m2 == m:
                after.add((i2, t2, h2))
    C["開示を受けた外れの後_同じ定義が同じ型で話した発話"] = len(after)
    C["その後の発話_当たり"] = sum(1 for x in after if x[2]); C["その後の発話_外れ"] = sum(1 for x in after if not x[2])
    return dict(C)


def main():
    arm_root, arm = pathlib.Path(sys.argv[1]).resolve(), sys.argv[2]
    WK = int(sys.argv[3]) if len(sys.argv) > 3 else 4
    fl = json.load(open(arm_root / "flag.json", encoding="utf-8"))
    seedf = str(REPO / json.load(open(REPO / fl["config"], encoding="utf-8")).get("seed_file", "seeds/U-011_seed_v3a2.json"))
    inc = collections.defaultdict(lambda: collections.defaultdict(list))   # (cell, seed) -> R -> [(born, died, motif)]
    for row in csv.DictReader(open(arm_root / "merged" / f"defs_spoke8org_{arm}.csv", encoding="utf-8")):
        cell, seed, K = row["defid"].split("/")
        R, born = K.rsplit("@", 1)
        died = row.get("died")
        inc[(cell, seed)][R].append((int(born), int(died) if died not in (None, "") else None, row.get("born_motif") or None))
    fs = sorted(glob.glob(str(arm_root / "ledgers/cells/*/seed*.jsonl.gz")))
    jobs = [(p, seedf, dict(inc[(os.path.basename(os.path.dirname(p)), os.path.basename(p)[:7])])) for p in fs]
    tot = collections.Counter()
    with concurrent.futures.ProcessPoolExecutor(max_workers=WK) as ex:
        for c in ex.map(one, jobs):
            tot.update(c)
    print(json.dumps({"腕": arm, "台帳": len(fs), **dict(tot)}, ensure_ascii=False))


if __name__ == "__main__":
    main()

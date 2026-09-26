"""★ 模型の形の表（2026-09-25 アストラさんの指示）。読むだけ。台帳一本ごとの数を出し、腕ごとの中央を出す。
★ 2026-09-26 0 時に足した列
   消えた定義          台帳の reg_del_events の "definition_removed" の数（deletion_event の写しは数えない）（貯蔵から消えるのは m_live=0 のときだけ＝行が全部死んだ。abm/deletion.py:82-94）
   死因_行が全部死んだ  ＝ 消えた定義
   死因_そのほか        登録 − 走行末の生存定義 − 消えた定義（ほかの道で消えたものがあれば 0 でなくなる）
   行の死              "deletion" の数（行が死んだ回数。verbatim_deletion は数えない）
   done_final_def_count  .done の final_def_count（走行末に貯蔵にある定義の数。検算用）
★ 出どころ（台帳一本ごと）
   登録された定義の数         side/<セル>/seedNNN.jsonl の "kind":"birth" の行の数
   走行末の生存定義の数       side の最後の行（"kind":"final"）の alive_end の数
   同化の回数                 side の "kind":"assim" の行の数
   生まれた行数               birth の行の m_alloc の合計（誕生のときの行の数）
   走行末の生きている行数     .done の final_m_live_total
   話した試行の数             台帳の試行で R_used があり coverage=1
   棄権の数                   台帳の試行で coverage=0
   水準2 の主張の数           tools/l2scan_spoke.py の出力（l2s）の 計.発話（無ければ空）
   通過 L=3・L=6 の定義の数    lsweep_<腕>.json の pass に L を含む定義の数
   v3.1a：同化で足した行の数・死んだ述語が戻った回数   manifest の v31.ext_added・v31.ext_returned_dead
   v3.1：① が付いた行の数（投影）  台帳の charge_source["①"] の数（d32 では投影の経路だけが足す）
          slot_history を減らした回数（穴埋め）  台帳の charge_source["①_穴埋め"] のうち 後 < 前 のもの
          あわせて v31.c1_projection・c1_filling（経路を通った試行の数）も出す
使い方  python3.12 shape_table.py <腕名> <走行根> <lsweep.json> <l2s.json か -> <出力json> [workers]"""
import concurrent.futures, glob, gzip, json, os, statistics as st, sys
from pathlib import Path
ARM, O, LS, L2S, OUT = sys.argv[1:6]
WK = int(sys.argv[6]) if len(sys.argv) > 6 else 4
O = Path(O)


def one(p):
    p = Path(p); cell = p.parent.name; stem = p.name.replace(".jsonl.gz", "")
    spk = abst = rows1 = hdec = removed = rowdeath = 0
    with gzip.open(p, "rt", encoding="utf-8") as f:
        next(f)
        for line in f:
            if '"coverage":0' in line:
                abst += 1
            elif '"coverage":1' in line and '"R_used":null' not in line:
                spk += 1
            # ★ 2026-09-26 01:10 直し：消える出来事は reg_del_events と deletion_event の二か所に同じものが書かれる。
            #   文字列で数えると 2 倍になるので、reg_del_events だけから数える
            hit_ev = '"kind":"definition_removed"' in line or '"kind":"deletion"' in line
            if '"charge_source":null' in line and not hit_ev:
                continue
            d = json.loads(line)
            for e in d.get("reg_del_events") or ():
                k = e.get("kind")
                if k == "definition_removed":
                    removed += 1          # ★ 定義が貯蔵から消えた（m_live が 0＝行が全部死んだ。abm/deletion.py:82-94）
                elif k == "deletion":
                    rowdeath += 1         # ★ 行の死（verbatim_deletion は数えない）
            cs = d.get("charge_source") or {}
            rows1 += len(cs.get("①") or [])
            for e in cs.get("①_穴埋め") or []:
                if e.get("前") is not None and e.get("後") is not None and e["後"] < e["前"]:
                    hdec += 1
    births = assims = born_rows = 0; alive_end = None
    for line in open(O / "side" / cell / f"{stem}.jsonl", encoding="utf-8"):
        d = json.loads(line)
        k = d.get("kind")
        if k == "birth":
            births += 1; born_rows += d.get("m_alloc") or 0
        elif k == "assim":
            assims += 1
        elif k == "final":
            alive_end = len(d.get("alive_end") or [])
    done = json.loads((p.parent / f"{stem}.done").read_text(encoding="utf-8"))
    return {"cell": cell, "seed": stem, "登録": births, "走行末の生存定義": alive_end, "同化": assims,
            "話した試行": spk, "棄権": abst, "生まれた行": born_rows, "走行末の生きている行": done["final_m_live_total"],
            "①の行_投影": rows1, "slot_history減_穴埋め": hdec,
            "消えた定義": removed, "死因_行が全部死んだ": removed,
            "死因_そのほか": births - (alive_end or 0) - removed, "行の死": rowdeath,
            "done_final_def_count": done["final_def_count"]}


def main():
    fs = sorted(glob.glob(str(O / "ledgers/cells/*/seed*.jsonl.gz")))
    with concurrent.futures.ProcessPoolExecutor(max_workers=WK) as ex:
        per = list(ex.map(one, fs))
    man = {}
    for line in open(O / "manifest.jsonl", encoding="utf-8"):
        r = json.loads(line)
        if "error" not in r and not r.get("skipped"):
            man[(r["cell"], f"seed{r['seed']:03d}")] = r
    claims = {}
    if L2S != "-" and Path(L2S).exists():
        for x in json.load(open(L2S, encoding="utf-8"))["台帳"]:
            claims[(x["cell"], x["seed"])] = x["計"].get("発話", 0)
    passL = {}
    for x in json.load(open(LS, encoding="utf-8"))["台帳"]:
        for L in (3, 6):
            passL[(x["cell"], x["seed"], L)] = sum(1 for v in x["定義"].values() if L in v.get("pass", []))
    for r in per:
        k = (r["cell"], r["seed"])
        r["水準2の主張"] = claims.get(k)
        r["通過L3"] = passL.get((r["cell"], r["seed"], 3)); r["通過L6"] = passL.get((r["cell"], r["seed"], 6))
        v = (man.get(k) or {}).get("v31") or {}
        for key in ("ext_added", "ext_returned_dead", "c1_projection", "c1_filling"):
            r["v31_" + key] = v.get(key)
    cols = [c for c in per[0] if c not in ("cell", "seed")]
    med = {c: (st.median([r[c] for r in per if r[c] is not None]) if any(r[c] is not None for r in per) else None) for c in cols}
    json.dump({"腕": ARM, "台帳数": len(per), "中央": med, "台帳ごと": per}, open(OUT, "w"), ensure_ascii=False, indent=1)
    print(ARM, "台帳", len(per), json.dumps(med, ensure_ascii=False))


if __name__ == "__main__":
    main()

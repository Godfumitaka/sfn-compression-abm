"""腕が上がるたびに control/ に書く数（2026-09-28 午後の判断「v3.7 の走行（マックの分）」の 3）。★ 判断しない。模型は動かさない（台帳を読むだけ）。
数えるもの（腕の全台帳の和と、台帳ごと）
  中心的過程のラベル：merged/l2s8_<腕>.json（走査の版 8）の定義（名前@生まれた試行）ごとの系列の pass に L が入っている定義の数（L＝2〜6。走行末に生きているかを問わない）。
  誕生：reg_del_events の registration で was_extension＝False の数。
    型またぎで生まれた：そのうち、土台の場面（base_written_at の試行）の型と、今の場面（その試行）の型が違うもの。
  同化：registration で was_extension＝True（すでにある定義に登録した）の数。
    土台と場面の型が違った同化：そのうち、base_written_at の試行の型と、その試行の型が違うもの。
  場面の型 ＝ 世界の試行の motif（台帳の見出しから世界を作り直す。world_hash を突き合わせる）。base_written_at が無い登録は「土台なし」に数える。
出力：<腕の走行根>/merged/型またぎ_<腕>.json（既にあれば作らない）。標準出力に要約。
使い方  python3.12 tools/v37_arm_counts.py <腕の走行根> <腕名> [workers]"""
import collections, concurrent.futures, glob, gzip, json, os, pathlib, sys

REPO = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
arm_root, arm = pathlib.Path(sys.argv[1]).resolve(), sys.argv[2]
WK = int(sys.argv[3]) if len(sys.argv) > 3 else 4
out = arm_root / "merged" / f"型またぎ_{arm}.json"
fl = json.load(open(arm_root / "flag.json", encoding="utf-8"))
SEEDF = str(REPO / json.load(open(REPO / fl["config"], encoding="utf-8")).get("seed_file", "seeds/U-011_seed_v3a2.json"))


def one(p):
    from abm.seed import load_seed
    from abm.world import generate_world
    with gzip.open(p, "rt", encoding="utf-8") as f:
        h = json.loads(next(f))
        ws = generate_world(h["run_seed"], h["trial_count"], ["agent"], seed=load_seed(SEEDF),
                            holdout_include_second_order=bool(h.get("arm_holdout_second_order") or False))
        assert ws.world_hash == h["world_hash"], p
        MOT = [tr.motif for tr in ws.trials]
        C = collections.Counter()
        for line in f:
            r = json.loads(line)
            if r.get("record_type") != "trial":
                continue
            t = r["prediction_order"]
            for e in r.get("reg_del_events") or ():
                if e.get("kind") != "registration":
                    continue
                k = "同化" if e.get("was_extension") else "誕生"
                C[k] += 1
                b = e.get("base_written_at")
                if b is None or not (0 <= b < len(MOT)):
                    C[k + "_土台なし"] += 1
                elif MOT[b] != MOT[t]:
                    C[k + "_型またぎ"] += 1
    return dict(cell=os.path.basename(os.path.dirname(p)), seed=os.path.basename(p)[:7], 数=dict(C))


def main():
    if out.exists():
        d = json.load(open(out, encoding="utf-8"))
    else:
        fs = sorted(glob.glob(str(arm_root / "ledgers/cells/*/seed*.jsonl.gz")))
        with concurrent.futures.ProcessPoolExecutor(max_workers=WK) as ex:
            res = list(ex.map(one, fs))
        tot = collections.Counter()
        for x in res:
            tot.update(x["数"])
        L = collections.Counter(); ndef = 0
        for x in json.load(open(arm_root / "merged" / f"l2s8_{arm}.json", encoding="utf-8"))["台帳"]:
            for K, v in x["定義"].items():
                ndef += 1
                for lv in (v.get("系列") or {}).get("pass", []):
                    L[lv] += 1
        d = {"腕": arm, "台帳": len(fs), "定義（同一性）": ndef, "L": {f"L{k}": L.get(k, 0) for k in (2, 3, 4, 5, 6)},
             "計": dict(tot), "台帳ごと": res, "種": SEEDF}
        json.dump(d, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    t = d["計"]
    print(f"{arm}：台帳 {d['台帳']}・定義 {d['定義（同一性）']:,}・L " + "・".join(f"{k} {v:,}" for k, v in d["L"].items())
          + f"・誕生 {t.get('誕生', 0):,}（型またぎ {t.get('誕生_型またぎ', 0):,}・土台なし {t.get('誕生_土台なし', 0):,}）"
          + f"・同化 {t.get('同化', 0):,}（土台と場面の型が違う {t.get('同化_型またぎ', 0):,}・土台なし {t.get('同化_土台なし', 0):,}）")


if __name__ == "__main__":
    main()

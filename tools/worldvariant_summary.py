"""世界 v4（型の変種、--world-cue、tools/worldvariant.py）の腕ごとの要約と control/ の一行（2026-09-30 深夜の追記 B-2）。★ 判断しない。模型は動かさない（台帳と side を読むだけ）。
世界は作り直さない（型は abm.world._motif_for_trial から、変種と伏せ辺の関係は台帳の研究者用の欄 world_variant・held_out_switch から）。
数えるもの（腕の全走行の和。走行ごとの値も json に残す）
  1 全課題を分母にした正解・誤答・棄権。
  2 誤答の出どころ：F の投影（sme_projection）・F の穴埋め・H の穴埋め・U の穴埋め（side の v39 の記録の穴埋めの席の状態）。
  3 切り替わる関係が伏せられた課題（held_out_switch あり）での正解・誤答・棄権を、変種（A・B）ごとに。
     変種 B で「その関係の変種 A の述語」を答えた数（例：T1 の関係で hold を答えた）も数える（記録だけ）。
  4 型またぎの同化：同化（台帳の登録の記録、was_extension）で、定義が生まれた型と場面の型が違うもの。型の組（生まれた型→場面の型）ごと。
     定義の同一性は 名前＋生まれた試行（登録の記録の誕生）。
  5 定義の数（走行末）、誕生と同化の数。
使い方  python3.12 tools/worldvariant_summary.py <腕の走行根> <腕名> <結果の作業場所> <HOST> [--no-push]
"""
from __future__ import annotations

import collections
import glob
import gzip
import json
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
UPRIGHT_PRED = {"T1": "hold", "T2": "break", "T3": "pull", "T4": "wrap"}


def one(led, side, motif_names):
    from abm.world import _motif_for_trial
    C = collections.Counter()
    cross = collections.Counter()
    fill = {}
    defs_end = None
    if os.path.exists(side):
        for line in open(side, encoding="utf-8"):
            if '"kind": "v39"' in line:
                d = json.loads(line)
                if d.get("kind") == "v39":
                    fill[d["trial"]] = dict((x[0], x[1]) for x in (d.get("fill") or []))
                    defs_end = d.get("defs")
    born = collections.defaultdict(list)   # 名前 → [(生まれた試行, 型)]
    with gzip.open(led, "rt", encoding="utf-8") as f:
        h = json.loads(next(f))
        seed = h["run_seed"]
        for line in f:
            r = json.loads(line)
            if r.get("record_type", "trial") != "trial":
                continue
            t = r["prediction_order"]
            mt = _motif_for_trial(seed, t, motif_names)
            C["課題"] += 1
            sw = r.get("held_out_switch")
            cue = r.get("world_variant")
            if r.get("coverage") == 1:
                if r.get("hit") == 1:
                    C["正解"] += 1
                    out = "正解"
                else:
                    C["誤答"] += 1
                    out = "誤答"
                    rid = (r.get("predicted_edge") or {}).get("relation_id") or ""
                    if rid.startswith("sme_projection__"):
                        C["誤答_F の投影"] += 1
                    elif rid.startswith("filling__"):
                        st = fill.get(t, {}).get(rid)
                        C[{"F": "誤答_F の穴埋め", "H": "誤答_H の穴埋め", "U": "誤答_U の穴埋め"}.get(st, "誤答_穴埋め（席が不明）")] += 1
                    else:
                        C["誤答_不明"] += 1
            else:
                C["棄権"] += 1
                out = "棄権"
            if sw is not None:
                C[f"席_{cue}_{out}"] += 1
                C[f"席_{cue}"] += 1
                if cue == "B" and out == "誤答":
                    pe = r.get("predicted_edge") or {}
                    if pe.get("predicate") == UPRIGHT_PRED.get(sw):
                        C["席_B で A の述語を答えた"] += 1
            reg = r.get("registration_event")
            if reg:
                R = reg["R"]
                if not reg.get("was_extension"):
                    born[R].append((t, mt))
                    C["誕生"] += 1
                else:
                    C["同化"] += 1
                    bs = [b for b in born.get(R, []) if b[0] <= t]
                    if bs:
                        bm = bs[-1][1]
                        if bm != mt:
                            cross[f"{bm}→{mt}"] += 1
                            C["型またぎの同化"] += 1
                    else:
                        C["同化_生まれが分からない"] += 1
    C["走行末の定義"] = defs_end or 0
    return C, cross


def main():
    a = [x for x in sys.argv[1:] if not x.startswith("--")]
    root, arm, results, host = Path(a[0]), a[1], Path(a[2]), a[3]
    no_push = "--no-push" in sys.argv
    fl = json.load(open(root / "flag.json", encoding="utf-8"))
    cfg = json.load(open(REPO / fl["config"], encoding="utf-8"))
    motif_names = tuple(json.load(open(REPO / cfg["seed_file"], encoding="utf-8"))["motif_structure"])
    tot = collections.Counter()
    cross_tot = collections.Counter()
    runs = []
    for led in sorted(glob.glob(str(root / "ledgers/cells/*/seed*.jsonl.gz"))):
        if not os.path.exists(led[:-len(".jsonl.gz")] + ".done"):
            continue
        cell = os.path.basename(os.path.dirname(led))
        sd = os.path.basename(led)[:-len(".jsonl.gz")]
        C, cross = one(led, root / "side" / cell / f"{sd}.jsonl", motif_names)
        tot.update(C)
        cross_tot.update(cross)
        runs.append({"seed": sd, **dict(C), "型またぎ": dict(cross)})
    g = tot.get
    summary = {"腕": arm, "走行": len(runs), "旗": {k: fl.get(k) for k in ("v39_price", "v39_u", "v39_decay", "world_cue", "v310_be", "hist_role", "score_role", "config")},
               **{k: v for k, v in sorted(tot.items())}, "型またぎ（生まれた型→場面の型）": dict(sorted(cross_tot.items())), "走行ごと": runs}
    dest = results / host / arm
    dest.mkdir(parents=True, exist_ok=True)
    (dest / f"世界v4の要約_{arm}.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    seat = lambda c: (f"{g(f'席_{c}', 0):,}（正解 {g(f'席_{c}_正解', 0):,}・誤答 {g(f'席_{c}_誤答', 0):,}・棄権 {g(f'席_{c}_棄権', 0):,}）")  # noqa: E731
    head = f"λ＝{fl.get('v39_price')}" + (f"、U {fl.get('v39_u')}" if fl.get("v39_u") not in (None, "global") else "") + f"、変種 A の確率 {fl.get('world_cue')}"
    line = (f"- {arm}（{head}、走行 {len(runs)}）：全課題 {g('課題', 0):,} のうち 正解 {g('正解', 0):,}・誤答 {g('誤答', 0):,}・棄権 {g('棄権', 0):,}"
            f"／誤答の出どころ F の投影 {g('誤答_F の投影', 0):,}・F の穴埋め {g('誤答_F の穴埋め', 0):,}・H の穴埋め {g('誤答_H の穴埋め', 0):,}・U の穴埋め {g('誤答_U の穴埋め', 0):,}"
            + (f"・不明 {g('誤答_穴埋め（席が不明）', 0) + g('誤答_不明', 0):,}" if g('誤答_穴埋め（席が不明）', 0) + g('誤答_不明', 0) else "")
            + f"／切り替わる関係が伏せられた課題：変種 A {seat('A')}、変種 B {seat('B')}（変種 B の誤答のうち変種 A の述語を答えた {g('席_B で A の述語を答えた', 0):,}）"
            f"／型またぎの同化 {g('型またぎの同化', 0):,}（{', '.join(f'{k} {v}' for k, v in sorted(cross_tot.items())) or 'なし'}）"
            f"／定義の数（走行末の和） {g('走行末の定義', 0):,}／誕生 {g('誕生', 0):,}・同化 {g('同化', 0):,}")
    md = [f"# {arm}：世界 v4（型の変種）での B＋E の要約（{host}）　判断しない", "",
          "tools/worldvariant_summary.py。数は走行の和。走行ごとの値は 世界v4の要約_<腕>.json の「走行ごと」。", "", "- " + line[2:], ""]
    (dest / f"世界v4の要約_{arm}.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    if not no_push:
        subprocess.run([sys.executable, str(REPO / "tools/results_push.py"), str(results), host, arm,
                        f"結果：{host} の {arm}（世界 v4（型の変種）の要約、tools/worldvariant_summary.py）"], check=True)
    print(line)


if __name__ == "__main__":
    main()

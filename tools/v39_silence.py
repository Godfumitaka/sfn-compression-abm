"""v3.9（予算無限）と v3.8 の台帳を、同じ種・同じセル・同じ試行で突き合わせ、片方だけが話した試行を数える（台帳を読むだけ）。
2026-09-29 の v3.10 委任書「B を始める前に」の 1。判断しない。

使い方  python3.12 tools/v39_silence.py <v3.9 の腕> <v3.8 の腕> <セル> <出力の .csv> [種の数＝20]
  腕は ~/v39prod/v39new_n70_hide_Binf のような腕のフォルダ。台帳は <腕>/ledgers/cells/<セル>/seedNNN.jsonl.gz、
  v3.9 の脇の記録は <腕>/side/<セル>/seedNNN.jsonl（kind＝"v39" の行）。

「話した」＝台帳の prediction_kind が EdgePrediction（実際の発話）。試行は行の順で合わせ、instance_id が同じことを確かめる。
v3.8 だけが話した試行の、v3.9 側の分け方（台帳の abstain_reason と candidate_distribution だけで分ける）：
  門の手前     abstain_reason が no_prototype・below_threshold・no_definition・below_tau（tools/v39.py:556-591）
  同点         ambiguous_projection（穴埋めの最大が同点。tools/v39.py:490・605-608）
  埋める席なし no_projectable_relation で candidate_distribution が空（投影の行も、候補を数えた席も無い）
  候補が空     no_projectable_relation で、候補の並びが空の席がある（tools/v39.py:492-494）
  最大が一つ   no_projectable_relation で、どの席も候補があり最大が一つ（残る枝は言い直し禁止の飛ばし tools/v39.py:495-498）
  U の棄権     --v39-u abstain の腕だけ。台帳に席ごとの記録は無いので、この分けは作らない（下の注）
"""
import csv
import gzip
import json
import pathlib
import sys
from collections import Counter

GATE = {"no_prototype", "below_threshold", "no_definition", "below_tau"}


def rows(p):
    with gzip.open(p, "rt", encoding="utf-8") as f:
        out = [json.loads(l) for l in f]
    return out[0], [r for r in out[1:] if r.get("record_type") == "trial"]


def spoke(r):
    return r["prediction_kind"] == "EdgePrediction"


def v39_reason(r):
    ar = r["abstain_reason"]
    if ar in GATE:
        return "門の手前:" + ar
    if ar == "ambiguous_projection":
        return "同点"
    if ar == "no_projectable_relation":
        cd = r.get("candidate_distribution") or []
        if not cd:
            return "埋める席なし"
        if any(not x.get("candidates") for x in cd):
            return "候補が空"
        return "最大が一つ"
    return "その他:" + str(ar)


def main():
    a39, a38, cell, out = map(pathlib.Path, sys.argv[1:5])
    cell = str(cell)
    nseed = int(sys.argv[5]) if len(sys.argv) > 5 else 20
    tab = Counter()
    per_seed = []
    recs = []
    for s in range(1, nseed + 1):
        sd = f"seed{s:03d}"
        h9, B = rows(a39 / "ledgers/cells" / cell / f"{sd}.jsonl.gz")
        h8, A = rows(a38 / "ledgers/cells" / cell / f"{sd}.jsonl.gz")
        if len(A) != len(B) or any(x["instance_id"] != y["instance_id"] for x, y in zip(A, B)):
            raise SystemExit(f"★ {sd}：試行の並びが合わない（{len(A)}・{len(B)}）")
        if h8["world_hash"] != h9["world_hash"] or h8["seed_file_sha256"] != h9["seed_file_sha256"]:
            raise SystemExit(f"★ {sd}：世界の指紋か種のファイルが違う")
        side = {}
        for l in open(a39 / "side" / cell / f"{sd}.jsonl", encoding="utf-8"):
            x = json.loads(l)
            if x.get("kind") == "v39":
                side[x["trial"]] = x
        c = Counter()
        for t, (a, b) in enumerate(zip(A, B)):
            k = (spoke(a), spoke(b))
            c[k] += 1
            if k == (True, False):
                why = v39_reason(b)
                sv = side.get(t) or {}
                states = sorted({x.get("席") for x in (b.get("candidate_distribution") or [])})
                same_R = (a["R_used"] == b["R_used"]) if b["R_used"] else None
                tab[("v38のみ", why, a["prediction_path"], same_R)] += 1
                recs.append({"seed": s, "trial": t, "instance_id": a["instance_id"], "side": "v38のみ",
                             "v38_path": a["prediction_path"], "v38_hit": a["hit"], "v38_R_used": a["R_used"],
                             "v39_reason": why, "v39_abstain_reason": b["abstain_reason"], "v39_R_used": b["R_used"],
                             "v39_seat_states": "|".join(map(str, states)),
                             "v39_F": sv.get("F"), "v39_H": sv.get("H"), "v39_U": sv.get("U")})
            elif k == (False, True):
                tab[("v39のみ", b["prediction_path"], a["abstain_reason"], None)] += 1
                recs.append({"seed": s, "trial": t, "instance_id": a["instance_id"], "side": "v39のみ",
                             "v38_path": None, "v38_hit": a["hit"], "v38_R_used": a["R_used"],
                             "v39_reason": b["prediction_path"], "v39_abstain_reason": None, "v39_R_used": b["R_used"],
                             "v39_seat_states": "", "v39_F": None, "v39_H": None, "v39_U": None,
                             "v39_hit": b["hit"], "v38_abstain_reason": a["abstain_reason"]})
        per_seed.append((s, c[(True, True)], c[(True, False)], c[(False, True)], c[(False, False)]))
    keys = sorted({k for r in recs for k in r})
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        w.writerows(recs)
    print(json.dumps({"per_seed": per_seed, "tab": [[*k, v] for k, v in sorted(tab.items(), key=lambda kv: -kv[1])],
                      "v39_only_hit": sum(1 for r in recs if r["side"] == "v39のみ" and r.get("v39_hit")),
                      "v38_only_hit": sum(1 for r in recs if r["side"] == "v38のみ" and r.get("v38_hit"))},
                     ensure_ascii=False))


if __name__ == "__main__":
    main()

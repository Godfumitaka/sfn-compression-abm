"""候補の記録と台帳の一致を確認し、外れを数えるだけ。"""
from __future__ import annotations
import argparse
from collections import Counter
import csv
import gzip
from itertools import combinations
import json
from pathlib import Path

from codex_answer_campaign import ARMS, body_sha, now


def category(row):
    """Uを先に分け、F・Hは門を通る正解候補／門の下だけ／無しに分ける。"""
    if row["seat_state"] == "U":
        return "U"
    if row["seat_state"] not in ("F", "H"):
        raise ValueError(f"不明の出どころ：{row['seat_state']}")
    return availability(row)


def availability(row):
    if int(row["cand_other_correct_passed"]):
        return "a"
    if int(row["cand_other_correct"]):
        return "b"
    return "c"


def read_arm(base, arm, count, world):
    root = base / "outputs" / arm
    dest = base / "results/mac" / arm
    with gzip.open(dest / f"answers_{arm}.csv.gz", "rt", encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    by_trial = {}
    candidate_count = 0
    for row in rows:
        key = (int(row["seed"]), int(row["trial"]))
        assert key not in by_trial, (arm, key)
        by_trial[key] = row
        cands = json.loads(row["cand_answers"])
        assert len(cands) == int(row["cand_n"])
        assert len({c["def_id"] for c in cands}) == len(cands)
        selected = [c for c in cands if c["selected"]]
        assert len(selected) == 1
        selected = selected[0]
        assert selected["def_id"] == row["def_id"]
        assert selected["gate_pass"] == 1
        assert selected["pred"] == row["pred"]
        assert selected["source"] == row["source"]
        assert selected["seat_state"] == row["seat_state"]
        assert selected["hit"] == int(row["hit"])
        for c in cands:
            assert c["support_ratio"] == c["support"] / c["m_live"]
            assert c["gate_pass"] == int(c["support"] >= __import__('math').ceil(.67 * c["m_live"]))
        others = [c for c in cands if not c["selected"]]
        assert int(row["cand_other_correct"]) == int(any(c["hit"] for c in others))
        assert int(row["cand_other_correct_passed"]) == int(any(c["hit"] and c["gate_pass"] for c in others))
        tied = [c for c in cands if c["support_ratio"] == selected["support_ratio"] and c["pred"] is not None]
        pairs = sum((a["pred"], a["arguments"]) != (b["pred"], b["arguments"]) for a, b in combinations(tied, 2))
        assert int(row["cand_tie_disagree_pairs"]) == pairs
        assert int(row["cand_tie_disagree"]) == int(pairs > 0)
        candidate_count += len(cands)
    hits = coverage = total = 0
    files = sorted(root.glob("ledgers/cells/*/seed*.jsonl.gz"))
    assert len(files) == count
    hashes = [json.loads(s) for s in (dest / "sha256.jsonl").read_text().splitlines()]
    assert len(hashes) == count
    seen = set()
    for path, saved in zip(files, hashes):
        seed = int(path.name.split('.')[0].removeprefix("seed"))
        seen.add(seed)
        digest, lines, _ = body_sha(path)
        assert lines == 1740 and saved["body_sha256"] == digest and saved["deleted"] is False
        with gzip.open(path, "rt", encoding="utf-8") as f:
            next(f)
            for trial, line in enumerate(f):
                d = json.loads(line)
                total += 1
                coverage += int(d["coverage"])
                hits += int(d["hit"])
                if not d["coverage"]:
                    assert (seed, trial) not in by_trial
                    continue
                row = by_trial[(seed, trial)]
                assert int(row["hit"]) == int(d["hit"])
                assert row["R"] == d["R_used"]
                edge, held = d["predicted_edge"], d["held_out_content"]
                assert row["pred"] == edge["predicate"]
                for c in json.loads(row["cand_answers"]):
                    if c["selected"]:
                        assert c["arguments"] == edge["arguments"]
                    hit = int(c["pred"] is not None and c["pred"] == held["predicate"] and c["arguments"] == held["arguments"])
                    assert c["hit"] == hit
    assert seen == set(range(1, count + 1))
    assert coverage == len(rows)
    assert hits == sum(int(r["hit"]) for r in rows)
    breakdown, uref, cats = Counter(), Counter(), Counter()
    tie_trials = tie_pairs = tie_error_trials = tie_error_pairs = 0
    for r in rows:
        assert r["same_motif"] in ("0", "1")
        if world:
            tie_trials += int(r["cand_tie_disagree"])
            tie_pairs += int(r["cand_tie_disagree_pairs"])
        if int(r["hit"]):
            continue
        k = category(r)
        cats[k] += 1
        breakdown[(k, r["seat_state"], int(r["same_motif"]))] += 1
        if k == "U":
            uref[(availability(r), int(r["same_motif"]))] += 1
        if world:
            tie_error_trials += int(r["cand_tie_disagree"])
            tie_error_pairs += int(r["cand_tie_disagree_pairs"])
    errors = coverage - hits
    assert errors == sum(cats.values())
    assert cats["U"] == sum(uref.values())
    return {"arm": arm, "runs": count, "total": total, "answered": coverage, "correct": hits,
            "errors": errors, "abstain": total - coverage, "candidate_records": candidate_count,
            "categories": dict(cats), "breakdown": [{"category": k, "source": st, "same_motif": same, "count": n}
                                                        for (k, st, same), n in sorted(breakdown.items())],
            "u_reference": [{"availability": k, "same_motif": same, "count": n} for (k, same), n in sorted(uref.items())],
            "tie_answered_trials": tie_trials, "tie_answered_pairs": tie_pairs,
            "tie_error_trials": tie_error_trials, "tie_error_pairs": tie_error_pairs,
            "validation": "候補列・門・採点・選択結果・台帳全行・全本体sha256の一致確認済み"}


def table(header, rows):
    return ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)] + ["| " + " | ".join(map(str, row)) + " |" for row in rows]


def report(base, records):
    names = {"a": "(a) 選び間違い", "b": "(b) 記憶にはあったが門の下", "c": "(c) 記憶に無い", "U": "U の当てずっぽう"}
    lines = ["# 外れの分け方（Codex、2026-09-30）", "", f"作成：{now()}。数と事実のみ。", "",
        "F は述語名が固定された席、H は候補の履歴がある席、U は候補の履歴が無い席。",
        "支持の割合は、定義の F・H の席のうち場面に写った席の割合。発話の門はこの割合が 0.67 以上という条件。",
        "候補の答えは門の下も含め、実際の選択時の対応・同じ記憶・正解を見る前の状態で計算した。正誤は述語と引数の両方の一致で数えた。",
        "U の外れを先に分け、残る F・H の外れを三分類した。正しい別候補が門を通れば (a)、門の下にだけあれば (b)、どの候補にも無ければ (c)。",
        "型は場面の骨組みの種類。『同じ型』は選ばれた定義が生まれた場面の型と現在の型が同じこと。", "",
        "- 基準：B＋E は v3.10hsa-main（f714394）、世界 v4 は v4v-main（16aff42）。記録を足した版と旗は各腕の flag.json。",
        "- Python 3.12.13。設定 config/sweep_b2_hide_s1_2026-09-22.json。最頻セル f0.5000_th2.1000_first_order。各1,740試行。",
        "- B＋E：種1〜20、λ＝L90・0.15・0.2・0.3・0.5。世界v4：種1〜10、λ＝0・L90、変種Aの確率0.8。L90＝0.09900039055209096。",
        "- 本番の旗：--v310-be --v39-decay actr --v39-budget inf --v39-price λ --hist-role --score-role --dump-answers。付随する既存の旗は flag.json とコードの tools/codex_answer_campaign.py。",
        "- 台帳は専用作業場所の outputs/<腕>/ledgers/ に全部保持。見出しを除いた本体のsha256（内容の指紋）は mac/<腕>/sha256.jsonl。", "", "## 腕ごとの件数", ""]
    lines += table(["腕", "本数", "全試行", "正解", "外れ", "棄権", "(a)", "(b)", "(c)", "U"],
                   [(r["arm"], r["runs"], r["total"], r["correct"], r["errors"], r["abstain"],
                     *[r["categories"].get(k, 0) for k in ("a", "b", "c", "U")]) for r in records])
    for r in records:
        bd = {(v["category"], v["source"], v["same_motif"]): v["count"] for v in r["breakdown"]}
        ur = {(v["availability"], v["same_motif"]): v["count"] for v in r["u_reference"]}
        lines += ["", f"## {r['arm']}", "", "F・H の外れ：", ""]
        lines += table(["分類", "F・同じ型", "F・それ以外", "H・同じ型", "H・それ以外", "合計"],
                       [(names[k], *[bd.get((k, st, same), 0) for st, same in (("F", 1), ("F", 0), ("H", 1), ("H", 0))],
                         r["categories"].get(k, 0)) for k in ("a", "b", "c")])
        lines += ["", "U の外れの参考表（主分類はすべて U）：", ""]
        lines += table(["正しく答えられる別候補", "全候補で有無", "門を通る候補で有無", "同じ型", "それ以外", "合計"],
                       [(label, any_, passed, ur.get((k, 1), 0), ur.get((k, 0), 0), ur.get((k, 1), 0) + ur.get((k, 0), 0))
                        for k, label, any_, passed in (("a", "門を通る候補にあり", 1, 1), ("b", "門の下にだけあり", 1, 0), ("c", "どの候補にも無し", 0, 0))])
    lines += ["", "## 世界 v4 の同点候補の答えの違い", "",
              "同点は選ばれた定義と支持の割合が同じこと。両方が答えを出し、述語または引数が異なる候補対を数えた。棄権した候補には答えが無いので対に含めない。",
              "『試行数』はそのような対が一つ以上ある試行を一件、『候補対数』は各試行内の異なる定義の組を一件として合計した。対象は実際に答えた試行。", ""]
    lines += table(["腕", "答えた全試行", "違う答えの対がある試行数", "候補対数", "外れ試行", "外れで対がある試行数", "外れでの候補対数"],
                   [(r["arm"], r["answered"], r["tie_answered_trials"], r["tie_answered_pairs"], r["errors"],
                     r["tie_error_trials"], r["tie_error_pairs"]) for r in records if r["arm"].startswith("v4vc_")])
    lines += ["", "## 記録と台帳の照合", "",
              "全腕について、実際に答えた試行の件数・述語・引数・当たり外れを台帳と照合した。候補の支持・門・正誤・別候補の正解有無・同点の件数を記録から再計算して一致を確認した。", ""]
    lines += table(["腕", "答えの行数", "候補の記録数", "台帳本数", "照合"],
                   [(r["arm"], r["answered"], r["candidate_records"], r["runs"], "一致") for r in records])
    (base / "results/control/2026-09-30_外れの分け方_Codex.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (base / "results/control/2026-09-30_外れの分け方_Codex.json").write_text(json.dumps(records, ensure_ascii=False, indent=2) + "\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("workspace", type=Path)
    ap.add_argument("--completed-only", action="store_true")
    args = ap.parse_args()
    base = args.workspace.resolve()
    records = []
    for arm, _, _, count, world in ARMS:
        if args.completed_only and not (base / "results/mac" / arm / "README.md").exists():
            continue
        records.append(read_arm(base, arm, count, world))
        print(arm, records[-1]["categories"], flush=True)
    report(base, records)


if __name__ == "__main__":
    main()

"""SME再生を照合し、旧版と同じ分類と記憶量の表の一本分を保存する。"""
from collections import Counter
from itertools import zip_longest
from pathlib import Path
import argparse
import gzip
import json
from common import CELL


def json_rows(path):
    opener = gzip.open if path.name.endswith(".gz") else open
    with opener(path, "rt", encoding="utf-8") as stream:
        for line in stream:
            yield json.loads(line)


def summarise(original, replay, dest, seed):
    assert 1 <= seed <= 5
    fl = json.loads((original / "flag.json").read_text())
    assert fl["shop_world"] in (1, 2) and fl["sme2017"]
    assert not fl.get("sme_support_ratio")
    ledger = original / "ledgers/cells" / CELL / f"seed{seed:03d}.jsonl.gz"
    side = original / "side" / CELL
    replay_side = replay / "side" / CELL
    rows = json_rows(ledger)
    header = next(rows)
    trials = header["trial_count"]
    assert header["run_seed"] == seed
    counts = {cue: Counter() for cue in ("e", "n")}
    money = {row["trial"]: row["C_end"] for row in json_rows(side / f"seed{seed:03d}.jsonl")
             if row.get("kind") == "v310be"}
    entity_rows = list(json_rows(original / "research" / CELL / f"seed{seed:03d}.entities.jsonl"))
    entities = {r["trial"]: r for r in entity_rows if r["run_seed"] == seed}
    assert sorted(entities) == list(range(trials))
    check = json.loads((replay_side / f"seed{seed:03d}.sme.analysis-check.json").read_text())
    assert check["main_legacy_calls"] == 0
    sums = Counter();max_bits = 0;final = None;public = Counter();n = 0
    candidates = json_rows(replay_side / f"seed{seed:03d}.sme.candidates.jsonl.gz")
    memories = json_rows(replay_side / f"seed{seed:03d}.sme.memory.jsonl.gz")
    for row, candidate, memory in zip_longest((r for r in rows if r.get("record_type") == "trial"), candidates, memories):
        assert row is not None and candidate is not None and memory is not None
        t = row["prediction_order"]
        assert t == candidate["trial"] == memory["trial"] == n
        if row["R_used"] is not None:
            assert candidate["chosen_R"] == row["R_used"]
        elif candidate["chosen_R"] is not None:
            assert row["abstain_reason"] == "below_tau"
        assert candidate["original_hit"] == bool(row["hit"])
        prediction = candidate["prediction"]
        if row["prediction_kind"] == "Abstain":
            assert prediction == {"abstain_reason": row["abstain_reason"]}
        else:
            assert prediction == row["predicted_edge"]
        assert money[t] == memory["total"], f"試行{t}：元のC_endと記憶の内訳が違う"
        er = entities[t]
        assert er["level"] == fl["shop_deco"]
        assert er["graph_id"] == row["instance_id"] == memory["graph_id"]
        assert all(er[k] == memory[k] for k in ("full_entity_count", "public_entity_count"))
        public[memory["public_entity_count"]] += 1
        keys = ("G", "Idef", "S", "seat2", "Hc", "Fc", "total", "defs", "nF", "nH", "nU")
        final = {k: memory[k] for k in keys}
        sums.update(final);max_bits = max(max_bits, memory["total"])
        if row["held_out_is_door"]:
            cue = row["shop_cue"]
            outcome = "黙り" if row["prediction_kind"] == "Abstain" else "正解" if row["hit"] else "外れ"
            counts[cue][outcome] += 1
            if outcome == "外れ":
                counts[cue]["選び間違い" if candidate["correct_gate_passed"] else "区別の喪失"] += 1
        n += 1
    assert n == trials
    original_states = side / f"seed{seed:03d}.sme.states.jsonl.gz"
    replay_states = replay_side / original_states.name
    # 実測時間の欄を持たない、予測前・答え・更新後の全フレームは圧縮バイトも一致する。
    from common import digest
    assert digest(original_states) == digest(replay_states)
    result = {"selection": "N3", "retention": "D" if fl.get("use_forget") is not None else "A",
              "level": fl["shop_deco"], "world": fl["shop_world"], "seed": seed, "trial_count": trials,
              "days": {k: dict(v) for k, v in counts.items()},
              "memory": {"trials": n, "mean": {k: v / n for k, v in sums.items()},
                         "max_total_bits": max_bits, "final": final},
              "public_entity_distribution": dict(public),
              "validation": {"native_sme_replay": True, "state_gzip_bytes_equal": True,
                  "predictions_checked": n, "C_end_mismatch": 0, "public_entities_checked": n,
                  "legacy": check}, "extra_research_scene_records_excluded": len(entity_rows) - n}
    dest.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("original", type=Path);parser.add_argument("replay", type=Path)
    parser.add_argument("dest", type=Path);parser.add_argument("seed", type=int)
    a = parser.parse_args()
    summarise(a.original, a.replay, a.dest, a.seed)

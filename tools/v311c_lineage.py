"""走行後の研究者用の系譜。個体へ値を渡さず、通信の元記録を変更しない。

単位は（個体、定義名、誕生試行）。受信した束の番号を親として集合で引き継ぐ。
同化後の全内容に同じ候補が付くため、席の由来・具体的誤答の因果を証明しない。
"""
import json
from pathlib import Path


def write_lineage(comm_path, out_path, groups):
    defs = {}
    with Path(comm_path).open(encoding="utf-8") as source, Path(out_path).open("w", encoding="utf-8") as dest:
        for line in source:
            row = json.loads(line)
            if row["kind"] == "bundle" and not row.get("empty"):
                key = (row["agent"], row["R"], row["R_born"])
                parents = defs.get(key, frozenset())
                dest.write(json.dumps({"kind": "utterance", "bundle": row["bundle"], "agent": row["agent"],
                                       "group": groups[row["agent"]], "t": row["t"], "pred": row["pred"],
                                       "R": row["R"], "R_born": row["R_born"], "send": row["send"],
                                       "relations": row["relations"], "parents": sorted(parents)}, ensure_ascii=False) + "\n")
            elif row["kind"] == "recv" and row.get("result") in ("同化", "誕生"):
                key = (row["agent"], row["R"], row["R_born"])
                defs[key] = defs.get(key, frozenset()) | {row["bundle"]}
                dest.write(json.dumps({"kind": "incorporation", "bundle": row["bundle"], "agent": row["agent"],
                                       "group": groups[row["agent"]], "t": row["t"], "R": row["R"],
                                       "R_born": row["R_born"], "parents": sorted(defs[key])},
                                      ensure_ascii=False) + "\n")

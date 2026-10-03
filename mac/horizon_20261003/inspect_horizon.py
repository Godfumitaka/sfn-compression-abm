"""走行はせず、走行長の参照と同じ定義の記憶費用を記録する。"""

import argparse
import csv
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--source", type=Path, default=ROOT / "source")
parser.add_argument("--out", type=Path, default=ROOT / "inspection")
args = parser.parse_args()
SOURCE = args.source.resolve()
OUT = args.out.resolve()
OUT.mkdir(parents=True, exist_ok=True)
sys.path[:0] = [str(SOURCE / "tools"), str(SOURCE)]

import v39
import strictpc
from abm.definition import Constituent, FrozenPrice, NamedDefinition
from abm.domains import Relation

pattern = re.compile(r"\bT\b|horizon|trial_count|decay_ladder|actr_weights|len\([^\n]*trials")
paths = subprocess.check_output(["git", "ls-files", "*.py"], cwd=SOURCE, text=True).splitlines()
hits = []
for name in paths:
    if name.startswith("llm_trial/"):
        continue
    p = SOURCE / name
    if not p.is_file():
        continue
    for line_number, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
        if pattern.search(line):
            hits.append({"file": name, "line": line_number, "text": line.strip()})
with (OUT / "T_使用候補.csv").open("w", encoding="utf-8", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=["file", "line", "text"], lineterminator="\n")
    writer.writeheader()
    writer.writerows(hits)

price = FrozenPrice(1.0, 0, 0.0, 2)
normal = NamedDefinition("d_normal", (
    Constituent(0, 0, Relation("r0", "push", ("x", "y")), price),
    Constituent(1, 0, Relation("r1", "fold", ("x", "y")), price),
), 2, 0)
typed = NamedDefinition("d_typed", (
    Constituent(0, 0, Relation("r2", "parent", ("missing_child", "x")), price),
    Constituent(1, 0, Relation("r3", "leaf", ("x", "y")), price),
), 2, 0)
v39.CFG.update(dict_index={p: i for i, p in enumerate(("push", "fold", "parent", "leaf"))})
base_structure = v39.structure_bits

def measure(d, label, fn, entity_count):
    history = {(d.name, r.slot_index): {r.relation.predicate: 1} for r in d.constituents}
    lengths = {r.relation.predicate: 2 for r in d.constituents}
    m = len(d.constituents)
    rows = []
    for t in (1740, 3480):
        v39.CFG["T"] = t
        v39.CTX["struct_cache"] = {}
        sb = fn(d)
        independent = v39.clog2(t) + v39.I(m) + v39.I(entity_count)
        for row in d.constituents:
            independent += v39.I(len(row.relation.arguments))
            for a in row.relation.arguments:
                is_relation = a == "missing_child"
                independent += 1 + v39.clog2(m if is_relation else entity_count)
        assert sb == independent, (label, t, sb, independent)
        rows.append({"T": t, "ceil_log2_T": v39.clog2(t), "structure_bits": sb,
                     "definition_bits": v39.definition_bits(d, history, lengths)})
    assert rows[1]["structure_bits"] - rows[0]["structure_bits"] == 1
    assert rows[1]["definition_bits"] - rows[0]["definition_bits"] == 1
    return {"case": label, "m": m, "e": entity_count,
            "relations": [{"id": r.relation.relation_id, "name": r.relation.predicate,
                           "arguments": list(r.relation.arguments), "state": "F",
                           "history": {r.relation.predicate: 1}, "name_code_bits": 2}
                          for r in d.constituents], "measurements": rows,
            "structure_difference_bits": 1, "definition_difference_bits": 1}

cases = [measure(normal, "tools/v39.py:124", base_structure, 2)]
strictpc.install()
strictpc.KINDS.update(r2=("関係", "物"), r3=("物", "物"))
cases.append(measure(typed, "tools/strictpc.py:356", v39.structure_bits, 2))
assert strictpc.STATS["struct_calls_changed"] > 0
summary = {"source_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=SOURCE, text=True).strip(),
           "branch": subprocess.check_output(["git", "branch", "--show-current"], cwd=SOURCE, text=True).strip(),
           "python": sys.version, "simulation_runs": 0, "seed_data_read": False,
           "cases": cases, "lambda": 0.01873710622997919,
           "lambda_times_one_bit": 0.01873710622997919,
           "inventory_files": len(set(h["file"] for h in hits)), "inventory_lines": len(hits)}
(OUT / "small_example.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps(summary, ensure_ascii=False))

"""補助記録の無い黙りを推定しないことと、集計の欄の分離。"""
import csv
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools/verb"))
from aggregate import aggregate
from followup import abstain_detail


def test_no_probe_tie_state_is_inferred():
    assert abstain_detail("ambiguous_projection", {}, probe=True) == "ambiguous_details_not_recorded"


def test_queried_u_tie_requires_recorded_state_and_tie_mark():
    assert abstain_detail("ambiguous_projection", {}, {"held_state": "U", "held_tied": "1"}) == "ambiguous_queried_U_tie"
    assert abstain_detail("ambiguous_projection", {}, {"held_state": "U", "held_tied": "0"}) == "ambiguous_details_not_recorded"


def test_selected_gate_failure_does_not_imply_no_other_passed_definition():
    assert abstain_detail("below_tau", {"tau_passed_defs": []}) == "below_tau_no_passed_definition"
    assert abstain_detail("below_tau", {"tau_passed_defs": [{"R": "other"}]}) == "below_tau_other_definition_passed"


def test_u_condition_and_u_seat_count_are_separate(tmp_path):
    run = tmp_path / "sample"
    (run / "analysis").mkdir(parents=True)
    (run / "complete.json").write_text("{}")
    (run / "resources.json").write_text("{}")
    summary = {"overregularization": [], "novel": [], "recovery": [], "classification": {}, "selected_name_states": {},
               "answering": [], "memory": [{"t": 5000, "definitions": 2, "F": 1, "H": 2, "U": 3, "bits": 100}]}
    (run / "analysis/summary.json").write_text(json.dumps(summary))
    output = aggregate(tmp_path, {"runs": [{"label": "sample", "seed": 1, "arm": "A", "U": "global"}]})
    with (output / "memory.csv").open() as f:
        row = next(csv.DictReader(f))
    assert row["U"] == "global"
    assert row["U_seats"] == "3"
    assert "100.0000" in (output / "tables.md").read_text()

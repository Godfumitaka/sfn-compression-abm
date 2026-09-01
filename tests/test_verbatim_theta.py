from __future__ import annotations

from abm.domains import (
    AgentConfig,
    CorrectionMode,
    Prototype,
    RelationGraph,
    VerbatimTrace,
)
from sweep import cell_name, enumerate_runs, parse_cell_name


def test_verbatim_threshold_falls_back_to_theta_prime() -> None:
    config = AgentConfig(0.0, CorrectionMode.NONE, theta_prime=0.1432)

    assert config.verbatim_threshold == config.theta_prime


def test_verbatim_threshold_uses_explicit_value() -> None:
    config = AgentConfig(
        0.0,
        CorrectionMode.NONE,
        theta_prime=0.1432,
        verbatim_theta=0.3842,
    )

    assert config.verbatim_threshold == 0.3842


def test_prototype_alive_boundary_for_verbatim_threshold() -> None:
    trace = VerbatimTrace(0, RelationGraph("scene"))
    prototype = Prototype((trace,))

    assert prototype.alive(48, 0.1432) == (trace,)
    assert prototype.alive(49, 0.1432) == ()


def test_cell_name_and_parser_support_independent_verbatim_theta() -> None:
    assert cell_name(0.0, 0.1432, "all") == "f0.0000_th0.1432_all"
    assert cell_name(0.0, 0.1432, "all", 0.1432) == "f0.0000_th0.1432_all"
    assert cell_name(0.0, 0.1432, "all", 0.3842) == "f0.0000_th0.1432_vt0.3842_all"
    parsed = parse_cell_name("f0.0000_th0.1432_vt0.3842_first_order")
    assert parsed["repair_scope"] == "first_order"


def test_enumerate_runs_without_verbatim_axis_preserves_cells_and_count() -> None:
    cfg = {
        "axes": {
            "f": [0.0, 0.5],
            "theta_prime": [0.1432],
            "repair_scope": ["first_order", "all"],
        },
        "seeds": {"start": 1, "count": 2},
    }

    runs = enumerate_runs(cfg)

    assert len(runs) == 8
    assert {run["cell"] for run in runs} == {
        "f0.0000_th0.1432_all",
        "f0.0000_th0.1432_first_order",
        "f0.5000_th0.1432_all",
        "f0.5000_th0.1432_first_order",
    }
    assert all(run["verbatim_theta"] is None for run in runs)

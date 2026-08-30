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


def test_explicit_verbatim_threshold_is_independent() -> None:
    config = AgentConfig(
        0.0,
        CorrectionMode.NONE,
        theta_prime=0.1432,
        verbatim_theta=0.3842,
    )
    assert config.verbatim_threshold == 0.3842


def test_verbatim_trace_expires_on_trial_49() -> None:
    trace = VerbatimTrace(written_at=0, scene=RelationGraph("scene"))
    prototype = Prototype((trace,))
    assert prototype.alive(48, 0.1432) == (trace,)
    assert prototype.alive(49, 0.1432) == ()


def test_cell_name_is_backward_compatible_and_parseable() -> None:
    assert cell_name(0.0, 0.1432, "all") == "f0.0000_th0.1432_all"
    assert cell_name(0.0, 0.1432, "all", 0.1432) == "f0.0000_th0.1432_all"
    assert cell_name(0.0, 0.1432, "all", 0.3842) == "f0.0000_th0.1432_vt0.3842_all"
    assert parse_cell_name("f0.0000_th0.1432_all") == (0.0, 0.1432, "all", None)
    assert parse_cell_name("f0.0000_th0.1432_vt0.3842_all") == (
        0.0,
        0.1432,
        "all",
        0.3842,
    )


def test_enumerate_runs_without_verbatim_axis_preserves_cells_and_count() -> None:
    axes = {
        "axes": {
            "f": [0.0, 0.5],
            "theta": [0.1432, 0.3842],
            "repair_scope": ["first", "all"],
        }
    }
    tasks = enumerate_runs(axes)
    assert len(tasks) == 8
    assert [task["cell_name"] for task in tasks] == [
        cell_name(f_value, theta, scope)
        for f_value in axes["axes"]["f"]
        for theta in axes["axes"]["theta"]
        for scope in axes["axes"]["repair_scope"]
    ]
    assert all(task["verbatim_theta"] is None for task in tasks)

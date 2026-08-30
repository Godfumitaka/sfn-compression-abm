"""掃引セルの列挙と、再開可能なセル名の相互変換。"""

from __future__ import annotations

from itertools import product
import math
import re
from typing import Any, Mapping


_CELL_RE = re.compile(
    r"^f(?P<f>-?\d+(?:\.\d+)?)_th(?P<theta>-?\d+(?:\.\d+)?)"
    r"(?:_vt(?P<verbatim_theta>-?\d+(?:\.\d+)?))?_(?P<scope>.+)$"
)


def cell_name(f_value, theta, scope, verbatim_theta=None):
    """腕の設定値からディレクトリ名を作る（旧形式を既定として維持する）。"""

    base = f"f{f_value:.4f}_th{theta:.4f}"
    if verbatim_theta is not None and verbatim_theta != theta:
        base += f"_vt{verbatim_theta:.4f}"
    return f"{base}_{scope}"


def parse_cell_name(name: str) -> tuple[float, float, str, float | None]:
    """旧形式と逐語閾値つき形式のセル名を解析する。"""

    match = _CELL_RE.fullmatch(name)
    if match is None:
        raise ValueError(f"不正なセル名: {name}")
    raw_verbatim_theta = match.group("verbatim_theta")
    return (
        float(match.group("f")),
        float(match.group("theta")),
        match.group("scope"),
        None if raw_verbatim_theta is None else float(raw_verbatim_theta),
    )


def validate(config: Mapping[str, Any]) -> None:
    """掃引軸の設定値を検査する。"""

    axes = config.get("axes", config)
    values = axes.get("verbatim_theta", ())
    if not isinstance(values, (list, tuple)):
        values = (values,)
    if any(
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        or value <= 0
        for value in values
    ):
        raise ValueError("verbatim_theta は 0 より大きい実数でなければなりません")


def enumerate_runs(config: Mapping[str, Any]) -> list[dict[str, Any]]:
    """f・theta・repair_scope・verbatim_theta の直積を task として列挙する。"""

    validate(config)
    axes = config.get("axes", config)
    f_values = axes.get("f", axes.get("f_value", ()))
    theta_values = axes.get("theta", axes.get("theta_prime", ()))
    scopes = axes.get("repair_scope", axes.get("scope", ()))
    verbatim_values = axes.get("verbatim_theta", (None,))
    tasks = []
    for f_value, theta, scope, verbatim_theta in product(
        f_values, theta_values, scopes, verbatim_values
    ):
        task = {
            "f_value": f_value,
            "theta": theta,
            "repair_scope": scope,
            "verbatim_theta": verbatim_theta,
        }
        task["cell_name"] = cell_name(f_value, theta, scope, verbatim_theta)
        tasks.append(task)
    return tasks

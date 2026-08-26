from __future__ import annotations

from copy import deepcopy
import json

import pytest

from abm.seed import DEFAULT_SEED_PATH, SeedValidationError, load_seed, seed_hash, validate_seed


def _raw_seed() -> dict:
    return json.loads(DEFAULT_SEED_PATH.read_text(encoding="utf-8"))


def test_seed_hash_and_five_internal_checks_pass() -> None:
    seed = load_seed()

    assert seed.sha256 == "ddc0e4ae928c08ce252c6f9456eb74e9e8044716a4b4e4c84d6c36daa974d858"
    validate_seed(seed.data)


def test_seed_is_deeply_read_only() -> None:
    seed = load_seed()

    with pytest.raises(TypeError):
        seed.data["version"] = "changed"  # type: ignore[index]
    with pytest.raises(TypeError):
        seed.data["bags"]["stone"] = ()  # type: ignore[index]


def test_load_seed_stops_on_hash_mismatch(tmp_path) -> None:
    raw = _raw_seed()
    raw["version"] = "tampered"
    path = tmp_path / "seed.json"
    path.write_text(json.dumps(raw), encoding="utf-8")

    with pytest.raises(SeedValidationError, match="sha256"):
        load_seed(path)


def test_internal_inconsistency_fails_even_with_matching_hash(tmp_path) -> None:
    raw = deepcopy(_raw_seed())
    raw["constituents"][0]["c"] = 6
    raw["sha256"] = seed_hash(raw)
    path = tmp_path / "seed.json"
    path.write_text(json.dumps(raw), encoding="utf-8")

    with pytest.raises(SeedValidationError, match=r"constituents\[0\]\.c"):
        load_seed(path)

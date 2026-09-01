"""委任書(C) §4 の検収。β の項を配線したことの動的試験（D14 の検出）。

V_q ＝ P_q·a_q ＋ β·((1−p_R)/p_R)·P_ext,q·a_q ＋ w·(embed_q/ℓ_q)   （U-09n）
★ 保持値は「R 適用あたり」の尺度なので、第一項に p_R は掛けない。
"""

from __future__ import annotations

import pytest

from abm.accounting import (
    D_COLD_MAX_PRIOR,
    adoption_rate,
    constituent_value,
    constituent_value_terms,
    decay_ladder,
    external_participation,
    initial_merit,
    participation,
    total_opportunity,
    update_merit,
)
from abm.definition import (
    Constituent,
    EmbedState,
    ExceptionAccumulator,
    FrozenPrice,
    MeritAccumulator,
    NamedDefinition,
)
from abm.deletion import apply_theta
from abm.domains import AgentConfig, AgentState, CorrectionMode, Relation
from abm.loop import run_longitudinal
from abm.world import generate_world


HORIZON = 200
LADDER = decay_ladder(HORIZON)
PRICE = FrozenPrice(4.0, 4, 8.0, 4)
NO_EXCEPTION = ExceptionAccumulator((0.0,) * 16, 0.0, 0)
NO_EMBED = EmbedState(0, 0.0, 0.0)


def _merit(*, applied: tuple[bool, ...], matched: tuple[bool, ...] = (),
           external: tuple[bool, ...] = (), base_age: int = 0) -> MeritAccumulator:
    """一試行ずつ update_merit を回して積み上げる。★ 閉形式と突き合わせる基準。"""

    accumulator = initial_merit(0, 0, base_age, HORIZON)
    for index, is_applied in enumerate(applied):
        accumulator = update_merit(
            accumulator,
            LADDER,
            matched=matched[index] if index < len(matched) else is_applied,
            filled_scored=False,
            alpha=0.0,
            applied=is_applied,
            external_use=external[index] if index < len(external) else False,
        )
    return accumulator


# ---------------------------------------------------------------- §4-1 後方互換
def test_c4_1_beta_zero_reproduces_the_old_formula_bit_for_bit() -> None:
    """β=0 の V は、β の項を持たなかった旧式と浮動小数点まで一致する。"""

    merit = _merit(applied=(True, False, True, True, False))
    for w in (0.0, 0.35):
        legacy = (
            participation(merit) * ((PRICE.saving - 0.0) / PRICE.ell_frozen)
            + w * 0.0 / PRICE.ell_frozen
        )
        assert constituent_value(
            PRICE, merit, NO_EXCEPTION, NO_EMBED, w=w, kappa=1.0,
            beta=0.0, decay=LADDER, elapsed=5,
        ) == legacy


def test_c4_1_beta_zero_needs_no_ladder() -> None:
    """β=0 の呼び出しは減衰梯子も経過試行数も要らない（既存の呼び出しが壊れない）。"""

    merit = _merit(applied=(True, False, True))
    assert constituent_value(PRICE, merit, NO_EXCEPTION, NO_EMBED, w=0.0, kappa=1.0) == pytest.approx(
        constituent_value(PRICE, merit, NO_EXCEPTION, NO_EMBED, w=0.0, kappa=1.0,
                          beta=0.0, decay=LADDER, elapsed=3)
    )


# ------------------------------------------------- §0-2 第一項に p_R を掛けない
def test_c0_2_first_term_carries_no_p_r_factor() -> None:
    """第一項は P·a のまま。★ M-019 の「試行あたり」式（p_R 倍）ではない。"""

    merit = _merit(applied=(True, False, False, True), external=(False, True, True, False))
    terms = constituent_value_terms(
        PRICE, merit, NO_EXCEPTION, NO_EMBED, w=0.0, kappa=1.0,
        beta=1.0, decay=LADDER, elapsed=4,
    )
    a = PRICE.saving / PRICE.ell_frozen
    assert terms.participation_term == participation(merit) * a
    assert terms.beta_term != 0.0


# --------------------------------------------------------- §4-2 D14 の動的試験
def test_c4_2_beta_changes_the_value_at_the_unit_level() -> None:
    """同じ功績でも β=0 と β=1 で V が変わる。★ 変わらなければ β は未配線。"""

    merit = _merit(applied=(True, False, False, True, False, False),
                   external=(False, True, True, False, True, True))
    values = [
        constituent_value(PRICE, merit, NO_EXCEPTION, NO_EMBED, w=0.0, kappa=1.0,
                          beta=beta, decay=LADDER, elapsed=6)
        for beta in (0.0, 0.5, 1.0)
    ]
    assert values[0] != values[1] != values[2]
    assert values[0] != values[2]


def test_c4_2_beta_changes_the_longitudinal_trajectory() -> None:
    """縦断ループでも β=0 と β=1 で V／削除の軌道が変わる（D14 の検出テスト）。"""

    trials = 150

    def trace(beta: float) -> list[tuple]:
        class Capture:
            def __init__(self) -> None:
                self.rows: list[tuple] = []

            def append(self, record):
                for event in record["deletion_event"]:
                    if event["kind"] == "deletion":
                        self.rows.append(
                            (event["R"], event["slot_index"], event["registered_at"],
                             event["trial"], event["V"])
                        )

        ledger = Capture()
        run_longitudinal(
            generate_world(1, trials, ("agent",)),
            {"agent": AgentState()},
            {"agent": AgentConfig(0.0, CorrectionMode.NONE, theta_prime=0.1432, beta=beta)},
            ledger,
        )
        return ledger.rows

    baseline, shifted = trace(0.0), trace(1.0)
    assert baseline, "削除が一度も起きない設定では D14 の検出にならない"
    assert baseline != shifted


# --------------------------------------------------------------- §4-3 P_ext > 0
def test_c4_3_external_use_lifts_p_ext_above_zero() -> None:
    """external_use を人工的に発火させると P_ext > 0 になる。"""

    quiet = _merit(applied=(True, False, False, False))
    assert quiet.ext_basis == ()
    assert external_participation(quiet, LADDER, 4) == 0.0

    loud = _merit(applied=(True, False, False, False), external=(False, True, True, True))
    assert len(loud.ext_basis) == 16
    assert external_participation(loud, LADDER, 4) > 0.0


def test_c4_3_p_ext_denominator_is_all_trials_minus_r_applied() -> None:
    """M-020: P_ext のエージェント側分母は「全試行 − R 適用」。"""

    merit = _merit(applied=(True, False, False, True), external=(False, True, True, False))
    expected = sum(merit.ext_basis) / (
        sum(total_opportunity(LADDER, 4)) - sum(merit.opportunity_basis)
    )
    assert external_participation(merit, LADDER, 4) == expected


# ------------------------------------------------------------- §4-4 二重計上なし
def test_c4_4_applied_trial_never_increments_external_use() -> None:
    """R_used が立っている試行では ext_use が増えない（M-018 の混入禁止）。"""

    accumulator = initial_merit(0, 0, 0, HORIZON)
    for _ in range(6):
        accumulator = update_merit(
            accumulator, LADDER, matched=True, filled_scored=False, alpha=0.0,
            applied=True, external_use=False,
        )
    assert accumulator.ext_use_count == 0
    assert accumulator.ext_basis == ()
    assert external_participation(accumulator, LADDER, 6) == 0.0


def test_c4_4_loop_never_counts_the_adopted_definition_as_external() -> None:
    """縦断ループでも、採択された def 自身の構成素は R 外使用に数えない。"""

    class Capture:
        """直前の試行と突き合わせて、採択された def の ext_use が動かないことを見る。"""

        def __init__(self) -> None:
            self.previous: dict[tuple[str, int, int], int] = {}
            self.checked = 0

        def append(self, record):
            used = record["R_used"]
            current: dict[tuple[str, int, int], int] = {}
            for row in record["constituent_states"]:
                key = (row["R"], row["slot_index"], row["registered_at"])
                current[key] = row["ext_use_count"]
                if row["R"] == used and key in self.previous:
                    assert row["ext_use_count"] == self.previous[key], (
                        f"採択された def の構成素で ext_use が増えた: {key}"
                    )
                    self.checked += 1
            self.previous = current

    ledger = Capture()
    run_longitudinal(
        generate_world(3, 120, ("agent",)),
        {"agent": AgentState()},
        {"agent": AgentConfig(0.0, CorrectionMode.NONE, theta_prime=0.1432, beta=1.0)},
        ledger,
    )
    assert ledger.checked > 0, "R_used が一度も立たない設定では検収にならない"


# ------------------------------------------- §4-5 同じ減衰基底・同じ更新順序
def test_c4_5_total_opportunity_matches_the_naive_recurrence() -> None:
    """閉形式の全試行和が、applied を常に真にした漸化式と一致する。"""

    for elapsed in (0, 1, 2, 7, 40, 200):
        naive = tuple(D_COLD_MAX_PRIOR for _ in LADDER)
        for _ in range(elapsed):
            naive = tuple(old * factor + 1.0 for old, factor in zip(naive, LADDER))
        closed = total_opportunity(LADDER, elapsed)
        for got, want in zip(closed, naive):
            assert got == pytest.approx(want, rel=1e-12, abs=1e-12)


@pytest.mark.parametrize("base_age", (0, 1, 5, 20, 100))
@pytest.mark.parametrize("elapsed", (0, 1, 3, 25, 150))
def test_c4_5_p_r_stays_within_zero_and_one(base_age: int, elapsed: int) -> None:
    """p_R ∈ (0,1]。★ D-cold の種を分母にも置いているので 1 を超えない。

    ★ 毎試行 R 適用・base_age=0 は上界で、閉形式と漸化式が数学的に等しくなる。
      丸めで 1 を 1ULP 超えることがあるが、そのとき R 外の試行は無いので
      P_ext が 0 に潰れ、β の項は符号ごと消える（下の assert がそれを縛る）。
    """

    merit = _merit(applied=(True,) * elapsed, base_age=base_age)
    rate = adoption_rate(merit, LADDER, elapsed)
    assert rate > 0.0
    assert rate == pytest.approx(1.0, rel=1e-12) or rate < 1.0
    if rate > 1.0:
        assert external_participation(merit, LADDER, elapsed) == 0.0


@pytest.mark.parametrize("elapsed", (0, 1, 3, 25, 150))
def test_c4_5_p_ext_denominator_never_goes_negative(elapsed: int) -> None:
    """P_ext の分母（全試行 − R 適用）が負にならない。"""

    # 上界: 毎試行 R 適用。★ 分母は 0 に潰れ、R 外の試行が無いので P_ext も 0。
    ceiling = _merit(applied=(True,) * elapsed)
    assert sum(total_opportunity(LADDER, elapsed)) == pytest.approx(
        sum(ceiling.opportunity_basis), rel=1e-12
    )
    assert external_participation(ceiling, LADDER, elapsed) == 0.0
    # R 外の試行が一つでもあれば、分母ははっきり正になる。
    mixed = _merit(applied=(True,) * elapsed + (False,))
    assert sum(total_opportunity(LADDER, elapsed + 1)) > sum(mixed.opportunity_basis)


def test_c4_5_p_r_p_ext_and_p_share_one_ladder() -> None:
    """P・p_R・P_ext が同じ 16 本の梯子と同じ更新順序（減衰してから加算）を使う。"""

    merit = _merit(applied=(True, False, True, False), external=(False, True, False, True))
    assert len(merit.basis) == len(merit.opportunity_basis) == len(merit.ext_basis) == len(LADDER)
    # 一段だけ手で回して、三つの基底がどれも old*φ + inc で進むことを見る。
    stepped = update_merit(
        merit, LADDER, matched=True, filled_scored=False, alpha=0.0,
        applied=True, external_use=False,
    )
    for index, factor in enumerate(LADDER):
        assert stepped.basis[index] == merit.basis[index] * factor + 1.0
        assert stepped.opportunity_basis[index] == merit.opportunity_basis[index] * factor + 1.0
        assert stepped.ext_basis[index] == merit.ext_basis[index] * factor


# ------------------------------------------------------- §2-4 p_R = 0 を黙らせない
def test_c2_4_zero_opportunity_basis_stops_instead_of_using_an_epsilon() -> None:
    """機会基底が正でなければ止める。★ 無言の epsilon で通さない。"""

    dead = MeritAccumulator(0, 0, (0.0,) * 16, (0.0,) * 16, 0.0, 0)
    with pytest.raises(ValueError, match="機会基底"):
        adoption_rate(dead, LADDER, 10)
    with pytest.raises(ValueError, match="機会基底"):
        constituent_value(PRICE, dead, NO_EXCEPTION, NO_EMBED, w=0.0, kappa=1.0,
                          beta=1.0, decay=LADDER, elapsed=10)


def test_c2_4_live_definitions_keep_a_positive_opportunity_basis() -> None:
    """D-cold の種があるかぎり、生存 def の機会基底は正のままである。"""

    merit = _merit(applied=(False,) * 199, base_age=100)
    assert sum(merit.opportunity_basis) > 0.0
    assert adoption_rate(merit, LADDER, 199) > 0.0


def test_c2_4_beta_run_without_horizon_stops() -> None:
    """β≠0 で走行長を渡さなければ止まる（黙って既定値に落とさない）。"""

    relation = Relation("r0", "p", ("a", "b"))
    constituent = Constituent(0, 0, relation, PRICE)
    state = AgentState(
        definitions={"R": NamedDefinition("R", (constituent,), 1, 0)},
        merit={("R", 0, 0): initial_merit(0, 0, 0, HORIZON)},
        embed={("R", 0, 0): NO_EMBED},
    )
    with pytest.raises(ValueError, match="horizon"):
        apply_theta(state, AgentConfig(0.0, CorrectionMode.NONE, beta=1.0), trial=5)
    # β=0 なら走行長なしでも従来どおり通る。
    apply_theta(state, AgentConfig(0.0, CorrectionMode.NONE, beta=0.0), trial=5)


# --------------------------------------------- §2-5 削除イベントに V の成分を残す
def test_c2_5_deletion_event_carries_the_four_value_terms() -> None:
    """D23 の V 成分に β の項が四つ目として乗る（β≠0 のときだけ欄が増える）。"""

    class Capture:
        def __init__(self) -> None:
            self.events: list[dict] = []

        def append(self, record):
            self.events.extend(
                e for e in record["deletion_event"] if e["kind"] == "deletion"
            )

    def deletions(beta: float) -> list[dict]:
        ledger = Capture()
        run_longitudinal(
            generate_world(1, 120, ("agent",)),
            {"agent": AgentState()},
            {"agent": AgentConfig(0.0, CorrectionMode.NONE, theta_prime=0.1432, beta=beta)},
            ledger,
        )
        return ledger.events

    with_beta = deletions(1.0)
    assert with_beta
    for event in with_beta:
        assert event["V"] == pytest.approx(
            event["V_participation"] + event["V_beta"] + event["V_embed"]
        )
    # β=0 では欄を足さない。既存 4,322 走行と台帳バイト列を一致させるため。
    for event in deletions(0.0):
        assert set(event) == {"kind", "R", "slot_index", "registered_at", "trial", "V"}

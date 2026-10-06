"""v3.9（2026-09-29 深夜、委任書「記憶予算・三段階の忘却（v3.9）」）：旗 --v39。
仕様：control/sfn_budget_implementation_spec_2026-09-29.md（ChatGPT、基準 v3.8-2026-09-28 / 996d469）。★ abm/ は変えない。旗を切れば何もしない。
v3.8 の旗一式（--own-evidence・--no-charge2・--charge1 d32・--fix2-full・--fix-order2・--proj-first・--fill-norestate・--extend-rule none・同定の旗）
の上に載せる。θ′ による行の削除・誕生の刈り込み（--greedy）・m_live＝0 の定義の削除は使わない（下の 5・6）。

1 席の三段階（今の表し方の上に載せる）
  F＝生きている行（固定名＝行の述語）。H＝墓石で、席の履歴（slot_history[(R, 席)]）がある。U＝墓石で、席の履歴が無い。
  F→H：行を墓石にし、行の述語を消す（ERASED に置き換える。★ 消した名を照合・親・履歴・識別子から読めなくする。仕様の検査 ⑧）。履歴は残す。
  H→U：席の履歴を消す（slot_history の鍵を消す）。全席が U になった定義は退役（定義と、その鍵の功績・例外・履歴・席の記録を消す）。
  U→H：新しい観察（m1 の観察、v3.8 の D-10）で履歴ができたら H に戻る。成績は新しい世代として 0 から。H→F の自動復帰はしない（--extend-rule none）。
2 照合（同定・選択）での席の扱い（委任書 1 の決めごと）
  F は今の生きている行と同じ（固定名で一致）。H は今の墓石と同じ規則（直し②：場面の述語が席の履歴に回数 1 以上あれば当てはまる）で、
  定義のグラフに席ごとの仮の名（HPRED＋席番号）の関係として置き、照合の候補づくり（sme._alignment_candidates）で「履歴の名」との一致を許す。
  U はグラフの関係に置かない（名前では当てはまらない）。U を子に持つ親の引数は直し②の空の履歴と同じ（見えていれば当てはまらない・伏せられていれば見えていない枠）。
  門：支持数（写った F と H の席の数）≧ ceil(0.67 ×（F 席数＋H 席数））。F＋H が 0 の定義は無い（退役する）。並べ方は今の規則（支持比→席数→新しさ→名前）。
3 話す（今の選択規則のまま：投影優先・言い直し禁止）
  投影は F の行だけ（固定名）。穴埋めは F＝固定名、H＝「席の相対回数^λ × 全体頻度」の最大（λ＝local_lambda、階数をそろえる。同点は棄権）、
  U＝引数の型・階数に適合する全体最頻（署名適合。--v39-u abstain では棄権）。
4 局所の三答えと採点
  予測の時点（開示前の同じ対応・同じ記憶）で、R_used の、引数の写しが決まった席ごとに、F 席は F/H/U、H 席は H/U の答えを作って控える。
  本人が開示を受けた試行だけ、名前と引数が開示と一致すれば 1、ほかは 0 を、S_F・S_H・S_U に、評価の量 E に 1 を足す（16 本の減衰。減衰してから加算）。
  開示なし・写しが決まらない席は全列を更新しない。誕生の初期成績（二場面：旧い場面 φ^年齢、今の場面 1）は別に持ち、点数では足す。
5 保持点数と処理順（仕様 5 節）
  V_FH ＝（S_F − S_H）/［(E＋2a) ΔC_FH］、V_HU ＝（S_H − S_U）/［(E＋2a) ΔC_HU］。S・E は 16 本の平均。Q（例外費用）は入れない。
  各試行の削除の段（apply_theta の代わり）：逐語の枚の削除（今の別基準）→ V＜0 の変換（容量無限でも）→ 総費用が予算以下になるまで低い点から一段ずつ。
  同点は独立した乱数（世界・開示の乱数を使わない）で一件ずつ選ぶ。各変換のあと、その定義の次の段と費用を計り直す。解放候補が尽きても予算を超えるなら「容量不適合」で止める。
6 費用（仕様 6 節。ビット）
  I(n)＝2 floor(log2(n+1))＋1、L(p)＝ceil(−log2(N_p/N))（語彙一つなら 0）。
  総費用＝全体回数表［I(語彙数)＋語彙数×ceil(log2 固定辞書の語数)＋Σ I(N_p)］＋ I(定義数) ＋ Σ 定義［構造＋Σ 席（状態 2 ビット＋中身）］。
  中身：U 0、H Hcost＝I(k)＋Σ[L(p)＋I(n_p)]（候補は固定辞書順、回数 0 の候補も数える）、F Hcost＋固定名の指定（履歴の中の位置 j に I(j)、無ければ I(0)＋L）。
  構造：ceil(log2 T)＋I(m)＋I(e)＋Σ 席［I(引数数)＋Σ 引数（型 1 ビット＋ceil(log2(e または m))）］。
7 誕生：土台と今の場面の共通構造（m1 と同じ対）から、子が組に無い高階の行を外して（構造上必要な子を残して）登録する。2 行未満なら登録しない。
  θ′ を使う刈り込みはしない。同化の規則は今のまま（--extend-rule none）。
使い方：tools/v3_run.py --v39 [--v39-budget inf|<ビット>] [--v39-init two|zero] [--v39-a 0.5|1] [--v39-u global|abstain]
"""
from __future__ import annotations

import json
import math
from collections.abc import Mapping
from dataclasses import dataclass, field, fields, replace
from functools import lru_cache
from hashlib import sha256
from random import Random

ERASED = "⟨消去⟩"
HPRED = "⟨H⟩"
STATS: dict = {}
CFG: dict = {}
CTX: dict = {}
REG: dict = {}
_POW: dict = {}


class Unfit(RuntimeError):
    """容量不適合（仕様 8 節）。走行を止めて記録する。"""


# ---------------------------------------------------------------- 符号長
@lru_cache(maxsize=None)
def I(n: int) -> int:
    if n < 0:
        raise ValueError(n)
    return 2 * int(math.floor(math.log2(n + 1))) + 1


def clog2(n: int) -> int:
    return int(math.ceil(math.log2(n))) if n > 1 else 0


def code_lengths(p_hat) -> dict:
    N = p_hat.total
    vocab = [p for p, n in p_hat.counts.items() if n > 0]
    if len(vocab) <= 1:
        return {p: 0 for p in vocab}
    return {p: int(math.ceil(-math.log2(p_hat.counts[p] / N))) for p in vocab}


def global_table_bits(p_hat) -> int:
    vocab = [p for p, n in p_hat.counts.items() if n > 0]
    return I(len(vocab)) + len(vocab) * clog2(CFG["D"]) + sum(I(p_hat.counts[p]) for p in vocab)


def hist_counts(h) -> dict:
    if h is None:
        return {}
    return dict(h) if isinstance(h, Mapping) else {p: 1 for p in h}


def dict_order(p: str) -> int:
    idx = CFG["dict_index"].get(p)
    if idx is None:
        STATS["not_in_dictionary"] = STATS.get("not_in_dictionary", 0) + 1
        return len(CFG["dict_index"]) + sum(map(ord, p))
    return idx


def hcost(h, L) -> int:
    c = hist_counts(h)
    return I(len(c)) + sum(L_of(p, L) + I(int(n)) for p, n in c.items())


def L_of(p, L) -> int:
    v = L.get(p)
    if v is None:
        STATS["L_unseen_name"] = STATS.get("L_unseen_name", 0) + 1
        return max(L.values(), default=0) + 1
    return v


def fixed_spec_bits(fixed: str, h, L) -> int:
    c = hist_counts(h)
    if fixed in c:
        j = 1 + sorted(c, key=dict_order).index(fixed)
        return I(j)
    return I(0) + L_of(fixed, L)


def structure_bits(d) -> int:
    rel_ids = {row.relation.relation_id for row in d.constituents}
    ents = {a for row in d.constituents for a in row.relation.arguments if a not in rel_ids}
    m = len({row.slot_index for row in d.constituents})
    e = len(ents)
    bits = clog2(CFG["T"]) + I(m) + I(e)
    for row in d.constituents:
        bits += I(len(row.relation.arguments))
        for a in row.relation.arguments:
            bits += 1 + (clog2(m) if a in rel_ids else clog2(e))
    return bits


# ---------------------------------------------------------------- 席
def seat_state(d, row, slot_history) -> str:
    """F＝生きている行。H＝墓石で履歴欄がある（空の表も H。仕様 6 節「空表も含め履歴欄全体を外す」）。U＝墓石で履歴欄が無い。"""
    if row.alive:
        return "F"
    return "H" if (d.name, row.slot_index) in slot_history else "U"


def n_FH(d, slot_history) -> int:
    return sum(1 for row in d.constituents if seat_state(d, row, slot_history) != "U")


def seat_content_bits(d, row, st, slot_history, L) -> int:
    if st == "U":
        return 0
    h = slot_history.get((d.name, row.slot_index))
    b = hcost(h, L)
    if st == "F":
        b += fixed_spec_bits(row.relation.predicate, h, L)
    return b


def definition_bits(d, slot_history, L) -> int:
    key = (d.name, d.registered_at, tuple((r.slot_index, r.registered_at) for r in d.constituents))
    sb = CTX["struct_cache"].get(key)
    if sb is None:
        sb = CTX["struct_cache"][key] = structure_bits(d)
    return sb + sum(2 + seat_content_bits(d, row, seat_state(d, row, slot_history), slot_history, L)
                    for row in d.constituents)


def total_bits(state, L) -> int:
    return (global_table_bits(state.p_hat) + I(len(state.definitions))
            + sum(definition_bits(d, state.slot_history, L) for d in state.definitions.values()))


# ---------------------------------------------------------------- 成績の記録（席ごと・世代ごと。16 本の減衰。遅延して減衰させる）
@dataclass(frozen=True, slots=True)
class SeatRec:
    gen: int
    state: str
    born: int                 # この世代が始まった試行
    t0: int                   # 値が「試行 t0 の終わり」の値であること
    init: tuple               # 誕生の初期成績 (SF, SH, SU, E)（各 16 本）
    post: tuple               # 誕生後の成績 (SF, SH, SU, E)
    n_scored: int = 0


ZERO16 = (0.0,) * 16
ZERO4 = (ZERO16, ZERO16, ZERO16, ZERO16)


def _pow(dt: int) -> tuple:
    v = _POW.get(dt)
    if v is None:
        v = _POW[dt] = tuple(f ** dt for f in CFG["decay"])
    return v


def rec_values(rec: SeatRec, t: int):
    """試行 t の時点の (init, post)（各 4 × 16 本）。"""
    w = _pow(max(t - rec.t0, 0))
    return (tuple(tuple(x * k for x, k in zip(col, w)) for col in rec.init),
            tuple(tuple(x * k for x, k in zip(col, w)) for col in rec.post))


def mean16(col) -> float:
    """16 本の記録を一つの量にする。既定は均等の平均（v3.9 のまま）。--v39-decay actr（v3.10）では、
    時定数 τₖ^(−0.5) に比例し合計 1 の重みで平均する（ACT-R の形：一回の採点の Δ 試行後の重みが、およそ Δ^(−0.5) に比例する）。"""
    wt = CFG.get("mean_weights")
    if wt is None:
        return sum(col) / 16.0
    return sum(x * k for x, k in zip(col, wt))


def rec_means(rec: SeatRec, t: int) -> tuple:
    """(S_F, S_H, S_U, E)：初期分と誕生後の分を足した 16 本の平均（重みは mean16）。"""
    w = _pow(max(t - rec.t0, 0))
    out = []
    wt = CFG.get("mean_weights")
    for a, b in zip(rec.init, rec.post):
        if wt is None:
            out.append(sum((x + y) * k for x, y, k in zip(a, b, w)) / 16.0)   # ★ v3.9 と一字一句同じ計算
        else:
            out.append(sum((x + y) * k * q for x, y, k, q in zip(a, b, w, wt)))
    return tuple(out)


def actr_weights(horizon: int) -> tuple:
    """--v39-decay actr の平均の重み：abm/accounting.py の decay_ladder と同じ時定数 τₖ（0.3〜3T の等比 16 本）に対し τₖ^(−0.5) ∝、合計 1。"""
    taus = [0.3 * ((max(horizon * 3, 0.3) / 0.3) ** (k / 15)) for k in range(16)]
    raw = [tau ** -0.5 for tau in taus]
    z = sum(raw)
    return tuple(r / z for r in raw)


def rec_add(rec: SeatRec, t: int, inc: tuple) -> SeatRec:
    init, post = rec_values(rec, t)
    post = tuple(tuple(x + d for x in col) for col, d in zip(post, inc))
    return replace(rec, t0=t, init=init, post=post, n_scored=rec.n_scored + 1)


# ---------------------------------------------------------------- 状態の型（v39 の席の記録を足す）
_STATE_CLS: list = []


def _state_class():
    from abm.domains import AgentState
    if not _STATE_CLS:
        @dataclass(frozen=True, slots=True)
        class AgentStateV39(AgentState):
            v39_seats: Mapping = field(default_factory=dict)
        _STATE_CLS.append(AgentStateV39)
    return _STATE_CLS[0]


def ensure(state):
    cls = _state_class()
    if isinstance(state, cls):
        return state
    kw = {f.name: getattr(state, f.name) for f in fields(state)}
    kw.setdefault("v39_seats", {})
    return cls(**kw)


# ---------------------------------------------------------------- グラフと照合の候補
def v39_graph(d, slot_history):
    from abm.domains import Entity, Relation, RelationGraph
    rel_ids = {row.relation.relation_id for row in d.constituents}
    ents = sorted({a for row in d.constituents for a in row.relation.arguments if a not in rel_ids})
    rels = []
    hallow = {}
    ushield = set()
    for row in d.constituents:
        st = seat_state(d, row, slot_history)
        if st == "F":
            rels.append(row.relation)
        elif st == "H":
            rels.append(Relation(row.relation.relation_id, f"{HPRED}{row.slot_index}", row.relation.arguments))
            hallow[row.relation.relation_id] = frozenset(
                p for p, n in hist_counts(slot_history.get((d.name, row.slot_index))).items() if n >= 1)
        else:
            ushield.add(row.relation.relation_id)
    g = RelationGraph(graph_id=f"definition:{d.name}", entities=tuple(Entity(e) for e in ents), relations=tuple(rels))
    REG[id(g)] = (g, hallow, frozenset(ushield))
    return g


def unregister(g) -> None:
    REG.pop(id(g), None)


# ★ 照合の候補の作り方の差し込み口（既定は空＝今と同じ）。--strict-pc（tools/strictpc.py）が、定義の行でない引数のうち
#   控えた種類が関係のものを「関係」とみなす関数を入れる：LEFT_REL[0](照合のグラフ, 基の引数, 相手の引数が見えている関係か) → bool
LEFT_REL: list = []


def _install_candidates():
    import abm.sme as sme
    from abm.sme import AlignmentCandidate
    prev = sme._alignment_candidates

    def _alignment_candidates(base_graph, partial_graph):
        entry = REG.get(id(base_graph))
        if entry is None or entry[0] is not base_graph:
            return prev(base_graph, partial_graph)
        _, hallow, ushield = entry
        base_relation_ids = sme._relation_ids(base_graph)
        partial_relation_ids = sme._relation_ids(partial_graph)
        partial_entity_ids = frozenset(e.entity_id for e in partial_graph.entities)
        candidates = []
        for left in sorted(base_graph.relations, key=sme._relation_key):
            allowed = hallow.get(left.relation_id)
            for right in sorted(partial_graph.relations, key=sme._relation_key):
                if len(left.arguments) != len(right.arguments):
                    continue
                if right.predicate != left.predicate and (allowed is None or right.predicate not in allowed):
                    continue
                entity_pairs = []
                relation_pairs = []
                compatible = True
                for left_arg, right_arg in zip(left.arguments, right.arguments, strict=True):
                    if left_arg in ushield:
                        # ★ U の子：直し②の空の履歴と同じ（見えている関係・物には当てはまらない。伏せられていれば見えていない枠）
                        if right_arg in partial_relation_ids or right_arg in partial_entity_ids:
                            compatible = False
                            break
                        relation_pairs.append((left_arg, right_arg))
                        continue
                    left_is_relation = left_arg in base_relation_ids or (LEFT_REL[0](base_graph, left_arg, right_arg in partial_relation_ids)
                                                                         if LEFT_REL else False)
                    right_is_relation = right_arg in partial_relation_ids
                    right_is_unobserved = (not right_is_relation) and (right_arg not in partial_entity_ids)
                    if left_is_relation and right_is_unobserved:
                        relation_pairs.append((left_arg, right_arg))
                        continue
                    if left_is_relation != right_is_relation:
                        compatible = False
                        break
                    if left_is_relation:
                        relation_pairs.append((left_arg, right_arg))
                    else:
                        entity_pairs.append((left_arg, right_arg))
                if compatible:
                    candidates.append(AlignmentCandidate(
                        base_relation_id=left.relation_id, partial_relation_id=right.relation_id,
                        predicate=left.predicate, arity=len(left.arguments),
                        entity_pairs=tuple(sorted(entity_pairs)), relation_pairs=tuple(sorted(relation_pairs))))
        return tuple(sorted(candidates, key=sme._candidate_order_key))

    sme._alignment_candidates = _alignment_candidates


def map_v39(d, slot_history, scene):
    import abm.sme as sme
    g = v39_graph(d, slot_history)
    try:
        al = sme.map_graphs(g, scene).alignment
    finally:
        unregister(g)
    return g, al


# ---------------------------------------------------------------- 三つの答え
def _order_pool(pool, d, row, hop):
    from abm.filling import _is_higher, _same_order
    rel_ids = {c.relation.relation_id for c in d.constituents}
    want = _is_higher(row.relation, rel_ids)
    return frozenset(p for p in pool if _same_order(p, want, hop))


def h_answer(d, row, slot_history, p_hat, lam, hop):
    from abm.filling import most_frequent
    h = slot_history.get((d.name, row.slot_index))
    if not h:
        return None, "履歴なし"
    counts = h if isinstance(h, Mapping) else None
    pool = _order_pool(frozenset(h), d, row, hop)
    if not pool:
        return None, "階数で候補なし"
    p, tied = most_frequent(pool, p_hat, lam, counts)
    return (None, "同点") if tied or p is None else (p, None)


def u_answer(d, row, scene, p_hat, hop):
    from abm.domains import RelationGraph
    from abm.filling import _predicate_has_signature, most_frequent, slot_signature
    if CFG["u_abstain"]:
        return None, "U は棄権"
    dg = RelationGraph("definition", relations=tuple(c.relation for c in d.constituents))
    sig = slot_signature(row.relation, dg)
    pool = frozenset(p for p in p_hat.alive_vocab if _predicate_has_signature(p, sig, scene, dg))
    pool = _order_pool(pool, d, row, hop)
    if not pool:
        return None, "適合する名なし"
    p, tied = most_frequent(pool, p_hat)
    return (None, "同点") if tied or p is None else (p, None)


def three_answers(d, alignment, state, config, scene):
    from abm.filling import _mapped_arguments
    out = []
    seats = getattr(state, "v39_seats", {})
    for row in sorted(d.constituents, key=lambda r: r.slot_index):
        st = seat_state(d, row, state.slot_history)
        pos = _mapped_arguments(row.relation, alignment.entity_mapping, alignment.relation_mapping)
        rec = seats.get((d.name, row.slot_index))
        item = {"slot": row.slot_index, "st": st, "pos": list(pos) if pos is not None else None,
                "gen": rec.gen if rec is not None else None}
        if st != "U" and pos is not None:
            ans = {}
            if st == "F":
                ans["F"] = row.relation.predicate
            ans["H"] = h_answer(d, row, state.slot_history, state.p_hat, config.local_lambda, config.higher_order_predicates)[0]
            ans["U"] = u_answer(d, row, scene, state.p_hat, config.higher_order_predicates)[0]
            item["ans"] = ans
        elif st == "U":
            item["U答え"] = (u_answer(d, row, scene, state.p_hat, config.higher_order_predicates)[0]
                            if pos is not None else None)
        out.append(item)
    return out


def score_answers(seats, ans, received, t):
    """控えた三答え（開示前）を、受け取った開示で採点する。名前と引数が一致すれば 1、ほかは 0。E に 1。
    写しが決まらない席（ans が無い）・U の席は全列を更新しない。席の世代・状態が変わっていれば採点しない。"""
    seats = dict(seats)
    scored = []
    for it in ans["items"]:
        if "ans" not in it:
            continue
        key = (ans["R"], it["slot"])
        rec = seats.get(key)
        if rec is None or rec.gen != it["gen"] or rec.state != it["st"]:
            STATS["score_skipped_changed"] = STATS.get("score_skipped_changed", 0) + 1
            continue
        pos_ok = tuple(it["pos"]) == tuple(received.arguments)
        s = {x: float(pos_ok and it["ans"].get(x) == received.predicate) for x in ("F", "H", "U")}
        inc = (s["F"] if it["st"] == "F" else 0.0, s["H"], s["U"], 1.0)
        seats[key] = rec_add(rec, t, inc)
        scored.append([it["slot"], it["st"], int(s["F"]), int(s["H"]), int(s["U"])])
    return seats, scored


# ---------------------------------------------------------------- 穴埋め（F＝固定名・H＝履歴・U＝全体最頻。言い直し禁止）
def fill_v39(definition, target, entity_mapping, relation_mapping, slot_history, p_hat, fill_selection="most_frequent",
             rng=None, *, higher_order_predicates, local_lambda=0.0):
    from abm.domains import Relation, RelationGraph
    from abm.filling import (FillingResult, _distribution, _is_higher, _mapped_arguments_recursive,
                             _predicate_has_signature, _same_order, most_frequent, sample_predicate, slot_signature)
    if higher_order_predicates is None:
        raise ValueError("higher_order_predicates が渡されていない")
    all_predicates = tuple(p_hat.alive_vocab)
    relations, indices, sources, alive_flags, distributions = [], [], [], [], []
    ambiguous = False
    fallback_used = False
    empty_pool_slots = 0
    history_size = 0
    tie_candidates = 0
    states = []
    definition_graph = RelationGraph("definition", relations=tuple(c.relation for c in definition.constituents))
    definition_relation_ids = {c.relation.relation_id for c in definition.constituents}
    scene_relation_ids = {relation.relation_id for relation in target.relations}
    definition_by_id = {c.relation.relation_id: c for c in definition.constituents}
    filled_by_id = {}
    visiting = set()

    def fill(constituent):
        nonlocal ambiguous, fallback_used, history_size, tie_candidates, empty_pool_slots
        relation_id = constituent.relation.relation_id
        if relation_id in filled_by_id:
            return filled_by_id[relation_id]
        if relation_id in visiting:
            raise ValueError("def(R) の充填依存に循環がある")
        mapped_to = relation_mapping.get(relation_id)
        if mapped_to is not None and mapped_to in scene_relation_ids:
            return None
        visiting.add(relation_id)
        mapped_arguments = _mapped_arguments_recursive(constituent.relation, entity_mapping, relation_mapping,
                                                       definition_by_id, scene_relation_ids, fill)
        if mapped_arguments is None:
            visiting.remove(relation_id)
            return None
        st = seat_state(definition, constituent, slot_history)
        used_fallback = False
        if st == "F":
            predicate = constituent.relation.predicate
            visible = next((item for item in target.relations
                            if item.predicate == predicate and item.arguments == mapped_arguments), None)
            if visible is not None:
                visiting.remove(relation_id)
                return visible
            distributions.append({"slot_index": constituent.slot_index, "candidates": [[predicate, 1.0]], "席": "F"})
        else:
            position_distribution = None
            raw_history = slot_history.get((definition.name, constituent.slot_index))
            if st == "H":
                pool = frozenset(raw_history)
                local_counts = raw_history if isinstance(raw_history, Mapping) else None
            else:
                if CFG["u_abstain"]:
                    STATS["u_abstain_fill"] = STATS.get("u_abstain_fill", 0) + 1
                    visiting.remove(relation_id)
                    return None
                used_fallback = True
                local_counts = None
                signature = slot_signature(constituent.relation, definition_graph)
                pool = frozenset(p for p in all_predicates
                                 if _predicate_has_signature(p, signature, target, definition_graph))
            pool_before_order = pool
            want_higher = _is_higher(constituent.relation, definition_relation_ids)
            pool = frozenset(p for p in pool if _same_order(p, want_higher, higher_order_predicates))
            if pool_before_order and not pool:
                empty_pool_slots += 1
            distribution = _distribution(pool, p_hat, local_lambda, local_counts)
            if st == "U" and CFG.get("u_position"):
                import uposition
                b, _, why = uposition.base_distribution(definition, constituent, target, p_hat, higher_order_predicates)
                if why is None:
                    position_distribution = b
                    distribution = tuple(sorted(b.items()))
            maximum = max((w for _, w in distribution), default=0.0)
            tied_count = sum(w == maximum for _, w in distribution) if maximum > 0 else 0
            history_size += len(pool)
            tie_candidates += tied_count if tied_count > 1 else 0
            distributions.append({"slot_index": constituent.slot_index,
                                  "candidates": [[p, w] for p, w in distribution], "席": st})
            if fill_selection == "sample":
                predicate = sample_predicate(distribution, rng)
                tied = False
            else:
                if position_distribution is not None:
                    predicate, tied = uposition.maximum(position_distribution)
                else:
                    predicate, tied = most_frequent(pool, p_hat, local_lambda, local_counts)
                ambiguous = ambiguous or tied
            fallback_used = fallback_used or used_fallback
            if predicate is None:
                visiting.remove(relation_id)
                return None
            # ★ 言い直し禁止（--fill-norestate と同じ）：選んだ名が写した位置で見えていれば埋めない
            if any(item.predicate == predicate and item.arguments == mapped_arguments for item in target.relations):
                visiting.remove(relation_id)
                STATS["skipped_restatement"] = STATS.get("skipped_restatement", 0) + 1
                return None
        filled = Relation(relation_id=f"filling__{definition.name}__{constituent.slot_index}__{constituent.registered_at}",
                          predicate=predicate, arguments=mapped_arguments)
        filled_by_id[relation_id] = filled
        relations.append(filled)
        indices.append(constituent.slot_index)
        sources.append("fixed" if st == "F" else "slot_history" if st == "H" else "signature_fallback")
        alive_flags.append(bool(constituent.alive))
        states.append(st)
        visiting.remove(relation_id)
        return filled

    for constituent in sorted(definition.constituents, key=lambda row: row.slot_index):
        fill(constituent)
    res = FillingResult(tuple(relations), tuple(indices), ambiguous, fallback_used, tuple(sources),
                        history_size, tie_candidates, tuple(distributions), tuple(alive_flags), empty_pool_slots)
    CTX["fill_states"] = tuple(states)
    CTX["fill_ids"] = tuple(r.relation_id for r in relations)
    return res


# ---------------------------------------------------------------- 定義の選び方（支持＝写った F と H の席、分母＝F＋H）
def select_definition(state, scene, config):
    import abm.agent_runtime as ar
    STATS["select_calls"] = STATS.get("select_calls", 0) + 1
    ranked = []
    for d in state.definitions.values():
        n = n_FH(d, state.slot_history)
        if n == 0:
            continue
        graph, alignment = map_v39(d, state.slot_history, scene)
        if alignment is None:
            continue
        support = sum(1 for row in d.constituents
                      if seat_state(d, row, state.slot_history) != "U"
                      and row.relation.relation_id in alignment.relation_mapping)
        ranked.append((support / n, support, d, graph, alignment, n))
    if not ranked:
        return None
    ranked.sort(key=lambda it: (-it[0], -it[5], -it[2].registered_at, it[2].name))
    best = ranked[0]
    tie_event = sum(it[0] == best[0] and it[5] == best[5] and it[2].registered_at == best[2].registered_at
                    for it in ranked) > 1
    passed = [{"R": d.name, "support": s, "m_live": n, "ratio": r, "selected": d.name == best[2].name}
              for r, s, d, _g, _a, n in ranked if s >= ar._need(config.tau_acc, n)]
    ratio, support, d, graph, alignment, n = best
    f_ids = {row.relation.relation_id for row in d.constituents if row.alive}
    alignment = replace(alignment, candidate_projections=tuple(x for x in alignment.candidate_projections if x in f_ids))
    return ratio, support, d, graph, alignment, n, tie_event, passed


# ---------------------------------------------------------------- 予測（abm/agent_runtime.py:predict の写し。★ の所だけ違う）
def predict(agent_input, state, config, rng):
    import abm.agent_runtime as ar
    from abm.domains import Abstain, AgentOutput, EdgePrediction
    from abm.sme import apply_threshold, map_graphs, project
    CTX["answers"] = None
    if not state.prototype.traces:
        output = AgentOutput(prediction=Abstain(reason="no_prototype"), trace={"tau_passed_defs": []})
        CTX["output"] = output
        return output, ar.PendingState(state, output, agent_input, ar._snapshot_rng_state(rng, state.rng_state))
    ranked = [(map_graphs(trace.scene, agent_input.target_graph_partial), trace) for trace in state.prototype.traces]
    if CFG.get("sme2017"):
        import smeshared
        mapping, selected_trace = smeshared.choose_trace(ranked, agent_input.target_graph_partial)
    else:
        mapping, selected_trace = sorted(
            ranked, key=lambda item: (-item[0].alignment.total_score, -item[1].written_at, item[1].scene.graph_id))[0]
    base = selected_trace.scene
    threshold = apply_threshold(mapping, config.threshold)
    trace = {"alignment": mapping.alignment, "support_at_adoption": 0, "R_used": None, "m_live": 0, "filled_slots": (),
             "entity_map_covered": False, "selected_scene": base, "selected_scene_written_at": selected_trace.written_at,
             "tau_passed_defs": []}
    projected_edge = None
    prediction_path = None
    filling = None
    scene = agent_input.target_graph_partial
    if not threshold.accepted:
        prediction = Abstain(reason="below_threshold")
    elif not state.definitions:
        prediction = Abstain(reason="no_definition")
    else:
        selected = select_definition(state, scene, config)          # ★ F と H の席で選ぶ
        if selected is None:
            prediction = Abstain(reason="no_definition")
        else:
            _, support, definition, graph, definition_alignment, n, tie_event, passed = selected
            trace["tau_passed_defs"] = passed
            name = definition.name
            trace["support_at_adoption"] = support
            trace["m_live"] = n                                     # ★ F＋H の席数
            trace["definition_alignment"] = definition_alignment
            trace["tie_event"] = tie_event
            if support >= min(2, n):
                trace["R_identified"] = name
            if support < ar._need(config.tau_acc, n):              # ★ 門：ceil(0.67 ×（F＋H））
                prediction = Abstain(reason="below_tau")
            else:
                trace["R_used"] = name
                prediction = project(definition_alignment, graph, scene, prototype_prior_weight=0.0)   # ★ F の行だけ
                if isinstance(prediction, EdgePrediction):
                    projected_edge = prediction.edge
                filling = fill_v39(definition, scene, definition_alignment.entity_mapping,
                                   definition_alignment.relation_mapping, state.slot_history, state.p_hat,
                                   config.fill_selection, rng, higher_order_predicates=config.higher_order_predicates,
                                   local_lambda=config.local_lambda)
                trace.update(filled_slots=filling.relations, filled_slot_indices=filling.slot_indices,
                             filling_fallback=filling.used_fallback,
                             entity_map_covered=all(a in definition_alignment.entity_mapping
                                                    or a in definition_alignment.relation_mapping
                                                    for row in definition.constituents for a in row.relation.arguments))
                prediction, prediction_path = fill_decision(prediction, filling, prediction_path)
                # ★ 局所の三答え（開示前の同じ対応・同じ記憶）
                CTX["answers"] = {"R": name, "items": three_answers(definition, definition_alignment, state, config, scene),
                                  "fill_states": CTX.get("fill_states", ()), "fill_ids": CTX.get("fill_ids", ())}
    output = AgentOutput(prediction=prediction, trace=trace)
    CTX["output"] = output
    pending = ar.PendingState(
        previous_state=state, output=output, agent_input=agent_input,
        rng_state=ar._snapshot_rng_state(rng, state.rng_state), projected_edge=projected_edge,
        prediction_path=prediction_path, filling_empty_pool_slots=filling.empty_pool_slots if filling is not None else 0,
        filling_slot_history_size=filling.slot_history_size if filling is not None else 0,
        filling_n_tie_candidates=filling.n_tie_candidates if filling is not None else 0,
        filling_candidate_distribution=filling.candidate_distribution if filling is not None else ())
    return output, pending


# ---------------------------------------------------------------- 同定（tools/v32.py の identify の写し。★ 定義のグラフを F と H の席で作る）
def identify(state, scene, threshold, self_score_cache=None, *, identification_graph="all", self_score_cache_mode="legacy"):
    import abm.sme as sme
    import v32
    rho = CFG["rho"]
    target = scene
    if CFG["commons"]:
        target = v32.commons_graph(scene, CTX["output"])
        if target is None:
            STATS["ident_commons_lt2"] = STATS.get("ident_commons_lt2", 0) + 1
            return None
    defs = sorted((d for d in state.definitions.values() if n_FH(d, state.slot_history) > 0),
                  key=lambda d: (-d.assimilation_count, -d.registered_at))
    first = best = best_ratio = None
    row_points = None
    for d in defs:
        g = v39_graph(d, state.slot_history)
        try:
            self_score = sme.map_graphs(g, g).alignment.total_score
            if self_score <= 0:
                continue
            res = sme.map_graphs(g, target)
        finally:
            unregister(g)
        score = res.alignment.total_score
        if rho:
            if row_points is None:
                row_points, _ = v32.self_row_points(target, sme.SMEParams())
            ratio = score / (self_score + rho * v32.target_only_points(row_points, set(res.alignment.relation_mapping.values())))
        else:
            ratio = score / self_score
        if ratio >= threshold and first is None:
            first = d.name
            if not CFG["argmax"]:
                break
        if CFG["argmax"] and (best_ratio is None or ratio > best_ratio):
            best, best_ratio = d.name, ratio
    if CFG["argmax"]:
        return best if (best_ratio is not None and best_ratio >= threshold) else None
    return first


# ---------------------------------------------------------------- 反実仮想の予測（記録だけ。loop._counterfactual_predictions の写し。F/H/U の表し方で）
def fill_decision(prediction, filling, prediction_path):
    """投影（F の行だけ）と穴埋めから、話す答えを決める（予測の最後の段。旗なしでは今までの書き方と同じ）。返り値：(予測, 答えの道)。"""
    from abm.domains import Abstain, EdgePrediction
    ambiguous = filling.ambiguous and not isinstance(prediction, EdgePrediction)   # ★ 投影優先（--proj-first）
    if ambiguous and not amb_blocks(filling):
        ambiguous = False
        STATS["amb_local_spoke"] = STATS.get("amb_local_spoke", 0) + 1
    if ambiguous:
        prediction = Abstain(reason="ambiguous_projection")
    elif isinstance(prediction, Abstain) and filling.relations:
        prediction = EdgePrediction(filling.relations[0])
        alive = filling.alive_by_slot[0] if filling.alive_by_slot else None
        prediction_path = "filling_live" if alive else "filling_tombstone"
    elif isinstance(prediction, Abstain):
        prediction = Abstain(reason="no_projectable_relation")
    elif isinstance(prediction, EdgePrediction):
        prediction_path = "projection"
    return prediction, prediction_path


def amb_blocks(filling) -> bool:
    """穴埋めの「あいまい」の印で、答え全体を止めるか。
    旗なし：止める（今のまま）。
    --amb-local（2026-09-30 夕の指示の 2、CFG["amb_local"]）：候補（名前と必要な引数が決まって埋まった関係）が一つでもあれば止めない。
      決まらない席（同点の席・U の常時棄権の席）は穴埋めで関係を作らず、その子に頼る親も引数が決まらないので作られない（fill_v39 のとおり）。
      候補どうしの選び方（最初に埋まった関係）と、固定の答えの投影の優先は今のまま。研究者の伏せ辺は見ない。"""
    return not (CFG.get("amb_local") and filling.relations)


def counterfactuals(state, target, output, held_out, higher_order_predicates, local_lambda=0.0):
    from abm.domains import Abstain, EdgePrediction
    from abm.sme import project
    results = []
    for item in output.trace.get("tau_passed_defs", []):
        if item["selected"]:
            continue
        d = state.definitions[item["R"]]
        graph, alignment = map_v39(d, state.slot_history, target)
        f_ids = {row.relation.relation_id for row in d.constituents if row.alive}
        alignment = replace(alignment, candidate_projections=tuple(x for x in alignment.candidate_projections if x in f_ids))
        prediction = project(alignment, graph, target, prototype_prior_weight=0.0)
        filling = fill_v39(d, target, alignment.entity_mapping, alignment.relation_mapping, state.slot_history, state.p_hat,
                           higher_order_predicates=higher_order_predicates, local_lambda=local_lambda)
        if filling.ambiguous and amb_blocks(filling):
            prediction = Abstain(reason="ambiguous_projection")
        elif isinstance(prediction, Abstain) and filling.relations:
            prediction = EdgePrediction(filling.relations[0])
        elif isinstance(prediction, Abstain):
            prediction = Abstain(reason="no_projectable_relation")
        edge = prediction.edge if isinstance(prediction, EdgePrediction) else None
        results.append({"R": d.name, "predicted_edge": edge.to_dict() if edge else None,
                        "hit": int(edge is not None and edge.predicate == held_out.predicate and edge.arguments == held_out.arguments),
                        "abstain_reason": prediction.reason if isinstance(prediction, Abstain) else None})
    return results


# ---------------------------------------------------------------- 誕生（構造上必要な子を残す）と初期成績
def _pool_pairs(base, target, alignment):
    from abm.abstraction import _structural_relation_ids
    base_by_id = {r.relation_id: r for r in base.relations}
    target_by_id = {r.relation_id: r for r in target.relations}
    raw = [(base_by_id[l], target_by_id[r]) for l, r in sorted(alignment.relation_mapping.items())
           if l in base_by_id and r in target_by_id]
    sids = _structural_relation_ids(base)
    return [p for p in raw if p[0].relation_id in sids and p[0].predicate == p[1].predicate]


def _drop_childless(S, base_ids):
    S = list(S)
    dropped = 0
    while True:
        ids = {r.relation_id for r in S}
        bad = {r.relation_id for r in S if any(a in base_ids and a not in ids for a in r.arguments)}
        if not bad:
            return S, dropped
        dropped += len(bad)
        S = [r for r in S if r.relation_id not in bad]


def _init_rec(d, row, state, base, target, trial, base_age, config):
    """誕生の初期成績（仕様 3 節）：二場面で三方式を採点。各場面の再現対象は、その席の登録に使った関係（述語は固定名と同じ）。"""
    if CFG["init"] == "zero":
        return SeatRec(0, "F", trial, trial, ZERO4, ZERO4)
    p = row.relation.predicate
    h, h_why = h_answer(d, row, state.slot_history, state.p_hat, config.local_lambda, config.higher_order_predicates)
    u_cur, u_why = u_answer(d, row, target, state.p_hat, config.higher_order_predicates)
    u_old, u_why_old = u_answer(d, row, base, state.p_hat, config.higher_order_predicates)
    s_old = (1.0, float(h == p), float(u_old == p), 1.0)
    s_cur = (1.0, float(h == p), float(u_cur == p), 1.0)
    w = tuple(f ** max(base_age, 0) for f in CFG["decay"])
    init = tuple(tuple(k * so + sc for k in w) for so, sc in zip(s_old, s_cur))
    CTX["births_rec"].append({"slot": row.slot_index, "F": 1, "H": int(h == p), "U旧": int(u_old == p), "U今": int(u_cur == p),
                              "H答え": h, "U答え": [u_old, u_cur], "理由": [h_why, u_why_old, u_why],
                              "履歴": hist_counts(state.slot_history.get((d.name, row.slot_index)))})
    return SeatRec(0, "F", trial, trial, init, ZERO4)


def reconcile(state, trial, why):
    """席の記録を今の表し方に合わせる：U→H の覚え直しは新しい世代（成績 0）。記録の無い席（誕生直後でないもの）は作る。"""
    state = ensure(state)
    seats = dict(state.v39_seats)
    changed = False
    for d in state.definitions.values():
        for row in d.constituents:
            key = (d.name, row.slot_index)
            st = seat_state(d, row, state.slot_history)
            rec = seats.get(key)
            if rec is None:
                seats[key] = SeatRec(0, st, trial, trial, ZERO4, ZERO4)
                changed = True
                STATS["rec_created_late"] = STATS.get("rec_created_late", 0) + 1
            elif rec.state != st:
                if rec.state == "U" and st == "H":
                    seats[key] = SeatRec(rec.gen + 1, "H", trial, trial, ZERO4, ZERO4)
                    STATS["relearn"] = STATS.get("relearn", 0) + 1
                    CTX["relearn"].append({"R": d.name, "slot": row.slot_index, "gen": rec.gen + 1, "by": why})
                else:
                    STATS["state_drift"] = STATS.get("state_drift", 0) + 1
                    CTX["drift"].append({"R": d.name, "slot": row.slot_index, "rec": rec.state, "now": st, "by": why})
                    seats[key] = replace(rec, state=st)
                changed = True
    return replace(state, v39_seats=seats) if changed else state


# ---------------------------------------------------------------- 変換
def _candidates(state, d, t, L, n_defs):
    """定義 d の席ごとの、可能な次の一段と V。"""
    a = CFG["a"]
    out = []
    sts = {row.slot_index: seat_state(d, row, state.slot_history) for row in d.constituents}
    n_nonU = sum(1 for s in sts.values() if s != "U")
    for row in d.constituents:
        st = sts[row.slot_index]
        if st == "U":
            continue
        rec = state.v39_seats[(d.name, row.slot_index)]
        SF, SH, SU, E = rec_means(rec, t)
        h = state.slot_history.get((d.name, row.slot_index))
        if st == "F":
            dc = fixed_spec_bits(row.relation.predicate, h, L)
            V = (SF - SH) / ((E + 2 * a) * dc)
            out.append((V, "FH", d.name, row.slot_index, dc, (SF, SH, SU, E)))
        else:
            dc = hcost(h, L)
            if n_nonU == 1:   # ★ 最後の変換：定義が退役する。構造を含む実際の総解放量
                dc = definition_bits(d, state.slot_history, L) + I(n_defs) - I(n_defs - 1)
            V = (SH - SU) / ((E + 2 * a) * dc)
            out.append((V, "HU", d.name, row.slot_index, dc, (SF, SH, SU, E)))
    return out


def _convert(state, kind, R, slot, trial):
    d = state.definitions[R]
    seats = dict(state.v39_seats)
    rec = seats[(R, slot)]
    if kind == "FH":
        rows = tuple(replace(r, alive=False, relation=replace(r.relation, predicate=ERASED)) if r.slot_index == slot else r
                     for r in d.constituents)
        defs = dict(state.definitions)
        defs[R] = replace(d, constituents=rows)
        seats[(R, slot)] = replace(rec, state="H", init=(ZERO16, rec.init[1], rec.init[2], rec.init[3]),
                                   post=(ZERO16, rec.post[1], rec.post[2], rec.post[3]))
        state = replace(state, definitions=defs, v39_seats=seats)
        if (R, slot) not in state.slot_history:
            # ★ 履歴欄の無い F 席（誕生の観察で写らなかった席）：F の中身は空の表（I(0)）＋固定名の指定なので、
            #   F→H で固定名の指定だけを捨てると、空の表の H になる（仕様 6 節）。
            STATS["FH_empty_table"] = STATS.get("FH_empty_table", 0) + 1
            hist = dict(state.slot_history)
            hist[(R, slot)] = {}
            state = replace(state, slot_history=hist)
        return state, None
    hist = dict(state.slot_history)
    hist.pop((R, slot), None)
    seats[(R, slot)] = replace(rec, state="U", init=ZERO4, post=ZERO4)
    state = replace(state, slot_history=hist, v39_seats=seats)
    return _retire_if_all_U(state, R, trial)


def _retire_if_all_U(state, R, trial):
    d = state.definitions[R]
    if all(seat_state(d, r, state.slot_history) == "U" for r in d.constituents):
        defs = {k: v for k, v in state.definitions.items() if k != R}
        state = replace(state, definitions=defs,
                        merit={k: v for k, v in state.merit.items() if k[0] != R},
                        embed={k: v for k, v in state.embed.items() if k[0] != R},
                        exceptions={k: v for k, v in state.exceptions.items() if k[0] != R},
                        slot_history={k: v for k, v in state.slot_history.items() if k[0] != R},
                        v39_seats={k: v for k, v in state.v39_seats.items() if k[0] != R})
        return state, {"kind": "definition_removed", "R": R, "trial": trial, "v39": "retire", "registered_at": d.registered_at}
    return state, None


def _pick(cands, trial, k):
    vmin = min(c[0] for c in cands)
    tied = [c for c in cands if c[0] == vmin]
    if len(tied) == 1:
        return tied[0], 1
    rnd = Random(int.from_bytes(sha256(f"v39-tie\x1f{CFG['seed']}\x1f{trial}\x1f{k}".encode()).digest()[:8], "big"))
    tied.sort(key=lambda c: (c[2], c[3], c[1]))
    return tied[rnd.randrange(len(tied))], len(tied)


def run_conversions(state, trial):
    L = code_lengths(state.p_hat)
    events = []
    conv = []
    before = total_bits(state, L)
    total = before
    by_def = {R: _candidates(state, d, trial, L, len(state.definitions)) for R, d in state.definitions.items()}
    k = 0
    ties = 0
    phase = "neg"
    boundary = {"最高削除点": None, "最低保持点": None, "同点で選んだ": 0}
    B = CFG["budget"]
    LAM = CFG.get("price") or 0
    while True:
        cands = [c for cs in by_def.values() for c in cs]
        if phase == "neg":
            # ★ v3.10 --v39-price λ：V＜λ の変換を、候補がなくなるまで低い点から一段ずつ（λ＝0 なら v3.9 の V＜0 の段と同じ）
            neg = [c for c in cands if c[0] < LAM] if LAM else [c for c in cands if c[0] < 0]
            if not neg:
                phase = "cap"
                continue
            pool = neg
        else:
            if B is None or total <= B:
                break
            if not cands:
                raise Unfit(json.dumps({"trial": trial, "total": total, "budget": B, "defs": len(state.definitions)}))
            pool = cands
        c, nt = _pick(pool, trial, k)
        k += 1
        if nt > 1:
            ties += 1
            if phase == "cap":
                boundary["同点で選んだ"] += 1
        V, kind, R, slot, dc, sc = c
        rec0 = state.v39_seats[(R, slot)]
        d0 = state.definitions[R]
        w0 = _pow(max(trial - rec0.t0, 0))
        split = [[round(mean16([x * k for x, k in zip(col, w0)]), 6) for col in rec0.init],
                 [round(mean16([x * k for x, k in zip(col, w0)]), 6) for col in rec0.post]]
        state, ev = _convert(state, kind, R, slot, trial)
        rec = state.v39_seats.get((R, slot))
        reg_at = next((r.registered_at for r in (state.definitions.get(R) or d0).constituents if r.slot_index == slot), None)
        # ★ F→H は、今の解析の道具が読む行の死（kind＝"deletion"）として書く。H→U は新しい種類
        e = {"kind": "deletion" if kind == "FH" else "v39_HU", "v39": kind, "R": R, "slot_index": slot,
             "registered_at": reg_at, "trial": trial, "V": V, "dC": dc,
             "why": ("price" if phase == "neg" and V >= 0 else phase),
             "tie_n": nt, "S": list(sc), "S_init_post": split, "gen": rec.gen if rec is not None else None}
        events.append(e)
        conv.append(e)
        if phase == "cap":
            boundary["最高削除点"] = V if boundary["最高削除点"] is None else max(boundary["最高削除点"], V)
        new_total = total_bits(state, L)
        if total - new_total != dc:
            STATS["dC_mismatch"] = STATS.get("dC_mismatch", 0) + 1
            CTX["cost_mismatch"].append({"trial": trial, "kind": kind, "R": R, "slot": slot, "dC": dc, "actual": total - new_total})
        total = new_total
        if ev is not None:
            events.append(ev)
            by_def.pop(R, None)
            # ★ 定義の数が減ると、ほかの定義の「最後の変換」の解放量が変わる
            by_def = {R2: _candidates(state, state.definitions[R2], trial, L, len(state.definitions)) for R2 in by_def}
        else:
            by_def[R] = _candidates(state, state.definitions[R], trial, L, len(state.definitions))
    after = total
    if conv and any(c["why"] == "cap" for c in conv):
        rest = [c[0] for cs in by_def.values() for c in cs]
        boundary["最低保持点"] = min(rest) if rest else None
    else:
        boundary = None
    if CFG.get("dump_cands"):
        CTX["last_cands"] = [c[0] for cs in by_def.values() for c in cs]
    return state, events, before, after, ties, boundary


# ---------------------------------------------------------------- 入れる所
def install(fo, *, seed: int, horizon: int, seed_file: str, budget, init: str, a: float, u: str,
            decay_mode: str = "uniform", price=None, dump_cands=None) -> None:
    import abm.abstraction as ab
    import abm.agent_runtime as ar
    import abm.loop as loop
    import sweep
    import v32
    from abm.accounting import decay_ladder
    from abm.seed import load_seed

    STATS.clear()
    CFG.clear()
    CTX.clear()
    REG.clear()
    _POW.clear()
    dictionary = list(load_seed(seed_file).data["marginal"].keys())
    CFG.update(seed=seed, T=horizon, budget=budget, init=init, a=float(a), u_abstain=(u == "abstain"),
               decay=decay_ladder(horizon), D=len(dictionary), dict_index={p: i for i, p in enumerate(dictionary)},
               rho=v32.STATS.get("rho"), argmax=bool(v32.STATS.get("argmax")), commons=bool(v32.STATS.get("commons")))
    # ★ v3.10：平均の重み（--v39-decay actr）・1 ビットの値段 λ（--v39-price）・較正用の候補の点数の書き出し
    if decay_mode not in ("uniform", "actr"):
        raise ValueError(decay_mode)
    if price is not None and budget is not None:
        raise ValueError("--v39-price は予算無限（--v39-budget inf）で使う")
    if decay_mode == "actr":
        CFG["mean_weights"] = actr_weights(horizon)
    if price is not None:
        CFG["price"] = float(price)
    if dump_cands:
        CFG["dump_cands"] = open(dump_cands, "wb")
    STATS.update(trials=0, scored_trials=0, scored_seats=0, births=0, birth_noop=0, birth_childless_dropped=0,
                 conv_FH=0, conv_HU=0, retire=0, neg_conv=0, cap_conv=0, ties=0, max_usage=0, relearn=0,
                 price_conv=0, cfg={**{k: CFG[k] for k in ("budget", "init", "a", "u_abstain", "D", "T", "rho", "argmax", "commons")},
                                    "decay_mode": decay_mode, "price": price})
    CTX.update(struct_cache={}, births_rec=[], relearn=[], drift=[], cost_mismatch=[], answers=None, output=None)
    _install_candidates()

    # 状態の型（席の記録を足す）
    sweep.AgentState = _state_class()

    # 予測・同定・反実仮想
    loop.predict = predict
    loop._identify_definition = identify
    loop._counterfactual_predictions = counterfactuals

    # 会計（v3.8 の包みの外）：U→H の覚え直し（D-10）と、三答えの採点
    real_accounting = loop._update_accounting

    def update_accounting(state, output, scene, config, horizon_, score, coin, revealed_edge):
        CTX["relearn"] = []
        CTX["drift"] = []
        next_state, acc = real_accounting(state, output, scene, config, horizon_, score, coin, revealed_edge)
        t = coin.t
        next_state = reconcile(next_state, t, "会計")
        ans = CTX.pop("answers", None)
        scored = []
        # ★ 本人が開示を受けた試行だけ（研究者用の伏せ辺は、開示が無ければ読まない）
        received = revealed_edge if coin.f_fired else None
        if ans is not None and received is not None:
            seats, scored = score_answers(next_state.v39_seats, ans, received, t)
            next_state = replace(next_state, v39_seats=seats)
            STATS["scored_trials"] += bool(scored)
            STATS["scored_seats"] += len(scored)
        CTX["trial_rec"] = {"answers": ans, "scored": scored, "relearn_acc": list(CTX["relearn"]),
                            "drift_acc": list(CTX["drift"])}
        return next_state, acc

    loop._update_accounting = update_accounting

    # 誕生と同化（m1）：構造上必要な子を残す・観察の写しを F/H/U の表し方で・初期成績
    real_m1 = loop.m1

    def m1(state, base, target, alignment, trial, **kw):
        state = ensure(state)
        CTX["births_rec"] = []
        CTX["relearn"] = []
        CTX["drift"] = []
        name = kw.get("name")
        info = None
        if name is None:
            pairs = _pool_pairs(base, target, alignment)
            S, dropped = _drop_childless([l for l, _ in pairs], {r.relation_id for r in base.relations})
            STATS["birth_childless_dropped"] += dropped
            info = {"pool": len(pairs), "dropped": dropped, "kept": len(S)}
            if len(S) < 2:
                STATS["birth_noop"] += 1
                CTX["m1_rec"] = {"birth_noop": info}
                return state, None
            keep = {r.relation_id for r in S}
            alignment = replace(alignment, relation_mapping={k: v for k, v in alignment.relation_mapping.items() if k in keep})
        pre_hist = state.slot_history
        orig_dg = ab._definition_graph
        made = []

        def dg(definition, *, mode="all"):
            g = v39_graph(definition, pre_hist)
            made.append(g)
            return g

        ab._definition_graph = dg
        try:
            out, reg = real_m1(state, base, target, alignment, trial, **kw)
        finally:
            ab._definition_graph = orig_dg
            for g in made:
                unregister(g)
        out = ensure(out)
        if CFG.get("u_position"):
            import uposition
            out = uposition.decorate(out, state, base, reg)
        if reg is not None and not reg["was_extension"]:
            R = reg["R"]
            d = out.definitions[R]
            seats = dict(out.v39_seats)
            for row in d.constituents:
                seats[(R, row.slot_index)] = _init_rec(d, row, out, base, target, trial,
                                                        trial - kw["base_written_at"], CTX["config"])
            out = replace(out, v39_seats=seats)
            STATS["births"] += 1
        out = reconcile(out, trial, "m1")
        CTX["m1_rec"] = {"birth": info, "reg": (reg["R"], bool(reg["was_extension"])) if reg else None,
                         "births_rec": list(CTX["births_rec"]), "relearn_m1": list(CTX["relearn"]), "drift_m1": list(CTX["drift"])}
        return out, reg

    loop.m1 = m1

    # 設定を控える（初期成績の H・U の答えに local_lambda・高階の語が要る）
    real_predict = loop.predict

    def predict_wrapped(agent_input, state, config, rng):
        CTX["config"] = config
        CTX["m1_rec"] = None
        CTX["trial_rec"] = None
        return real_predict(agent_input, state, config, rng)

    loop.predict = predict_wrapped

    # 削除の段（tools/v3_run.py の theta_wrapped が呼ぶ）：逐語の枚の削除（今の別基準）→ 変換
    def apply(state, config, trial, *, horizon=None):
        from abm.domains import Prototype
        state = ensure(state)
        events = []
        prototype = state.prototype
        if prototype.traces:
            surviving = prototype.alive(trial, config.verbatim_threshold)
            for tr in prototype.traces:
                if tr not in surviving:
                    events.append({"kind": "verbatim_deletion", "graph_id": tr.scene.graph_id, "written_at": tr.written_at,
                                   "trial": trial, "sigma": tr.sigma(trial)})
            state = replace(state, prototype=Prototype(surviving))
        CTX["cost_mismatch"] = []
        state, conv_events, before, after, ties, boundary = run_conversions(state, trial)
        events.extend(conv_events)
        if CFG.get("dump_cands"):
            from array import array
            array("d", [v for v in CTX.get("last_cands", ()) if v > 0]).tofile(CFG["dump_cands"])
            CFG["dump_cands"].flush()
        STATS["trials"] += 1
        STATS["max_usage"] = max(STATS["max_usage"], after)
        for e in conv_events:
            k = e.get("v39")
            if k == "FH":
                STATS["conv_FH"] += 1
            elif k == "HU":
                STATS["conv_HU"] += 1
            elif k == "retire":
                STATS["retire"] += 1
            if k in ("FH", "HU"):
                STATS["neg_conv" if e["why"] == "neg" else "price_conv" if e["why"] == "price" else "cap_conv"] += 1
        STATS["ties"] += ties
        nF = nH = nU = 0
        for d in state.definitions.values():
            for row in d.constituents:
                st = seat_state(d, row, state.slot_history)
                nF += st == "F"; nH += st == "H"; nU += st == "U"
        tr = CTX.get("trial_rec") or {}
        rec = {"kind": "v39", "trial": trial, "F": nF, "H": nH, "U": nU, "defs": len(state.definitions),
               "bits_before": before, "bits_after": after, "B": CFG["budget"],
               "conv": [[e["v39"], e["R"], e["slot_index"], e["V"], e["dC"], e["why"], e["tie_n"]]
                        for e in conv_events if e.get("v39") in ("FH", "HU")],
               "retire": [e["R"] for e in conv_events if e.get("v39") == "retire"],
               "boundary": boundary, "scored": tr.get("scored"), "m1": CTX.get("m1_rec")}
        ans = tr.get("answers")
        if ans is not None:
            rec["R_used"] = ans["R"]
            rec["answers"] = [[it["slot"], it["st"], it.get("pos") is not None, it.get("ans"), it.get("U答え")]
                              for it in ans["items"]]
            rec["fill"] = [list(x) for x in zip(ans["fill_ids"], ans["fill_states"])]
        if tr.get("relearn_acc") or tr.get("drift_acc"):
            rec["acc"] = {"relearn": tr.get("relearn_acc"), "drift": tr.get("drift_acc")}
        if CTX["cost_mismatch"]:
            rec["cost_mismatch"] = CTX["cost_mismatch"]
        fo.write(json.dumps(rec, ensure_ascii=False) + "\n")
        return state, tuple(events)

    CTX["apply"] = apply

"""v3.10 E（2026-09-29、委任書「D（ACT-R の忘却）と E（まとめる圧縮）」の第 2 部）：旗 --v310-merge。
基準は v3.10-main（cd8dc52）。tools/v39.py の上に載せる（v39.install のあとに install する）。★ abm/ は変えない。旗を切れば何もしない。

同化か誕生かを、同化の基準 NSIM の代わりに「その場面を一番短く書けるところに入れる」で決める（中華料理店過程を記述の長さで書いたもの）。
  想起と共通構造（土台と今の場面）は今のまま（tools/v32.py commons_graph）。定義 k の写しは今の同定と同じ（v39_graph → sme.map_graphs）。
  生きている定義 k の費用（ビット）＝
      −log₂(n_k ÷ (N ＋ α))                                   n_k＝assimilation_count（誕生で 1、同化で ＋1）、N＝生きている定義の和
    ＋ Σ_{写った F・H の席} −log₂ P_k(述語 | 席)              P＝（席での回数 ＋ 全体での割合）÷（席の合計回数 ＋ 1）
    ＋ Σ_{共通構造の、どの席にも写らなかった関係}（L(述語) ＋ 引数を書くビット）
    ＋ Σ_{写らなかった F・H の席} −log₂(1 − p_在)             p_在＝（在った ＋ 0.5）÷（数えた ＋ 1）。U の席は入れない
  新しい定義の費用＝ −log₂(α ÷ (N ＋ α)) ＋ 共通構造から生まれる定義（構造上必要な子を残したもの）を仕様 6 節で書いたビット（各席の履歴 1 回）
  argmin：一番小さい費用。sample：確率 ∝ 2^(−費用)（乱数は世界・開示と別。種と試行から作る）。
  既存を選べば今の同化（m1 に名前を渡す）、新しいものを選べば今の誕生（名前なし）。共通構造が 2 行未満なら今までどおり（名前なし）。
「在った・数えた」の記録（新しい）：席ごとに 16 本の減衰（v39 の成績と同じ φ）、平均は v39.mean16（--v39-decay actr の重み）。
  選ばれて使われた（R_used）・同化の先になったときに、各席を数える（写った席は在った）。誕生の試行は 0 から。
委任書だけで一つに決まらない点（control/2026-09-29_E_仕様の問い_マック.md の Q1〜Q6）は、--v310-opts で必ず指定する（既定を置かない）。
  q1＝a|b（写らなかった関係の引数のビットの e・m：a 共通構造、b 定義 k）
  q2＝a|b（U→H の覚え直しで在った・数えたを：a 0 から、b 持ち越す）
  q3＝a|b（同化の先の「写った席」：a 今の同化で履歴に足された席、b E の費用の写しで写った席）
  q4＝a|b（使われたことを数える時点：a その試行の会計、b E の選択と登録のあと）
  q5＝a|b（新しい定義が 2 行未満になるとき：a 選択肢から外す、b 外す前の行で費用を計り、選ばれたら登録しない）
  q6＝a|b|c（argmin の同点で新しい定義を：a 回数 0・今の試行の誕生として並べる、b 既存より先、c 既存より後）
（B＋E の --v310-merge-price は、2 本目の追記「単位の設計が決まるまで実装しない」により外した。）
使い方：tools/v3_run.py --v39 ... --v310-merge --v310-alpha α --v310-merge-select argmin|sample --v310-opts q1=a,q2=a,q3=a,q4=a,q5=a,q6=a
"""
from __future__ import annotations

import json
import math
from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from hashlib import sha256
from random import Random

STATS: dict = {}
CFG: dict = {}
CTX: dict = {}
OPTS_KEYS = {"q1": "ab", "q2": "ab", "q3": "ab", "q4": "ab", "q5": "ab", "q6": "abc"}


def parse_opts(s: str) -> dict:
    out = {}
    for part in (s or "").split(","):
        if not part.strip():
            continue
        k, v = part.strip().split("=")
        if k not in OPTS_KEYS or v not in OPTS_KEYS[k]:
            raise ValueError(f"--v310-opts の {part} が分からない")
        out[k] = v
    missing = sorted(set(OPTS_KEYS) - set(out))
    if missing:
        raise ValueError(f"--v310-opts に {missing} が無い（既定は置かない。control/2026-09-29_E_仕様の問い_マック.md）")
    return out


# ---------------------------------------------------------------- 在った・数えた（席ごと・16 本の減衰）
@dataclass(frozen=True, slots=True)
class PresRec:
    gen: int                  # v39 の席の世代（U→H の覚え直しで増える）
    t0: int
    counted: tuple
    present: tuple


def _zero(gen: int, t: int) -> PresRec:
    import v39
    return PresRec(gen, t, v39.ZERO16, v39.ZERO16)


def pres_add(rec: PresRec, t: int, present: bool) -> PresRec:
    import v39
    w = v39._pow(max(t - rec.t0, 0))
    c = tuple(x * k + 1.0 for x, k in zip(rec.counted, w))
    p = tuple(x * k + (1.0 if present else 0.0) for x, k in zip(rec.present, w))
    return PresRec(rec.gen, t, c, p)


def pres_values(rec: PresRec | None, t: int) -> tuple:
    """(在った, 数えた)：減衰させてから v39.mean16 で一つの量にする。"""
    import v39
    if rec is None:
        return 0.0, 0.0
    w = v39._pow(max(t - rec.t0, 0))
    return (v39.mean16([x * k for x, k in zip(rec.present, w)]), v39.mean16([x * k for x, k in zip(rec.counted, w)]))


def p_present(rec, t) -> float:
    pr, cn = pres_values(rec, t)
    return (pr + 0.5) / (cn + 1.0)


def seat_rec(state, R, slot):
    """席の在った・数えたの記録。v39 の席の世代が変わっていれば（U→H の覚え直し）、q2 に従う。"""
    rec = state.v310_pres.get((R, slot))
    v = state.v39_seats.get((R, slot))
    gen = v.gen if v is not None else 0
    if rec is None:
        return None, gen
    if rec.gen != gen:
        return (None if CFG["opts"]["q2"] == "a" else replace(rec, gen=gen)), gen
    return rec, gen


# ---------------------------------------------------------------- 状態の型（在った・数えたの記録を足す）
def _install_state_class():
    import sweep
    import v39
    base = v39._state_class()
    if getattr(base, "__name__", "") == "AgentStateV310E":
        return base

    @dataclass(frozen=True, slots=True)
    class AgentStateV310E(base):
        v310_pres: Mapping = field(default_factory=dict)

    v39._STATE_CLS[:] = [AgentStateV310E]
    sweep.AgentState = AgentStateV310E
    return AgentStateV310E


# ---------------------------------------------------------------- 費用
def _arg_bits(rel, rel_ids, e, m):
    import v39
    return v39.I(len(rel.arguments)) + sum(1 + (v39.clog2(m) if a in rel_ids else v39.clog2(e)) for a in rel.arguments)


def _share(p_hat, p) -> float:
    return p_hat.counts.get(p, 0) / p_hat.total if p_hat.total else 0.0


def cost_existing(state, d, C, N, t, L, scene_rel_ids):
    """定義 d で共通構造 C を書く費用。返り値：(費用, 内訳, 写った席の集合)。"""
    import abm.sme as sme
    import v39
    alpha = CFG["alpha"]
    g = v39.v39_graph(d, state.slot_history)
    try:
        res = sme.map_graphs(g, C)
    finally:
        v39.unregister(g)
    rm = res.alignment.relation_mapping
    C_by_id = {r.relation_id: r for r in C.relations}
    n_k = d.assimilation_count
    choose = -math.log2(n_k / (N + alpha))
    fit = absent = 0.0
    mapped_C = set()
    mapped_slots = set()
    for row in d.constituents:
        st = v39.seat_state(d, row, state.slot_history)
        if st == "U":
            continue
        cid = rm.get(row.relation.relation_id)
        if cid in C_by_id:
            p = C_by_id[cid].predicate
            h = v39.hist_counts(state.slot_history.get((d.name, row.slot_index)))
            P = (h.get(p, 0) + _share(state.p_hat, p)) / (sum(h.values()) + 1.0)
            fit += -math.log2(P)
            mapped_C.add(cid)
            mapped_slots.add(row.slot_index)
        else:
            rec, _ = seat_rec(state, d.name, row.slot_index)
            absent += -math.log2(1.0 - p_present(rec, t))
    if CFG["opts"]["q1"] == "a":
        e = len({a for r in C.relations for a in r.arguments if a not in scene_rel_ids})
        m = len(C.relations)
    else:
        rel_ids = {row.relation.relation_id for row in d.constituents}
        e = len({a for row in d.constituents for a in row.relation.arguments if a not in rel_ids})
        m = len({row.slot_index for row in d.constituents})
    unm = 0.0
    for r in C.relations:
        if r.relation_id in mapped_C:
            continue
        # 引数が関係か物かは、場面の関係の ID かどうかで決める（q1＝b でも同じ）
        unm += v39.L_of(r.predicate, L) + _arg_bits(r, scene_rel_ids, e, m)
    total = choose + fit + unm + absent
    return total, {"選ぶ": choose, "当てはまり": fit, "写らない関係": unm, "無い席": absent}, mapped_slots


class _Row:
    __slots__ = ("relation", "slot_index")

    def __init__(self, relation, slot_index):
        self.relation = relation
        self.slot_index = slot_index


class _Def:
    __slots__ = ("constituents",)

    def __init__(self, rows):
        self.constituents = rows


def new_definition_rows(base, target, alignment):
    """今の誕生と同じ手順（tools/v39.py の m1：_pool_pairs → _drop_childless）で、生まれる定義の行（土台の側）を返す。"""
    import v39
    pairs = v39._pool_pairs(base, target, alignment)
    S, _ = v39._drop_childless([l for l, _ in pairs], {r.relation_id for r in base.relations})
    return [l for l, _ in pairs], S


def cost_new(rows, N, L):
    """新しい定義の費用：−log₂(α ÷ (N ＋ α)) ＋ 仕様 6 節の定義のビット（各席は F、履歴は {述語: 1}）。"""
    import v39
    alpha = CFG["alpha"]
    d = _Def([_Row(r, i) for i, r in enumerate(rows)])
    bits = v39.structure_bits(d)
    for r in rows:
        h = {r.predicate: 1}
        bits += 2 + v39.hcost(h, L) + v39.fixed_spec_bits(r.predicate, h, L)
    choose = -math.log2(alpha / (N + alpha))
    return choose + bits, {"選ぶ": choose, "定義のビット": bits}


# ---------------------------------------------------------------- 選ぶ（identify の差し替え）
def choose(state, scene, trial):
    import v32
    import v39
    output = v39.CTX["output"]
    C = v32.commons_graph(scene, output)
    CTX["choice"] = None
    if C is None:
        STATS["commons_lt2"] += 1
        return None                                         # ★ 今までどおり（名前なし → m1 の誕生も 2 行未満で何もしない）
    L = v39.code_lengths(state.p_hat)
    scene_rel_ids = {r.relation_id for r in scene.relations}
    defs = sorted(state.definitions.values(), key=lambda d: (-d.assimilation_count, -d.registered_at, d.name))
    N = sum(d.assimilation_count for d in defs)
    opts = []                                               # (費用, 並びの鍵, 名前 or None, 内訳)
    mapped = {}
    for i, d in enumerate(defs):
        c, parts, ms = cost_existing(state, d, C, N, trial, L, scene_rel_ids)
        mapped[d.name] = ms
        opts.append([c, (-d.assimilation_count, -d.registered_at, d.name), d.name, parts])
    raw_rows, rows = new_definition_rows(output.trace["selected_scene"], scene, output.trace["alignment"])
    new_ok = len(rows) >= 2
    if new_ok or CFG["opts"]["q5"] == "b":
        c, parts = cost_new(rows if new_ok else raw_rows, N, L)
        q6 = CFG["opts"]["q6"]
        key = {"a": (0, -trial, ""), "b": (float("-inf"),), "c": (float("inf"),)}[q6]
        opts.append([c, key, None, parts])
    else:
        STATS["new_excluded"] += 1
    if not opts:
        return None
    if CFG["select"] == "argmin":
        lo = min(o[0] for o in opts)
        tied = sorted((o for o in opts if o[0] == lo), key=lambda o: o[1])
        pick = tied[0]
        STATS["ties"] += len(tied) > 1
    else:
        rnd = Random(int.from_bytes(sha256(f"v310-merge\x1f{CFG['seed']}\x1f{trial}".encode()).digest()[:8], "big"))
        lo = min(o[0] for o in opts)
        order = sorted(opts, key=lambda o: o[1])
        w = [2.0 ** (-(o[0] - lo)) for o in order]
        u = rnd.random() * sum(w)
        acc = 0.0
        pick = order[-1]
        for o, wi in zip(order, w):
            acc += wi
            if u < acc:
                pick = o
                break
    STATS["chose_new" if pick[2] is None else "chose_existing"] += 1
    CTX["choice"] = {"R": pick[2], "mapped": sorted(mapped.get(pick[2], ())) if pick[2] else None}
    CTX["side"] = {"kind": "v310E", "trial": trial, "N": N, "n_opts": len(opts), "new_ok": new_ok,
                   "chosen": pick[2], "cost": round(pick[0], 6), "parts": {k: round(v, 6) for k, v in pick[3].items()},
                   "costs": sorted([[o[2], round(o[0], 6)] for o in opts], key=lambda x: x[1])[:8]}
    return pick[2]


# ---------------------------------------------------------------- 在った・数えたを足す
def count_use(state, output, scene, t):
    """選ばれて使われた定義（R_used）の各席を数える。写った席（予測の定義の写しで、場面の見えている関係に写った席）は在った。"""
    R = output.trace.get("R_used")
    da = output.trace.get("definition_alignment")
    if not R or da is None or R not in state.definitions:
        return state
    scene_ids = {r.relation_id for r in scene.relations}
    d = state.definitions[R]
    pres = dict(state.v310_pres)
    for row in d.constituents:
        rec, gen = seat_rec(state, R, row.slot_index)
        rec = rec or _zero(gen, t)
        pres[(R, row.slot_index)] = pres_add(rec, t, da.relation_mapping.get(row.relation.relation_id) in scene_ids)
    STATS["use_counted"] += 1
    return replace(state, v310_pres=pres)


def count_assim(state, R, t, present_slots):
    d = state.definitions[R]
    pres = dict(state.v310_pres)
    for row in d.constituents:
        rec, gen = seat_rec(state, R, row.slot_index)
        rec = rec or _zero(gen, t)
        pres[(R, row.slot_index)] = pres_add(rec, t, row.slot_index in present_slots)
    STATS["assim_counted"] += 1
    return replace(state, v310_pres=pres)


def prune(state):
    live = set(state.definitions)
    if all(k[0] in live for k in state.v310_pres):
        return state
    return replace(state, v310_pres={k: v for k, v in state.v310_pres.items() if k[0] in live})


# ---------------------------------------------------------------- 入れる所
def install(fo, *, seed: int, alpha: float, select: str, opts: str) -> None:
    import abm.loop as loop
    import v39
    if select not in ("argmin", "sample"):
        raise ValueError(select)
    if not alpha > 0:
        raise ValueError("--v310-alpha は正の数")
    STATS.clear()
    CFG.clear()
    CTX.clear()
    CFG.update(seed=seed, alpha=float(alpha), select=select, opts=parse_opts(opts))
    STATS.update(calls=0, commons_lt2=0, chose_new=0, chose_existing=0, ties=0, new_excluded=0, use_counted=0,
                 assim_counted=0, cfg={"alpha": float(alpha), "select": select, "opts": dict(CFG["opts"])})
    _install_state_class()

    # 同定の差し替え：NSIM の代わりに記述の長さで選ぶ（threshold は使わない）
    def identify(state, scene, threshold, self_score_cache=None, *, identification_graph="all", self_score_cache_mode="legacy"):
        STATS["calls"] += 1
        state = v39.ensure(state)
        return choose(state, scene, CTX["trial"])

    loop._identify_definition = identify

    # 会計：その試行の会計で「使われた」を数える（q4＝a）。伏せ辺は読まない。何度呼ばれても同じ結果（CTX を消費しない）
    inner_acc = loop._update_accounting

    def update_accounting(state, output, scene, config, horizon_, score, coin, revealed_edge):
        CTX["trial"] = coin.t
        next_state, acc = inner_acc(state, output, scene, config, horizon_, score, coin, revealed_edge)
        next_state = v39.ensure(next_state)
        if CFG["opts"]["q4"] == "a":
            next_state = count_use(next_state, output, scene, coin.t)
        return next_state, acc

    loop._update_accounting = update_accounting

    # m1：誕生なら 0 から、同化なら数える（q3）。q4＝b ならここで「使われた」も数える
    inner_m1 = loop.m1

    def m1(state, base, target, alignment, trial, **kw):
        state = v39.ensure(state)
        pre_hist = state.slot_history
        out, reg = inner_m1(state, base, target, alignment, trial, **kw)
        out = v39.ensure(out)
        if reg is not None:
            R = reg["R"]
            if not reg["was_extension"]:
                d = out.definitions[R]
                pres = dict(out.v310_pres)
                for row in d.constituents:
                    v = out.v39_seats.get((R, row.slot_index))
                    pres[(R, row.slot_index)] = _zero(v.gen if v is not None else 0, trial)
                out = replace(out, v310_pres=pres)
            else:
                if CFG["opts"]["q3"] == "a":
                    post_hist = out.slot_history
                    present = {row.slot_index for row in out.definitions[R].constituents
                               if sum(v39.hist_counts(post_hist.get((R, row.slot_index))).values())
                               > sum(v39.hist_counts(pre_hist.get((R, row.slot_index))).values())}
                else:
                    ch = CTX.get("choice") or {}
                    present = set(ch.get("mapped") or ()) if ch.get("R") == R else set()
                out = count_assim(out, R, trial, present)
        if CFG["opts"]["q4"] == "b":
            o = v39.CTX.get("output")
            if o is not None:
                out = count_use(out, o, target, trial)
        out = prune(out)
        side = CTX.pop("side", None)
        if side is not None:
            side["reg"] = [reg["R"], bool(reg["was_extension"])] if reg else None
            fo.write(json.dumps(side, ensure_ascii=False) + "\n")
        return out, reg

    loop.m1 = m1

    # 削除の段のあと（退役）に、死んだ定義の記録を落とす
    inner_apply = v39.CTX["apply"]

    def apply(state, config, trial, *, horizon=None):
        res = inner_apply(state, config, trial, horizon=horizon)
        st = prune(v39.ensure(res[0]))
        return (st, *res[1:])

    v39.CTX["apply"] = apply

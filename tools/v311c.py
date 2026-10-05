"""v3.11c（集団化・事例伝達、2026-09-29 夕の委任書）：旗 --v311c。仕様 control/sfn_collective_spec_2026-09-29_v2.md（版 2）の 3〜7 節。
基準は U の照合・覚え直しの初期評価・同点の並べ方・候補ごとの棄権を含む個体版 B＋E（v3.10urta-main、74b60da）。★ abm/ は変えない。集団化を切れば四つの旗を付けた基準版と一字一句同じ。

仕組み（個体の走り方は変えない）
  ・一個体を一つのプロセスで、今の個体の走行（sweep.run_one → abm.loop.run_longitudinal）のまま走らせる。乱数と作業領域は個体ごとに分かれる（仕様 8 節 ②）。
  ・各試行の削除の段（tools/v3_run.py の theta_wrapped が呼ぶ v39 の apply）の一番外を包み、そこで
      (1) この試行に話していれば、開示の前に固定した束を、まとめ役へ渡す（送るか・宛先は、個体ごとの別の乱数で決めてある）
      (2) まとめ役が全員の世界試行の終わりを待ってから配る束を、無作為の順で全件、個体版の道（比較→共通部分→E で取り込み／誕生）で処理する
      (3) 100 試行ごとの回答の一致の試験（状態と乱数を変えない）
    をしてから、次の試行へ進む。世界試行の時計は進めない（受け取った束は、その試行の時刻で逐語の記憶に入れる）。
  ・まとめ役（coordinate）は、個体のプロセスと試行ごとに歩調を合わせ、宛先へ束を配り、通信の記録（研究者用）を書く。

束（仕様 3 節）
  ・実際に予測を出したときだけ作る（沈黙では作らない）。初期束＝使った定義（R_used）の F・H の席が写した、見えている関係（同じ関係は一件）＋実際の予測一件。
  ・参照先の補い：束の関係の引数にある関係を順にたどる。開示前に見えていれば、定義との対応がなくても加える。実際の予測も参照先として認める。
    それ以外（見えていない・穴埋めでできた関係など）を要る高階の関係は外し、その除外で参照が切れる上の関係も外す。
    最後に残った初期束の関係が要る参照先だけを含める。新しい予測は作らない。数：初期本数・外した本数・加えた本数・最終本数（最終＝初期−外した＋加えた）。
  ・物と関係の識別子は、束の中の対応を保って、意味の無い識別子に付け直す（別の場面との偶然の一致や出どころの漏れを防ぐ）。名札は付け直さない。
  ・受け手には、見た／予測した／参照用に加えた の区別・正誤・世界の型を渡さない（研究者用の記録にだけ書く）。
名札（仕様 5・6 節）
  ・定義ごとに名札の回数表を持つ（状態の欄 c_tags）。話すときは、使った定義の回数表（開示前）の割合で一つ引く。
  ・世界からの誕生は新しい名札を 1、報告からの誕生は受けた名札を 1 で始める。名札付きの束を取り込んだ（同化した）ときだけ、その名札に 1 足す。
    自分の発話・土台の再利用・世界の場面への同化では足さない。
  ・名札表の費用 C_name＝I(k)＋Σ_j［b＋I(n_j)］、b＝ceil(log₂ max(2, N×T))（全条件で固定）。v3.9 の総費用に足す。E の ΔC にも足す。
    席を薄くしても名札表は消えない。定義を手放すと名札表も全部空く（最後の席の変換の解放量に入れる）。名札だけを忘れる仕組みは無い（初版の制限）。
受け取り（仕様 4 節）
  ・受信 A：逐語の記憶から、今の似方の基準（予測の土台の選び方）で比べる相手を選ぶ。受信 B：同じ名札の過去の束に絞ってから同じ基準（無ければ A）。
    今回の束は比べる相手にしない。記憶が空なら、個体版の初めの扱い（何も登録しない）。
  ・土台を選んだあと、今回の束を逐語の記憶に一度入れる（場面を書くのと同じく、全体の回数表 p_hat にも書く）。そのあと個体版の道（E）で取り込み／誕生。
  ・予測と開示による採点はしない。束に無い関係は反証にしない（B＋E の取消は常に 0 本）。誕生したときだけ、個体版どおり材料二場面で初期採点。
使い方：tools/v3_run.py … --v311c --v311c-f 0.5,0.5 --v311c-q 0.2 --v311c-recv B --v311c-runs 1,2,3（くわしくは v3_run.py の説明）
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, field, fields, replace
from hashlib import sha256
from random import Random
from types import SimpleNamespace
from typing import Mapping
from v311c_fingerprint import fingerprint

STATS: dict = {}
CFG: dict = {}
CTX: dict = {}


class NotInDictionary(RuntimeError):
    """研究者側の停止。模型の費用や候補を修正しない。"""

    def __init__(self, diagnostic):
        self.diagnostic = diagnostic
        super().__init__(json.dumps(diagnostic, ensure_ascii=False, sort_keys=True))


def _install_dictionary_guard():
    import v39
    real_order = v39.dict_order
    CTX["dictionary_unknown_names"] = set()

    def record_order(name):
        result = real_order(name)
        if name not in v39.CFG["dict_index"]:
            CTX["dictionary_unknown_names"].add(name)
        return result

    # 元の関数の返り値・カウンタを継承し、取り除かれた候補の名前も控える。
    v39.dict_order = record_order


def _check_dictionary_guard(trial, phase):
    import v39
    count = v39.STATS.get("not_in_dictionary", 0)
    if count >= 1:
        diagnostic = {"kind": "v311c_not_in_dictionary", "run": CFG["run"],
                      "agent": CFG["agent"], "trial": trial, "phase": phase,
                      "count": count, "names": sorted(CTX["dictionary_unknown_names"])}
        CTX["fo"].write(json.dumps(diagnostic, ensure_ascii=False) + "\n")
        CTX["fo"].flush()
        raise NotInDictionary(diagnostic)
    STATS["dictionary_checks"] = STATS.get("dictionary_checks", 0) + 1
_STATE_CLS: list = []


# ---------------------------------------------------------------- 状態の型：名札の回数表・逐語の記憶の束の名札
def _state_class():
    import v39
    if not _STATE_CLS:
        base = v39._state_class()

        @dataclass(frozen=True, slots=True)
        class AgentStateV311(base):
            c_tags: Mapping = field(default_factory=dict)          # 定義の名前 → {名札: 回数}
            c_trace_tags: Mapping = field(default_factory=dict)    # 逐語の記憶の束（graph_id）→ 名札
        _STATE_CLS.append(AgentStateV311)
    return _STATE_CLS[0]


def ensure(state):
    import v39
    cls = _state_class()
    if isinstance(state, cls):
        return state
    state = v39.ensure(state)
    kw = {f.name: getattr(state, f.name) for f in fields(state)}
    kw.setdefault("c_tags", {})
    kw.setdefault("c_trace_tags", {})
    return cls(**kw)


def _dbg(*a):
    import os
    import sys
    import time
    if os.environ.get("V311C_DEBUG"):
        print(time.strftime("%T"), "[v311c]", *a, file=sys.stderr, flush=True)


def opaque(*parts) -> str:
    return sha256("\x1f".join(str(p) for p in parts).encode()).hexdigest()[:12]


def rng_for(*parts) -> Random:
    """世界・開示の乱数とは別の、個体ごと・試行ごと・用途ごとの乱数（再現できる）。"""
    return Random(int(sha256(("v311c\x1f" + "\x1f".join(str(p) for p in parts)).encode()).hexdigest()[:16], 16))


# ---------------------------------------------------------------- 名札
def tag_cost(tags) -> int:
    import v39
    if not tags:
        return 0
    return v39.I(len(tags)) + sum(CFG["b"] + v39.I(int(n)) for n in tags.values())


def new_tag() -> str:
    CTX["tag_counter"] += 1
    STATS["new_tags"] += 1
    if STATS["new_tags"] > CFG["tag_limit"]:
        raise RuntimeError(f"新しい名札が上限 {CFG['tag_limit']} を超えた（検査の失敗。b を途中で変えない）")
    return "n" + opaque("tag", CFG["wseed"], CTX["tag_counter"])


def sample_tag(tags, rng):
    items = sorted(tags.items())
    total = sum(n for _, n in items)
    x = rng.random() * total
    acc = 0.0
    for tag, n in items:
        acc += n
        if x < acc:
            return tag
    return items[-1][0]


def tagged_total_bits(real_total, state, L):
    """v39 の総費用 ＋ 生きている定義の名札表の費用。"""
    tags = getattr(state, "c_tags", {})
    return real_total(state, L) + sum(tag_cost(tags.get(R, {})) for R in state.definitions)


def tagged_candidates(real_cands, state, d, t, L, n_defs):
    """最後の席の変換（H→U で定義が消える）の解放量に、その定義の名札表を足す。"""
    import v39
    out = real_cands(state, d, t, L, n_defs)
    nonU = sum(1 for row in d.constituents if v39.seat_state(d, row, state.slot_history) != "U")
    extra = tag_cost(getattr(state, "c_tags", {}).get(d.name, {})) if nonU == 1 else 0
    if not extra:
        return out
    res = []
    for c_ in out:
        V, kind, R, slot, dc, sc = c_
        if kind == "HU":
            c_ = (V * dc / (dc + extra), kind, R, slot, dc + extra, sc)
        res.append(c_)
    return res


def tag_update(tags, R, was_extension, rtag, new_tag_fn):
    """名札の更新：世界からの誕生＝新しい名札 1、報告からの誕生＝受けた名札 1、名札付きの束の同化＝その名札に 1。世界の場面への同化は変えない。"""
    tags = dict(tags)
    if not was_extension:
        tags[R] = {(rtag if rtag is not None else new_tag_fn()): 1}
    elif rtag is not None:
        t0 = dict(tags.get(R, {}))
        t0[rtag] = t0.get(rtag, 0) + 1
        tags[R] = t0
    return tags


def choose_partner(state, G, tag, mode):
    """受信 A／B の比べる相手（仕様 4 節）。返り値：(土台の逐語, 写し, 同じ名札の候補の数, B を使ったか)。記憶が空なら土台は None。"""
    from abm.sme import map_graphs
    traces = state.prototype.traces
    same = [tr for tr in traces if state.c_trace_tags.get(tr.scene.graph_id) == tag]
    use_B = mode == "B" and bool(same)
    cand = same if use_B else list(traces)
    if not cand:
        return None, None, len(same), use_B
    ranked = [(map_graphs(tr.scene, G), tr) for tr in cand]
    if CFG.get("sme2017"):
        import smeshared
        if smeshared.CTX.get("tie_uniform"):
            mapping, base_tr = smeshared.choose_trace(ranked, G)
            return base_tr, mapping, len(same), use_B
    mapping, base_tr = sorted(ranked, key=lambda it: (-it[0].alignment.total_score, -it[1].written_at, it[1].scene.graph_id))[0]
    return base_tr, mapping, len(same), use_B


# ---------------------------------------------------------------- 束（仕様 3 節）
def build_bundle(state, output, scene, t):
    from abm.domains import EdgePrediction, Entity, Relation, RelationGraph
    import v39
    p = output.prediction
    R = output.trace.get("R_used")
    if not isinstance(p, EdgePrediction) or R is None or R not in state.definitions:
        return None
    d = state.definitions[R]
    al = output.trace.get("definition_alignment")
    scene_rel = {r.relation_id: r for r in scene.relations}
    ents = {e.entity_id for e in scene.entities}
    pred = p.edge
    aligned = []
    for row in sorted(d.constituents, key=lambda r: r.slot_index):
        if v39.seat_state(d, row, state.slot_history) == "U":
            continue
        cid = al.relation_mapping.get(row.relation.relation_id) if al is not None else None
        if cid in scene_rel and cid not in aligned:
            aligned.append(cid)
    rels = dict(scene_rel)
    rels[pred.relation_id] = pred
    initial = aligned + [pred.relation_id]
    # 参照先をたどる（見えている関係は加える。予測も参照先として認める。それ以外が要る関係は外す）
    cand = list(initial)
    seen = set(cand)
    bad = {}
    i = 0
    while i < len(cand):
        rid = cand[i]
        i += 1
        for a in rels[rid].arguments:
            if a in ents:
                continue
            if a in scene_rel:
                if a not in seen:
                    seen.add(a)
                    cand.append(a)
            elif a == pred.relation_id:
                pass
            else:
                bad.setdefault(rid, f"参照先 {a} が開示前に見えていない（予測でもない）")
    changed = True
    while changed:
        changed = False
        for rid in cand:
            if rid in bad:
                continue
            for a in rels[rid].arguments:
                if a in bad:
                    bad[rid] = f"参照先 {a} が外れた"
                    changed = True
                    break
    survivors = [rid for rid in initial if rid not in bad]
    final = list(survivors)
    fs = set(final)
    j = 0
    while j < len(final):
        for a in rels[final[j]].arguments:
            if a in scene_rel and a not in fs and a not in bad:
                fs.add(a)
                final.append(a)
            elif a == pred.relation_id and a not in fs and a not in bad:
                fs.add(a)
                final.append(a)
        j += 1
    added = [rid for rid in final if rid not in set(initial)]
    excluded = [rid for rid in initial if rid in bad]
    assert len(final) == len(initial) - len(excluded) + len(added)
    if not final:
        return {"empty": True, "initial": len(initial), "excluded": len(excluded), "pred_excluded": pred.relation_id in bad}
    # 識別子を付け直す（束の中の対応は保つ）
    ent_used = sorted({a for rid in final for a in rels[rid].arguments if a in ents})
    emap = {e: "e" + opaque(CFG["wseed"], t, "e", e) for e in ent_used}
    rmap = {rid: "r" + opaque(CFG["wseed"], t, "r", rid) for rid in final}
    new_rels = tuple(Relation(rmap[rid], rels[rid].predicate,
                              tuple(emap.get(a, rmap.get(a, a)) for a in rels[rid].arguments)) for rid in final)
    gid = "b" + opaque(CFG["wseed"], t, "bundle")
    graph = RelationGraph(graph_id=gid, entities=tuple(Entity(emap[e]) for e in ent_used), relations=new_rels)
    origin = {rmap[rid]: ("予測" if rid == pred.relation_id else "見えた（定義が写した）" if rid in aligned else "見えた（参照先として加えた）")
              for rid in final}
    return {"graph": graph, "initial": len(initial), "excluded": len(excluded), "added": len(added), "final": len(final),
            "pred_excluded": pred.relation_id in bad, "excluded_ids": {rid: bad[rid] for rid in excluded},
            "added_ids": added, "initial_ids": initial, "origin": origin, "R": R, "R_born": d.registered_at,
            "pred": [pred.relation_id, pred.predicate, list(pred.arguments)],
            "scene_n": len(scene.relations), "bundle_from_scene": sum(1 for rid in final if rid in scene_rel),
            "bundle_not_in_scene": sum(1 for rid in final if rid not in scene_rel)}


def bundle_bits(graph, tag_bits, L):
    """話の長さ（ビット）：関係の本数 I(m)＋各関係［名前の ℓ＋I(引数数)＋各引数（型 1＋ceil(log₂(物の数 又は 関係の数))）］＋名札 b。
    記録だけ（B＋E の「追加」の書き方と同じ）。"""
    import v39
    rel_ids = {r.relation_id for r in graph.relations}
    e = len(graph.entities)
    m = len(graph.relations)
    bits = v39.I(m)
    for r in graph.relations:
        bits += v39.L_of(r.predicate, L) + v39.I(len(r.arguments))
        bits += sum(1 + (v39.clog2(m) if a in rel_ids else v39.clog2(e)) for a in r.arguments)
    return bits + tag_bits


# ---------------------------------------------------------------- E（tools/v310be.py の choose_and_register の写し。★ の所だけ違う：名札表の費用と更新）
def choose_and_register(state, base, target, alignment, trial, kw, inner_m1):
    import v310be
    import v32
    import v39
    output = v39.CTX["output"]
    x = v32.commons_graph(target, output)
    recv = CTX.get("recv")
    rec = {"kind": "v310be", "trial": trial, "disclosed": v310be.CTX.get("disclosed"), "source": "報告" if recv else "世界"}
    if x is None:
        v310be.STATS["commons_lt2"] += 1
        rec["x"] = None
        v310be.CTX["side"] = rec
        return inner_m1(state, base, target, alignment, trial, **kw)
    config = v39.CTX["config"]
    lam = v310be.CFG["lam"]
    alpha = v310be.CFG["alpha"]
    L = v39.code_lengths(state.p_hat)
    scene_rel_ids = {r.relation_id for r in target.relations}
    n_defs = len(state.definitions)
    N = sum(d.assimilation_count for d in state.definitions.values())
    rtag = recv["tag"] if recv else None
    cands = []
    for d in sorted(state.definitions.values(), key=lambda d: (-d.assimilation_count, -d.registered_at, d.name)):
        h = v310be.hypo_m1(state, base, target, alignment, trial, d.name, kw)
        if h is None:
            v310be.STATS["assim_impossible"] += 1
            continue
        sa, R = h
        dC = (v39.definition_bits(sa.definitions[R], sa.slot_history, L) - v39.definition_bits(d, state.slot_history, L))
        # ★ 名札表：名札付きの束を取り込むときだけ、その名札に 1 足す（世界の場面への同化では増えない）
        t0 = state.c_tags.get(d.name, {})
        dT = (tag_cost({**t0, rtag: t0.get(rtag, 0) + 1}) - tag_cost(t0)) if rtag is not None else 0
        r, parts = v310be.rewrite(sa, R, x, L, config, scene_rel_ids)
        A = -math.log2(d.assimilation_count / (N + alpha))
        cands.append({"R": d.name, "A": A, "r": r, "dC": dC + dT, "dT": dT, "K": A + r + lam * (dC + dT), "parts": parts,
                      "key": (-d.assimilation_count, -d.registered_at, d.name)})
    h = v310be.hypo_m1(state, base, target, alignment, trial, None, kw)
    if h is None:
        v310be.STATS["new_excluded_structure"] += 1
        rec["new_excluded"] = "構造の条件（構造上必要な子を残すと 2 行未満）"
    else:
        sa, R = h
        dC = v39.definition_bits(sa.definitions[R], sa.slot_history, L) + v39.I(n_defs + 1) - v39.I(n_defs)
        dT = tag_cost({"_": 1})   # ★ 新しい定義の名札表（世界からは新しい名札、報告からは受けた名札。どちらも回数 1）
        r, parts = v310be.rewrite(sa, R, x, L, config, scene_rel_ids)
        A = -math.log2(alpha / (N + alpha))
        cands.append({"R": None, "A": A, "r": r, "dC": dC + dT, "dT": dT, "K": A + r + lam * (dC + dT), "parts": parts,
                      "key": (0, -trial, "")})
    if not cands:
        v310be.STATS["no_candidate"] += 1
        v310be.CTX["side"] = rec
        return state, None
    lo = min(c["K"] for c in cands)
    tied = sorted((c for c in cands if c["K"] == lo), key=lambda c: c["key"])
    pick = tied[0]
    v310be.STATS["ties"] += len(tied) > 1
    v310be.STATS["chose_new" if pick["R"] is None else "chose_existing"] += 1
    C0 = v39.total_bits(state, L)
    kw2 = dict(kw, name=pick["R"])
    out, reg = inner_m1(state, base, target, alignment, trial, **kw2)
    out = ensure(out)
    if reg is not None:
        # ★ 名札の更新
        out = replace(out, c_tags=tag_update(out.c_tags, reg["R"], reg["was_extension"], rtag, new_tag))
        if not reg["was_extension"]:
            STATS["birth_report" if rtag is not None else "birth_world"] += 1
        elif rtag is not None:
            STATS["assim_report"] += 1
    C1 = v39.total_bits(out, L)
    if reg is not None and abs((C1 - C0) - pick["dC"]) > 1e-9:
        v310be.STATS["dC_mismatch"] += 1
        STATS["dC_mismatch"] += 1
    if pick["R"] is not None and reg is not None:
        R = reg["R"]
        v310be.STATS["assim_match0"] += pick["parts"]["一致"] == 0
        inc = sum(sum(v39.hist_counts(out.slot_history.get(k)).values()) for k in out.slot_history if k[0] == R) \
            - sum(sum(v39.hist_counts(state.slot_history.get(k)).values()) for k in state.slot_history if k[0] == R)
        v310be.STATS["assim_hist0"] += inc == 0
        rec["hist_inc"] = inc
    rec.update({"x_rows": len(x.relations), "N": N, "lam": lam, "chosen": pick["R"], "reg": reg["R"] if reg else None,
                "was_extension": bool(reg["was_extension"]) if reg else None,
                "K": pick["K"], "r": pick["r"], "dC_pred": pick["dC"], "dT": pick["dT"],
                "dC_real": (C1 - C0) if reg is not None else None, "C_after_E": C1, "ties": len(tied),
                "cands": [[c["R"], round(c["A"], 6), round(c["r"], 6), c["dC"], round(c["K"], 6),
                           {k: v for k, v in c["parts"].items()}] for c in sorted(cands, key=lambda c: c["K"])][:12]})
    v310be.CTX["side"] = rec
    v310be.CTX["R_E_trial"] = pick["r"]
    return out, reg


# ---------------------------------------------------------------- 受け取り（仕様 4 節）
def receive_one(state, msg, t, config):
    import abm.loop as loop
    import v310be
    import v39
    from abm.accounting import update_frequency
    from abm.domains import Prototype, VerbatimTrace
    from abm.sme import map_graphs
    G = plain_to_graph(msg["graph"]) if isinstance(msg["graph"], dict) else msg["graph"]
    if CFG.get("strict_pc"):
        # 世界の観察と同じく、受け取った公開の束だけから引数の種類を控える。
        # 受信では通常採点を呼ばないので、その入口の控えをここで行う。
        import strictpc
        strictpc.record_kinds(G)
    tag = msg["tag"]
    traces = state.prototype.traces
    base_tr, mapping, n_same, use_B = choose_partner(state, G, tag, CFG["recv"])
    rec = {"t": t, "bundle": G.graph_id, "tag": tag, "recv": CFG["recv"], "same_tag_candidates": n_same,
           "used_B": use_B, "memory_empty": not traces}
    if base_tr is not None:
        rec["base"] = base_tr.scene.graph_id
        rec["base_is_report"] = base_tr.scene.graph_id in state.c_trace_tags
        rec["base_tag"] = state.c_trace_tags.get(base_tr.scene.graph_id)
        rec["base_written_at"] = base_tr.written_at
    # ★ 今回の束を普通の逐語の記憶に一度入れる（場面を書くのと同じく p_hat にも書く）。比べる相手は、その前に選んだ
    tt = dict(state.c_trace_tags)
    tt[G.graph_id] = tag
    state = replace(state, prototype=Prototype((*traces, VerbatimTrace(t, G))), p_hat=update_frequency(state.p_hat, G.relations),
                    c_trace_tags=tt)
    if base_tr is None:
        rec["result"] = "記憶が空（個体版の初めの扱い：登録しない）"
        STATS["recv_memory_empty"] += 1
        return state, rec
    seats0 = state.v39_seats
    merit0 = state.merit
    v39.CTX["output"] = SimpleNamespace(trace={"selected_scene": base_tr.scene, "alignment": mapping.alignment}, prediction=None)
    v39.CTX["m1_rec"] = None
    CTX["recv"] = {"tag": tag}
    try:
        out, reg = loop.m1(state, base_tr.scene, G, mapping.alignment, t, name=None, base_written_at=base_tr.written_at,
                           horizon=CFG["T"], pricing_rule=config.pricing_rule, refill_rule=config.refill_rule,
                           local_lambda=config.local_lambda)
    finally:
        CTX["recv"] = None
    side = v310be.CTX.pop("side", None)
    v310be.CTX["R_E_trial"] = 0.0
    rec["E"] = side
    rec["m1"] = v39.CTX.get("m1_rec")
    v39.CTX["m1_rec"] = None
    # ★ 個体版の m1 は「この試行に登録された行」の功績・埋込・例外を初期値に置き直す（一試行に m1 は一回の前提）。
    #   受け取りで、この試行に生まれた定義が同化の先になると置き直しが重なるので、受け取りの前の値に戻す（採点をしない）
    out = ensure(out)
    if reg is not None and reg["was_extension"]:
        emb0 = state.embed
        exc0 = state.exceptions
        fix = {k: merit0[k] for k in out.merit if k in merit0 and out.merit[k] is not merit0[k]}
        if fix or any(k in emb0 and out.embed[k] is not emb0[k] for k in out.embed) or any(
                k in exc0 and out.exceptions[k] is not exc0[k] for k in out.exceptions):
            STATS["recv_reinit_restored"] = STATS.get("recv_reinit_restored", 0) + 1
            out = replace(out, merit={**out.merit, **fix},
                          embed={**out.embed, **{k: emb0[k] for k in out.embed if k in emb0}},
                          exceptions={**out.exceptions, **{k: exc0[k] for k in out.exceptions if k in exc0}})
    # ★ 検査 ⑨：受け取りは通常採点しない。誕生の初期値と、覚え直し（U→H、新しい世代の初期評価だけ）のほかは、
    #   席の成績も行の功績も変わらないことを毎回確かめる
    born = reg["R"] if (reg is not None and not reg["was_extension"]) else None
    for k, v in out.v39_seats.items():
        if k[0] != born and k in seats0 and seats0[k] != v:
            a0 = seats0[k]
            if (a0.state == "U" and v.state == "H" and v.gen == a0.gen + 1
                    and v.post == v39.ZERO4 and v.n_scored == 0
                    and (v.init == v.post or CFG.get("relearn_init"))):
                STATS["recv_relearn"] = STATS.get("recv_relearn", 0) + 1
                continue
            STATS["recv_score_changed"] += 1
            if len(STATS.setdefault("recv_changed_examples", [])) < 6:
                a0 = seats0[k]
                STATS["recv_changed_examples"].append({"seat": list(k), "before": [a0.gen, a0.state, a0.t0, a0.n_scored],
                                                       "after": [v.gen, v.state, v.t0, v.n_scored], "reg": reg["R"] if reg else None,
                                                       "ext": bool(reg["was_extension"]) if reg else None})
    for k, v in out.merit.items():
        if k[0] != born and k in merit0 and merit0[k] != v:
            STATS["recv_merit_changed"] += 1
            if len(STATS.setdefault("recv_merit_examples", [])) < 4:
                STATS["recv_merit_examples"].append({"key": list(k), "reg": reg["R"] if reg else None,
                                                     "ext": bool(reg["was_extension"]) if reg else None,
                                                     "same_obj": merit0[k] is v, "b0": merit0[k].basis[:2], "b1": v.basis[:2]})
    if reg is None:
        rec["result"] = "不成立"
        STATS["recv_none"] += 1
    else:
        rec["result"] = "同化" if reg["was_extension"] else "誕生"
        rec["R"] = reg["R"]
        rec["R_born"] = ensure(out).definitions[reg["R"]].registered_at
        STATS["recv_assim" if reg["was_extension"] else "recv_birth"] += 1
    return ensure(out), rec


# ---------------------------------------------------------------- 回答の一致の試験（状態・乱数・記録を変えない）
def _snapshot_modules():
    import sys
    snap = []
    for name in ("v39", "v310be", "v38", "v32", "fix2", "fixorder2", "v31", "nocharge2", "projfirst", "fillnorestate", "v311c",
                 "histrole", "ustruct", "relearninit", "tiestruct", "strictpc", "answergap"):
        m = sys.modules.get(name)
        if m is None:
            continue
        for attr in ("CTX", "STATS", "LAST", "CFG", "REG", "UREG", "TCTX", "KINDS", "RELPOS", "NONROW", "SHADOW", "MODE"):
            d = getattr(m, attr, None)
            if isinstance(d, dict):
                # Counter の型も保つ（普通の dict に替えると、新しい項目の加算ができなくなる）。
                snap.append((d, {k: (v.copy() if isinstance(v, (dict, list, set)) else v) for k, v in d.items()}))
            elif isinstance(d, (list, set)):
                snap.append((d, d.copy()))
    sme = sys.modules.get("smeshared")
    if CFG.get("sme2017") and sme is not None and sme.ENGINE is not None:
        return snap, sme.snapshot(), sme.LOG.get("diagnostic", False)
    return snap


def _restore_modules(snap):
    if isinstance(snap, tuple):
        import smeshared
        snap, own, diagnostic = snap
        smeshared.restore(own)
        smeshared.LOG["diagnostic"] = diagnostic
    for d, saved in snap:
        d.clear()
        if isinstance(d, list):
            d.extend(saved)
        else:
            d.update(saved)


def learning_fingerprint(state):
    """研究者側で、模型の記憶とSMEの控え・専用乱数を合わせて読む。"""
    if CFG.get("sme2017"):
        import smeshared
        return fingerprint((state, smeshared.snapshot()))
    return fingerprint(state)


def probe(state, items, config):
    from abm.domains import AgentInput, EdgePrediction
    import random
    audit = CFG.get("audit", False)
    before = (learning_fingerprint(state), random.getstate()) if audit else None
    snap = _snapshot_modules()
    if CFG.get("sme2017"):
        import smeshared
        smeshared.LOG["diagnostic"] = True
    out = []
    try:
        for k, it in enumerate(items):
            scene = plain_to_graph(it["scene"]) if isinstance(it["scene"], dict) else it["scene"]
            ai = AgentInput(scene, scene, tuple(r.relation_id for r in scene.relations))
            o, _ = CFG["inner_predict"](ai, state, config, rng_for("probe", CFG["run"], k))
            p = o.prediction
            out.append([p.edge.predicate, list(p.edge.arguments)] if isinstance(p, EdgePrediction) else None)
        _check_dictionary_guard(CTX.get("t", 0), "probe")
    finally:
        _restore_modules(snap)
    if audit and before != (learning_fingerprint(state), random.getstate()):
        raise RuntimeError("一致の試験で学習状態又は本走行の乱数状態が変わった")
    return out


# ---------------------------------------------------------------- 入れる所（個体のプロセスの中で）
def install(fo, task, REAL) -> None:
    import abm.loop as loop
    import sweep
    import v310be
    import v39
    c = task["v311c"]
    STATS.clear()
    CFG.clear()
    CTX.clear()
    CFG.update(run=c["run"], agent=c["agent"], wseed=int(task["seed"]), n=c["n"], T=int(task["cfg"]["trial_count"]), q=float(c["q"]), m=float(c["m"]),
               recv=c["recv"], groups=list(c["groups"]), tags=bool(c.get("tags", True)),
               b=max(1, math.ceil(math.log2(max(2, int(c.get("b_n") or c["n"]) * int(task["cfg"]["trial_count"]))))),
               tag_limit=int(task["cfg"]["trial_count"]), conn=c.get("conn"),
               relearn_init=bool(task.get("relearn_init")), strict_pc=bool(task.get("strict_pc")),
               sme2017=bool(task.get("sme2017")))
    if c.get("audit"):
        CFG["audit"] = True
    serial = c.get("serial_lock")
    STATS.update(speak=0, bundles=0, bundle_empty=0, sent=0, new_tags=0, birth_world=0, birth_report=0, assim_report=0,
                 recv=0, recv_assim=0, recv_birth=0, recv_none=0, recv_memory_empty=0, dC_mismatch=0, probes=0,
                 recv_score_changed=0, recv_merit_changed=0,
                 cfg={k: CFG[k] for k in ("run", "agent", "n", "T", "q", "m", "recv", "groups", "tags", "b")})
    CTX.update(t=0, tag_counter=0, bundle=None, recv=None, fo=fo)
    _install_dictionary_guard()
    if CFG["tags"]:
        sweep.AgentState = _state_class()   # ★ 機能を切った検査 ① では状態の型を換えない（台帳の状態の記録が個体版と同じになるように）

    if not CFG["tags"]:
        # ★ 検査 ① 用：集団化の機能を全部切る（名札も通信もしない）。個体版と同じになることを確かめる
        CFG["q"] = 0.0
        STATS["cfg"]["tags"] = False
    else:
        # 総費用に名札表を足す（v39 の総費用・最後の席の変換の解放量）
        real_total = v39.total_bits
        v39.total_bits = lambda state, L: tagged_total_bits(real_total, state, L)
        real_cands = v39._candidates
        # ★ 最後の席の変換で定義が消える：名札表も空くビットに入れる
        v39._candidates = lambda state, d, t, L, n_defs: tagged_candidates(real_cands, state, d, t, L, n_defs)

        # E：名札の費用と更新を入れた写しで選ぶ
        inner_m1 = REAL["m1_before_be"]

        def m1(state, base, target, alignment, trial, **kw):
            state = ensure(v39.ensure(state))
            v310be.CTX["R_E_trial"] = 0.0
            kw = {k: v for k, v in kw.items() if k != "name"}
            return choose_and_register(state, base, target, alignment, trial, kw, inner_m1)

        loop.m1 = m1

    # 予測：話したら、開示の前に束を作って固定する
    real_predict = loop.predict
    CFG["inner_predict"] = real_predict

    def predict(agent_input, state, config, rng):
        output, pending = real_predict(agent_input, state, config, rng)
        t = CTX["t"]
        CTX["bundle"] = None
        CTX["config"] = config
        from abm.domains import EdgePrediction
        if isinstance(output.prediction, EdgePrediction):
            STATS["speak"] += 1
        if CFG["tags"] and isinstance(output.prediction, EdgePrediction) and output.trace.get("R_used") is not None:
            st = ensure(state)
            b = build_bundle(st, output, agent_input.target_graph_partial, t)
            if b is not None and not b.get("empty"):
                R = output.trace["R_used"]
                tags = st.c_tags.get(R, {})
                tag = sample_tag(tags, rng_for("tag", CFG["wseed"], t)) if tags else None
                send = rng_for("send", CFG["wseed"], t).random() < CFG["q"] if tag is not None else False
                to = None
                if send:
                    rr = rng_for("to", CFG["wseed"], t)
                    others = [j for j in range(CFG["n"]) if j != CFG["agent"]]
                    g = CFG["groups"][CFG["agent"]]
                    same = [j for j in others if CFG["groups"][j] == g]
                    other = [j for j in others if CFG["groups"][j] != g]
                    if CFG["n"] == 2:
                        pool = others                       # 一対一：互いに相手を選ぶ（m は使わない）
                    elif other and (not same or rr.random() < CFG["m"]):
                        pool = other
                    else:
                        pool = same
                    to = pool[rr.randrange(len(pool))]
                L = v39.code_lengths(st.p_hat)
                b.update(tag=tag, send=bool(send), to=to, t=t, sender=CFG["agent"],
                         bits=bundle_bits(b["graph"], CFG["b"], L), n_rel=len(b["graph"].relations))
                CTX["bundle"] = b
                STATS["bundles"] += 1
                STATS["sent"] += bool(send)
            elif b is not None:
                STATS["bundle_empty"] += 1
                CTX["bundle"] = {"empty": True, **b, "t": t, "sender": CFG["agent"]}
        return output, pending

    loop.predict = predict

    # 削除の段の一番外：束を渡す → 全員の世界試行を待つ → 届いた束を処理 → 試験 → 次の試行へ
    real_apply = REAL["theta_impl"]

    def apply(state, config, trial, **kw):
        state, events = real_apply(state, config, trial, **kw)
        _check_dictionary_guard(trial, "world")
        if CFG["tags"]:
            state = ensure(state)
            # 消えた定義の名札表・消えた逐語の記憶の名札を片付ける（同じ名前で生まれ直した定義が古い表を引き継がないように）
            if state.c_tags and any(R not in state.definitions for R in state.c_tags):
                state = replace(state, c_tags={R: v for R, v in state.c_tags.items() if R in state.definitions})
            live = {tr.scene.graph_id for tr in state.prototype.traces}
            if state.c_trace_tags and any(g not in live for g in state.c_trace_tags):
                state = replace(state, c_trace_tags={g: v for g, v in state.c_trace_tags.items() if g in live})
        if CFG.get("sme2017"):
            import smereplay
            smereplay.collective_phase("world", trial, state)
        b = CTX.pop("bundle", None)
        conn = CFG["conn"]
        recs = []
        deliver = []
        if conn is not None:
            present = (sorted({tg for tags in state.c_tags.values() for tg in tags} | set(state.c_trace_tags.values()))
                       if CFG["tags"] else [])
            _dbg("agent", CFG["agent"], "t", trial, "send trial msg", "bundle" if b else None)
            if serial is not None:
                serial.release()
            conn.send({"type": "trial", "t": trial, "bundle": _pub(b), "research": _res(b), "tags": present,
                       "defs": len(state.definitions)})
            msg = conn.recv()
            _dbg("agent", CFG["agent"], "t", trial, "got deliver", len(msg.get("deliver", [])))
            deliver = msg.get("deliver", [])
            if serial is not None:
                serial.acquire()
            order = list(range(len(deliver)))
            rng_for("order", CFG["wseed"], trial).shuffle(order)
            for k in order:
                STATS["recv"] += 1
                _dbg("agent", CFG["agent"], "t", trial, "receive", k)
                state, rec = receive_one(state, deliver[k], trial, CTX.get("config") or config)
                _dbg("agent", CFG["agent"], "t", trial, "received", k, rec.get("result"))
                rec["from"] = deliver[k]["sender"]
                recs.append(rec)
            _check_dictionary_guard(trial, "received")
            if CFG.get("sme2017"):
                smereplay.collective_phase("received", trial, state, deliveries=deliver)
            present = (sorted({tg for tags in state.c_tags.values() for tg in tags} | set(state.c_trace_tags.values()))
                       if CFG["tags"] else [])
            reply = {"type": "received", "t": trial, "records": recs, "tags": present, "defs": len(state.definitions)}
            if CFG.get("audit"):
                reply["audit"] = {"state": fingerprint(state),
                                  "rng": sha256(repr(state.rng_state).encode()).hexdigest()}
            if CFG.get("audit") and CFG.get("sme2017"):
                import smeshared
                # 全控えの指紋は試験の前後で照合する。毎試行は記憶・乱数と控えの件数を残す。
                reply["audit"]["sme_rng"] = fingerprint(smeshared.ENGINE.rng.getstate())
                reply["audit"]["sme_cache_counts"] = {
                    "matches": len(smeshared.ENGINE.cache), "self": len(smeshared.ENGINE.self_cache),
                    "results": len(smeshared.RESULTS), "graphs": len(smeshared.GRAPHS), "choices": len(smeshared.CHOICES)}
            if serial is not None:
                serial.release()
            conn.send(reply)
            while True:
                cmd = conn.recv()
                if cmd["type"] == "probe":
                    STATS["probes"] += 1
                    if serial is not None:
                        serial.acquire()
                    answers = probe(state, cmd["items"], CTX.get("config") or config)
                    if serial is not None:
                        serial.release()
                    conn.send({"type": "probe", "answers": answers})
                else:
                    break
            if serial is not None:
                serial.acquire()
        if CFG["tags"] and trial + 1 == CFG["T"]:
            # ★ 研究者用の最終名札回数表。記憶と費用は変えず、受け手には渡さない。
            STATS["name_tables_end"] = {R: {"born": d.registered_at, "tags": dict(state.c_tags.get(R, {}))}
                                        for R, d in sorted(state.definitions.items())}
        CTX["t"] = trial + 1
        return state, events

    REAL["theta_impl"] = apply


def graph_to_plain(g):
    return {"id": g.graph_id, "ents": [e.entity_id for e in g.entities],
            "rels": [[r.relation_id, r.predicate, list(r.arguments)] for r in g.relations]}


def plain_to_graph(x):
    from abm.domains import Entity, Relation, RelationGraph
    return RelationGraph(graph_id=x["id"], entities=tuple(Entity(e) for e in x["ents"]),
                         relations=tuple(Relation(i, p, tuple(a)) for i, p, a in x["rels"]))


def _pub(b):
    """受け手に渡すもの：付け直した束（素の値）・名札・送り手（宛先の決定に使う）。見た／予測／補った の区別・正誤・型は入れない。"""
    if b is None or b.get("empty") or not b.get("send"):
        return None
    return {"graph": graph_to_plain(b["graph"]), "tag": b["tag"], "sender": b["sender"], "to": b["to"]}


def _res(b):
    """研究者用の記録（受け手には渡さない）。"""
    if b is None:
        return None
    r = {k: v for k, v in b.items() if k != "graph"}
    if "graph" in b:
        r["bundle"] = b["graph"].graph_id
        r["relations"] = [[x.relation_id, x.predicate, list(x.arguments)] for x in b["graph"].relations]
    return r


# ---------------------------------------------------------------- まとめ役（個体のプロセスと歩調を合わせる）
def _agent_main(conn, task):
    import os
    import sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import v3_run
    task = dict(task)
    task["v311c"] = dict(task["v311c"], conn=conn)
    lock = task["v311c"].get("serial_lock")
    if lock is not None:
        lock.acquire()
    try:
        try:
            rec = v3_run.worker(task)
            message = {"type": "done", "rec": _jsonable({k: v for k, v in rec.items() if k != "v311c"} | {"v311c": rec.get("v311c")})}
        finally:
            if lock is not None:
                # 終了通知は大きく、個体番号順の読取りを待ち得る。計算と通知の準備だけを直列化する。
                # ここで一度だけ解放し、送信が詰まっても他の個体の計算を止めない。
                try:
                    lock.release()
                except ValueError:
                    pass
        conn.send(message)
    except BaseException as e:  # noqa
        import traceback
        tb = traceback.format_exc()
        print(tb, file=sys.stderr, flush=True)
        try:
            message = {"type": "error", "error": repr(e), "tb": tb}
            if isinstance(e, NotInDictionary):
                message["diagnostic"] = e.diagnostic
            conn.send(message)
        except BaseException:
            pass


def _jsonable(x):
    try:
        json.dumps(x)
        return x
    except TypeError:
        return json.loads(json.dumps(x, default=str))


def probe_items(seed_file, run, higher_order_second, per_motif=5):
    """回答の一致の試験：走行ごとに固定の試験の世界（種 900000＋走行）から、型ごとに最初の 5 試行（伏せる関係も固定）。計 20 件。"""
    from abm.seed import load_seed
    from abm.world import generate_world
    ws = generate_world(900000 + int(run), 400, ["agent"], seed=load_seed(seed_file), holdout_include_second_order=higher_order_second)
    items = []
    by = {}
    for tr in ws.trials:
        by.setdefault(tr.motif, [])
        if len(by[tr.motif]) < per_motif:
            by[tr.motif].append(tr)
    for motif in sorted(by):
        for tr in by[motif]:
            items.append({"scene": graph_to_plain(tr.target_graph_partial), "held": [tr.held_out_edge.predicate, list(tr.held_out_edge.arguments)],
                          "motif": motif, "trial": tr.trial})
    return items


def probe_shop_items(seed_file, run, higher_order_second, *, world, exc=0.2):
    """研究者用の固定1740場面。店×日ごとにドア3・その他2。不足なら停止し、抽選をやり直さない。"""
    import shopworld
    from abm.seed import load_seed
    from abm.world import generate_world
    seed = 900000 + int(run)
    ws = generate_world(seed, 1740, ["agent"], seed=load_seed(seed_file),
                        holdout_include_second_order=higher_order_second)
    buckets = {(typ, cue, door): [] for typ in ("甲", "乙") for cue in ("n", "e") for door in (True, False)}
    ids_before = dict(shopworld.IDS)
    try:
        for tr in ws.trials:
            cue = "e" if shopworld.cue_rng(seed, tr.trial).random() < exc else "n"
            built, info = shopworld.build(tr, seed, tr.trial, cue=cue, world=world)
            key = (info["shop_type"], cue, info["held_out_is_door"])
            need = 3 if key[2] else 2
            if len(buckets[key]) < need:
                buckets[key].append({"scene": graph_to_plain(built.target_graph_partial),
                                     "held": [built.held_out_edge.predicate, list(built.held_out_edge.arguments)],
                                     "motif": built.motif, "trial": built.trial,
                                     "shop_type": key[0], "shop_cue": cue, "held_out_is_door": key[2]})
    finally:
        shopworld.IDS.clear()
        shopworld.IDS.update(ids_before)
    missing = {str(k): len(v) for k, v in buckets.items() if len(v) != (3 if k[2] else 2)}
    if missing:
        raise ValueError(f"固定のお店の試験の世界で場面が不足（種 {seed}、1740場面）: {missing}")
    return [it for typ in ("甲", "乙") for cue in ("n", "e")
            for it in sorted(buckets[(typ, cue, True)] + buckets[(typ, cue, False)], key=lambda it: it["trial"])]


def coordinate(tasks, out_path, probe_every=100):
    """一つの集団の走行（tasks＝個体ごとの v3_run の仕事）。通信の記録を out_path（jsonl）に書き、要約を返す。
    まとめ役で失敗したら、個体のプロセスを止め、失敗を要約に書いて返す（待ち続けないように）。"""
    procs = []
    try:
        return _coordinate(tasks, out_path, probe_every, procs)
    except BaseException as e:  # noqa
        import traceback
        for p in procs:
            if p.is_alive():
                p.terminate()
        return {"errors": [{"coordinator": repr(e), "tb": traceback.format_exc()}], "trials": None}


def _coordinate(tasks, out_path, probe_every, procs_out):
    import multiprocessing as mp
    from pathlib import Path
    n = len(tasks)
    T = int(tasks[0]["cfg"]["trial_count"])
    ctx = mp.get_context("fork")
    if tasks[0]["v311c"].get("serial"):
        lock = ctx.BoundedSemaphore(1)
        tasks = [dict(t, v311c=dict(t["v311c"], serial_lock=lock)) for t in tasks]
    seed_file = str(Path(__file__).resolve().parent.parent / tasks[0]["cfg"]["seed_file"])
    shop = tasks[0]["v311c"].get("probe_shop")
    if shop:
        items = probe_shop_items(seed_file, tasks[0]["v311c"]["run"],
                                 bool(tasks[0]["cfg"]["fixed"].get("holdout_include_second_order")),
                                 world=tasks[0]["shop_world"], exc=tasks[0].get("shop_exc", 0.2))
    else:
        items = probe_items(seed_file, tasks[0]["v311c"]["run"], bool(tasks[0]["cfg"]["fixed"].get("holdout_include_second_order")))
    pipes = [ctx.Pipe() for _ in range(n)]
    procs = [ctx.Process(target=_agent_main, args=(pipes[i][1], tasks[i])) for i in range(n)]
    procs_out.extend(procs)
    for p in procs:
        p.start()
    conns = [pp[0] for pp in pipes]
    fo = open(out_path, "w", encoding="utf-8")
    if shop:
        fo.write(json.dumps({"kind": "probe_items", "seed": 900000 + tasks[0]["v311c"]["run"],
                             "corpus_trials": 1740, "items": items}, ensure_ascii=False) + "\n")
    audit_file = (open(str(out_path) + ".state.jsonl", "w", encoding="utf-8")
                  if tasks[0]["v311c"].get("audit") else None)
    summ = {"trials": 0, "bundles": 0, "sent": 0, "delivered": 0, "recv": {}, "probe": [], "tag_lost": 0, "errors": []}
    tags_prev: set = set()
    done = [None] * n
    for t in range(T):
        _dbg("coord t", t)
        msgs = []
        for i, c in enumerate(conns):
            m = c.recv()
            if m["type"] in ("error", "done"):
                summ["errors"].append({"agent": i, "t": t, "msg": m})
                done[i] = m
                msgs.append(None)
            else:
                msgs.append(m)
        if any(m is None for m in msgs):
            # ★ 失敗した個体があれば、ほかの個体を止める（待ち続けないように）。失敗は記録に残す
            for p in procs:
                if p.is_alive():
                    p.terminate()
            break
        deliver = [[] for _ in range(n)]
        for i, m in enumerate(msgs):
            if m["research"] is not None:
                summ["bundles"] += not m["research"].get("empty")
                fo.write(json.dumps({"kind": "bundle", "t": t, "agent": i, **m["research"]}, ensure_ascii=False, default=str) + "\n")
            b = m["bundle"]
            if b is not None:
                summ["sent"] += 1
                deliver[b["to"]].append(b)
        for i, c in enumerate(conns):
            summ["delivered"] += len(deliver[i])
            c.send({"deliver": deliver[i]})
        tags_now = set()
        for i, c in enumerate(conns):
            m = c.recv()
            if m["type"] in ("error", "done"):
                summ["errors"].append({"agent": i, "t": t, "phase": "received", "msg": m})
                done[i] = m
                for p in procs:
                    if p.is_alive():
                        p.terminate()
                break
            if audit_file is not None:
                audit_file.write(json.dumps({"t": t, "agent": i, **m["audit"]}) + "\n")
            for r in m["records"]:
                summ["recv"][r.get("result", "?")] = summ["recv"].get(r.get("result", "?"), 0) + 1
                fo.write(json.dumps({"kind": "recv", "t": t, "agent": i, **r}, ensure_ascii=False, default=str) + "\n")
            tags_now |= set(m["tags"])
        if summ["errors"]:
            break
        lost = sorted(tags_prev - tags_now)
        if lost:
            summ["tag_lost"] += len(lost)
            fo.write(json.dumps({"kind": "tag_lost", "t": t, "tags": lost}) + "\n")
        tags_prev = tags_now
        if probe_every and (t + 1) % probe_every == 0:
            answers = []
            for c in conns:
                c.send({"type": "probe", "items": items})
            for i, c in enumerate(conns):
                m = c.recv()
                if m["type"] in ("error", "done"):
                    summ["errors"].append({"agent": i, "t": t, "phase": "probe", "msg": m})
                    done[i] = m
                    for p in procs:
                        if p.is_alive():
                            p.terminate()
                    break
                answers.append(m["answers"])
            if summ["errors"]:
                break
            cats = {"双方正解": 0, "同じ誤答": 0, "双方棄権": 0, "その他": 0}
            for a in range(n):
                for b2 in range(a + 1, n):
                    for k, it in enumerate(items):
                        x, y = answers[a][k], answers[b2][k]
                        if x == it["held"] and y == it["held"]:
                            cats["双方正解"] += 1
                        elif x is None and y is None:
                            cats["双方棄権"] += 1
                        elif x is not None and x == y:
                            cats["同じ誤答"] += 1
                        else:
                            cats["その他"] += 1
            correct = [sum(1 for k, it in enumerate(items) if answers[a][k] == it["held"]) for a in range(n)]
            summ["probe"].append({"t": t, **cats, "正解の数（個体ごと）": correct})
            fo.write(json.dumps({"kind": "probe", "t": t, **cats, "answers": answers, "correct": correct}, ensure_ascii=False) + "\n")
        fo.flush()
        for c in conns:
            c.send({"type": "go"})
        summ["trials"] = t + 1
    for i, c in enumerate(conns):
        # ★ 先に終わった個体の知らせも取りこぼさない（プロセスが終わっていても、届いた知らせは読める）
        while done[i] is None:
            try:
                if c.poll(5):
                    m = c.recv()
                    if m.get("type") in ("done", "error"):
                        done[i] = m
                elif not procs[i].is_alive():
                    done[i] = {"type": "error", "error": "終わりの知らせが無いまま個体のプロセスが終わった"}
            except EOFError:
                done[i] = {"type": "error", "error": "EOF"}
    for p in procs:
        p.join()
    summ["agents"] = [d.get("rec") if d and d.get("type") == "done" else d for d in done]
    fo.write(json.dumps({"kind": "summary", **summ}, ensure_ascii=False, default=str) + "\n")
    fo.close()
    if audit_file is not None:
        audit_file.close()
    return summ

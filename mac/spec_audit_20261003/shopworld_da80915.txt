"""お店の世界（2026-10-01 未明の予約の委任書「手がかりの世界」の 1）：旗 --shop-world {1,2}・--shop-exc・--shop-keep-cue。
★ abm/ は変えない（abm.world.generate_trial を外側から包む。tools/worldvariant.py と同じ作り）。旗を切れば何もしない。
種ファイル：tools/shop/U-011_seed_shop.json（M1＝甲、M2＝乙。tools/shop/make_seed.py で作る）。

変更
  1 場面ごとに、シール（一引数の関係、述語 sig_n＝通常 又は sig_e＝例外、引数は物 a）と link（述語 attach、引数は（シールの ID, 一番上の関係の ID））
    の二本を、全部の場面の関係の後ろに足す。関係の ID は opaque_id(run_seed, 試行, "relation:shop:sig"／"relation:shop:link")。
    通常か例外かは、世界の乱数とは別の流れ（sha256(run_seed ‖ 試行 ‖ "shopcue")）から、確率 --shop-exc で例外にする。
    場面のほかの乱数（周縁・つなぎ・伏せ辺）の引き方は変えない。シールと link は伏せる候補に入らない（元の生成が伏せ辺を決めたあとに足すため）。
  2 ドア＝T1 の最初の一階の葉（経路 0.0.0、種 v3a2 で hold の位置）。述語を次の表で決める（X＝hold、Y＝hold_b）。
      世界 1：甲→X、乙→Y（シールによらない）。世界 2：甲・通常→X、甲・例外→Y、乙・通常→Y、乙・例外→X。
    伏せた関係がドアなら、その述語は表で決めたもの。関係の ID・引数・ほかの関係は変えない。
  3 研究者の側の記録：台帳の各試行に shop_type（甲／乙）・shop_cue（n／e）・door_pred（X／Y）・held_out_is_door を足す。エージェントには何も足さない。
  4 固定辞書（v3.9 の費用）に新しい述語 sig_n・sig_e・attach・hold_b を後ろから足す（extend_dictionary、v39.install のあと）。
    高階の述語の集合（abm.seed.higher_order_predicates）に attach を足す（他の関係を引数に取る位置の述語。仮の決定）。
  5 --shop-keep-cue（診断）：B の変換の候補（tools/v39.py の _candidates＝tools/v310be.py candidates）から、シールと link の席を外す。
    記憶の費用・E の同化・採点は変えない。シールと link の席は、関係 ID が研究者の側の登録（IDS）にあるかで見分ける。
  6 記録（side/<セル>/seed<種>.shop.jsonl、記録だけ）：シールと link の席の状態の変化（生まれた・F→H・H→U・U→H・定義ごと消えた）の試行、
    そのときの点数の内訳（変換の候補の V の分子と分母、R̄F・R̄H・R̄U・重み。その試行で候補に上がっていれば）、最後に採点された試行。
"""
from __future__ import annotations

import json
from dataclasses import replace
from hashlib import sha256
from random import Random

SIG_N, SIG_E, ATTACH, X, Y = "sig_n", "sig_e", "attach", "hold", "hold_b"
NEW_PREDICATES = (SIG_N, SIG_E, ATTACH, Y)
DOOR_PATH = "0.0.0"
TYPE = {"M1": "甲", "M2": "乙"}
INFO: dict = {}   # G_star.graph_id → 研究者の側の記録
IDS: dict = {}    # シール・link の関係 ID → "sig"／"link"
CFG: dict = {}
STATS: dict = {}
CTX: dict = {}


def door_rng(run_seed, trial_index) -> Random:
    """--shop-door-p の乱数（場面のほかの乱数と別の流れ）。"""
    return Random(int.from_bytes(sha256(f"{run_seed}\x1f{trial_index}\x1fshopdoor".encode("utf-8")).digest(), "big"))


def rehide(tr, run_seed, trial_index, p):
    """--shop-door-p p（2026-10-02 朝の委任書「C の格子」の段 1）：伏せ辺を選び直す。確率 p でドアを伏せ、それ以外は
    ドア以外の伏せる候補から一様に一本。乱数は door_rng（一回目 random() でドアか、ドアでなければ choice で一本）。
    伏せる候補（元の生成器 abm/world.py generate_trial の holdout_candidates と同じ集合・同じ並び）＝元の場面の一階の関係（引数がすべて物）
      のうち役割ユナリーを除いたもの：骨組みの一階・つなぎ（mediator）・周縁・のり（glue）。シールと link は元の生成のあとに足すので入らない。
      ★ 設定 hide1（二階を伏せない）を前提にする（二階を伏せる設定では使えない。install で止める）。
    並びは元の場面の関係の並び。見えている関係と見える物の作り方は abm/world.py と同じ。"""
    import abm.world as w
    from abm.domains import RelationGraph
    door_id = w.opaque_id(run_seed, trial_index, f"relation:tree:{DOOR_PATH}")
    ents = {e.entity_id for e in tr.G_star.entities}
    unary = w.opaque_id(run_seed, trial_index, "relation:role_unary")      # 役割ユナリーは元の生成器でも候補にしない（abm/world.py の B-5）
    cands = [r.relation_id for r in tr.G_star.relations if r.relation_id != unary and all(a in ents for a in r.arguments)]
    if door_id not in cands or tr.held_out_edge.relation_id not in cands:
        raise ValueError("--shop-door-p：ドアか元の伏せ辺が一階の候補に無い")
    rng = door_rng(run_seed, trial_index)
    held_id = door_id if rng.random() < p else rng.choice([c for c in cands if c != door_id])
    relations = tr.G_star.relations
    held = next(r for r in relations if r.relation_id == held_id)
    visible = tuple(r for r in relations if r.relation_id != held_id)
    ids = frozenset(r.relation_id for r in visible)
    reach = frozenset(a for r in visible for a in r.arguments if a not in ids and a in ents)
    partial = RelationGraph(graph_id=tr.G_star.graph_id, entities=tuple(e for e in tr.G_star.entities if e.entity_id in reach),
                            relations=visible)
    _bump("door_p_door", int(held_id == door_id))
    return replace(tr, target_graph_partial=partial, held_out_edge=held)


def cue_rng(run_seed, trial_index) -> Random:
    return Random(int.from_bytes(sha256(f"{run_seed}\x1f{trial_index}\x1fshopcue".encode("utf-8")).digest(), "big"))


def door_pred(world: int, typ: str, cue: str) -> str:
    if world == 1:
        return X if typ == "甲" else Y
    return X if (typ == "甲") == (cue == "n") else Y


def _bump(k, n=1):
    STATS[k] = STATS.get(k, 0) + n


def build(tr, run_seed, trial_index, *, cue, world):
    """元の場面 tr に、ドアの述語・シール・link を当てる（試験の場面を作るときにも使う）。"""
    import abm.world as w
    from abm.domains import Relation, RelationGraph
    typ = TYPE.get(tr.motif)
    if typ is None:
        raise ValueError(f"お店の世界に無い型 {tr.motif}（種ファイルは M1・M2 だけのものを使う）")
    door_id = w.opaque_id(run_seed, trial_index, f"relation:tree:{DOOR_PATH}")
    root_id = w.opaque_id(run_seed, trial_index, "relation:tree:root")
    a_id = w.opaque_id(run_seed, trial_index, "entity:a")
    by_id = {r.relation_id: r for r in tr.G_star.relations}
    if door_id not in by_id or by_id[door_id].predicate != X or root_id not in by_id:
        raise ValueError("ドア（経路 0.0.0 の hold）か一番上の関係が場面に無い")
    dp = door_pred(world, typ, cue)
    sig_id = w.opaque_id(run_seed, trial_index, "relation:shop:sig")
    link_id = w.opaque_id(run_seed, trial_index, "relation:shop:link")
    rels = [Relation(r.relation_id, dp, r.arguments, r.attributes) if r.relation_id == door_id else r for r in tr.G_star.relations]
    rels += [Relation(sig_id, SIG_E if cue == "e" else SIG_N, (a_id,)), Relation(link_id, ATTACH, (sig_id, root_id))]
    held_id = tr.held_out_edge.relation_id
    held = next(r for r in rels if r.relation_id == held_id)
    graph = RelationGraph(graph_id=tr.G_star.graph_id, entities=tr.G_star.entities, relations=tuple(rels))
    visible = tuple(r for r in rels if r.relation_id != held_id)
    if tuple(r.relation_id for r in visible[:-2]) != tuple(r.relation_id for r in tr.target_graph_partial.relations):
        raise ValueError("見えている関係の並びが元の世界と違う")
    ids = frozenset(r.relation_id for r in visible)
    ents = {e.entity_id for e in graph.entities}
    reach = frozenset(x for r in visible for x in r.arguments if x not in ids and x in ents)
    partial = RelationGraph(graph_id=tr.target_graph_partial.graph_id, entities=tuple(e for e in graph.entities if e.entity_id in reach),
                            relations=visible)
    IDS[sig_id] = "sig"
    IDS[link_id] = "link"
    info = {"shop_type": typ, "shop_cue": cue, "door_pred": "X" if dp == X else "Y", "held_out_is_door": held_id == door_id,
            "door_id": door_id, "sig_id": sig_id, "link_id": link_id, "root_id": root_id}
    return replace(tr, G_star=graph, target_graph_partial=partial, held_out_edge=held), info


def shop_trial(original, run_seed, trial_index, agent_ids, *, seed, holdout_include_second_order=False):
    tr = original(run_seed, trial_index, agent_ids, seed=seed, holdout_include_second_order=holdout_include_second_order)
    if CFG.get("door_p") is not None:
        tr = rehide(tr, run_seed, trial_index, CFG["door_p"])
    cue = "e" if cue_rng(run_seed, trial_index).random() < CFG["exc"] else "n"
    out, info = build(tr, run_seed, trial_index, cue=cue, world=CFG["world"])
    INFO[out.G_star.graph_id] = info
    _bump("trials")
    _bump(f"{info['shop_type']}_{cue}")
    _bump("held_out_is_door", int(info["held_out_is_door"]))
    return out


def _seat_states(state):
    import v39
    out = {}
    for d in state.definitions.values():
        for row in d.constituents:
            k = IDS.get(row.relation.relation_id)
            if k is not None:
                out[(d.name, d.registered_at, row.slot_index)] = (k, v39.seat_state(d, row, state.slot_history))
    return out


def install(fo, *, world: int, exc: float, keep_cue: bool, side_path: str, door_p=None) -> None:
    """tools/v3_run.py の worker で、v39・v310be・U の旗・同点の並べ方のあと、世界を作る前に入れる。"""
    import abm.ledger as ledger
    import abm.loop as loop
    import abm.seed as seedmod
    import abm.world as w
    INFO.clear()
    IDS.clear()
    STATS.clear()
    CTX.clear()
    CFG.clear()
    CFG.update(world=int(world), exc=float(exc), keep_cue=bool(keep_cue), door_p=(None if door_p is None else float(door_p)))
    CTX.update(f=open(side_path, "w", encoding="utf-8"), prev={}, cand={}, scored={})
    original = w.generate_trial
    CTX["orig_gen"] = original

    def generate_trial(run_seed, trial_index, agent_ids, *, seed, holdout_include_second_order=False):
        return shop_trial(original, run_seed, trial_index, agent_ids, seed=seed, holdout_include_second_order=holdout_include_second_order)

    w.generate_trial = generate_trial

    real_hop = seedmod.higher_order_predicates

    def higher_order_predicates(seed):
        return frozenset(real_hop(seed)) | {ATTACH}

    seedmod.higher_order_predicates = higher_order_predicates
    import sweep
    if getattr(sweep, "higher_order_predicates", None) is real_hop:
        sweep.higher_order_predicates = higher_order_predicates

    # 台帳の各試行に研究者用の四欄を足す（tools/worldvariant.py と同じ作り）。あわせてシール・link の席の状態の変化を side に書く
    real_record = loop._ledger_record

    def _ledger_record(agent_id, trial, *a, **k):
        rec, snap, h = real_record(agent_id, trial, *a, **k)
        info = INFO.get(trial.G_star.graph_id) or {}
        rec = dict(rec)
        for key in ("shop_type", "shop_cue", "door_pred", "held_out_is_door"):
            rec[key] = info.get(key)
        after = a[4]
        now = _seat_states(after)
        prev = CTX["prev"]
        t = trial.trial
        for key, (kind, st) in now.items():
            old = prev.get(key, (kind, None))[1]
            if old != st:
                _write({"kind": "shop_seat", "trial": t, "R": key[0], "reg": key[1], "slot": key[2], "which": kind,
                        "from": old or "生まれた", "to": st, "cand": CTX["cand"].get((key[0], key[2], t)),
                        "last_scored": CTX["scored"].get((key[0], key[2]))})
        for key, (kind, st) in prev.items():
            if key not in now:
                _write({"kind": "shop_seat", "trial": t, "R": key[0], "reg": key[1], "slot": key[2], "which": kind,
                        "from": st, "to": "定義ごと消えた", "last_scored": CTX["scored"].get((key[0], key[2]))})
        CTX["prev"] = now
        CTX["cand"] = {}
        return rec, snap, h

    loop._ledger_record = _ledger_record

    real_append = ledger.Ledger.append
    extra_keys = ("shop_type", "shop_cue", "door_pred", "held_out_is_door")

    def append(self, record):
        extra = {k: record[k] for k in extra_keys if k in record}
        base = {k: v for k, v in record.items() if k not in extra}
        if not extra:
            return real_append(self, base)
        keys = frozenset(base)
        expected = frozenset(ledger.LEDGER_FIELDS)
        if keys != expected:
            raise ValueError(f"台帳欄が不一致: missing={sorted(expected - keys)}, extra={sorted(keys - expected)}")
        null_fields = sorted(f for f in ledger.NON_NULL_FIELDS if base[f] is None)
        if null_fields:
            raise ValueError(f"毎試行 non-null 欄が null: {null_fields}")
        self._write_line({"record_type": "trial", **base, **extra})

    ledger.Ledger.append = append

    # B の変換の候補：シール・link の席の点数の内訳を控える。--shop-keep-cue なら候補から外す
    import v39
    real_cands = v39._candidates

    def _candidates(state, d, t, L, n_defs):
        out = real_cands(state, d, t, L, n_defs)
        rows = {row.slot_index: row.relation.relation_id for row in d.constituents}
        keep = []
        for c in out:
            V, kind, R, slot, dc, means = c
            if rows.get(slot) in IDS:
                RF, RH, RU, n = means
                CTX["cand"][(R, slot, t)] = {"V": V, "kind": kind, "num": (RH - RF) if kind == "FH" else (RU - RH), "den": dc,
                                             "RF": RF, "RH": RH, "RU": RU, "n": n}
                if CFG["keep_cue"]:
                    _bump("keep_cue_dropped")
                    continue
            keep.append(c)
        return keep

    v39._candidates = _candidates

    # 最後に採点された試行（席は定義の名前と席番号で。採点のときにその名前の定義は一つだけ）
    real_score = v39.score_answers

    def score_answers(seats_in, ans, received, t):
        out, scored = real_score(seats_in, ans, received, t)
        for x in scored:
            CTX["scored"][(ans["R"], x[0])] = t
        return out, scored

    v39.score_answers = score_answers


SHARED_PATHS = ("0.0.1", "0.1.0", "0.1.1")   # T1 のドア以外の一階の葉（種 v3a2 で push・carry・lift）


def add_probes(pst, *, run_seed, agent_ids, holdout_second) -> None:
    """--probe-world の試験に、お店の世界の試験を足す（tools/probeworld.py の install のあとで呼ぶ）。
    試験の場面の元：probeworld と同じ流れ（"probe‖run_seed"）で、型ごとに最初の試行の元の場面（シールを足す前）を作る。
    対になった試験：甲・乙それぞれ、元の場面にシール通常／例外を当てた二場面で、ドアを伏せる（ほかの見えている関係はまったく同じ）。
    共有部分の試験：甲・乙 × 通常・例外の四場面で、T1 のドア以外の一階の葉を一本ずつ伏せる（三本。仮の決定）。"""
    import abm.world as w
    import probeworld as pw
    sd = pst["sd"]
    motifs = tuple(sd.data["motif_structure"])
    prs = f"probe\x1f{run_seed}"
    snap = pw._snapshot_modules()
    base = {}
    i = 0
    while len(base) < len(motifs) and i < 10000:
        m = w._motif_for_trial(prs, i, motifs)
        if m not in base:
            base[m] = CTX["orig_gen"](prs, i, agent_ids, seed=sd, holdout_include_second_order=holdout_second)
        i += 1
    pw._restore_modules(snap)
    n0 = len(pst["probes"])
    for m in motifs:
        tr0 = base[m]
        info, _ = pw._paths(sd.data, prs, tr0.trial, m)
        for cue in ("n", "e"):
            tr, si = build(tr0, prs, tr0.trial, cue=cue, world=CFG["world"])
            by_id = {r.relation_id: r for r in tr.G_star.relations}
            facts = {(r.predicate, tuple(r.arguments)) for r in tr.G_star.relations}
            for kind, paths in (("対", (DOOR_PATH,)), ("共有", SHARED_PATHS)):
                for p in paths:
                    hid, lvl, _pred, par = info[p]
                    pst["probes"].append({"motif": m, "path": p, "level": lvl, "truth": by_id[hid].predicate,
                                          "role": [(info[pp][2], k) for pp, k in par], "hid": hid, "G": tr.G_star,
                                          "partial": pw._partial(tr.G_star, hid), "facts": facts,
                                          "extra": {"shop_probe": kind, "shop_type": si["shop_type"], "shop_cue": cue,
                                                    "door_pred": si["door_pred"]}})
    STATS["probes_added"] = len(pst["probes"]) - n0


def _write(rec):
    f = CTX.get("f")
    if f is not None:
        f.write(json.dumps(rec, ensure_ascii=False, default=str) + "\n")


def extend_dictionary() -> None:
    """v3.9 の費用の固定辞書に、新しい述語を後ろから足す（v39.install のあとで呼ぶ。tools/worldvariant.py と同じ）。"""
    import v39
    if not v39.CFG.get("dict_index"):
        return
    idx = dict(v39.CFG["dict_index"])
    for p in NEW_PREDICATES:
        if p not in idx:
            idx[p] = len(idx)
    v39.CFG["dict_index"] = idx
    v39.CFG["D"] = len(idx)


def close() -> dict:
    f = CTX.get("f")
    if f is not None:
        f.close()
    return dict(STATS)

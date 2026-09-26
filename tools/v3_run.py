"""委任書 2026-09-25「v3（仕様に沿わせた模型）の組み立てと小さな試し」の走行ドライバ。
★ tools/ 版（2026-09-25 午後）。analysis_v3_2026-09-25/v3_run.py（md5 7e1e1c9f…）を写し、--lowmem と --compare-to を足した。
★ nohash_run.py（2026-09-24、md5 334915ef…）を写して足した。abm/・sweep.py・runs/ は変えない（外側のドライバ）。
★ 旗と設定（すべて既定は v2 のまま）
   --nohash       名前の一致の経路を使わない（nohash_run.py と同じ包み方）
   --nsim X       同定の基準 nsim_threshold を X にする（既定は config の 0.95）
   --vt X         逐語の枚の閾値 verbatim_theta を X にする（既定は無し＝θ′ に落ちる）
   --extend-rule R  v3.1 の取り込み（tools/v31.py）：v2（今のまま、既定）／profit（v3.1a、Σ(V−θ′) が増える限り一本ずつ足す）／none（v3.1b、足さない）
   --charge1 C      v3.1 の ① の罰（tools/v31.py）：v2（今のまま、既定）／d32（投影は予測した行だけ・穴埋めは slot_history を一つ減らす）
   --dump-slot-history  走行末の全定義の slot_history（墓石の席も含む）と行を side の最後の行に書く（v3.1-slotdump。記録だけ）
   --ident-rho ρ  旗A（二つ目の実験、2026-09-26）両側で測る：比 ＝ 点(定義,相手) ÷（点(定義,定義) ＋ ρ × 相手の側だけの点）。tools/v32.py
   --ident-argmax 旗B 候補すべての比を出し、一番高い定義が基準に届けば同化・届かなければ誕生（同点は今の走査順）。tools/v32.py
   --ident-commons 旗C 照らす相手を、土台と今の場面で一致した構造（案 C1）にする。tools/v32.py
   --ident-shadow 確かめ：元の同定も毎回呼んで比べる（旗A・B・C・直し② が切れていれば、違えば止める）
   --proj-first   穴埋めの同点で投影を捨てない（2026-09-26 夜）：投影が一本出ていれば、穴埋めが同点でも投影を使う。tools/projfirst.py
   --fix-order    名前の順番の直し（2026-09-26 夜）：親の中身として一緒に対になった子も、述語が一致していれば、
                  自分の番で対にしたのと同じ点を数える。map_graphs を差し替え、使っている所すべてに効く。tools/fixorder.py
   --rename-check 確かめ：同定のたびに述語の名前を付け替えて（二通り）判断をやり直し、違った回を数える（記録だけ）
   --fix2         直し②（2026-09-26 夕）：墓石を子に持つ高階の行を、墓石の席の slot_history で照らす。
                  見えている子は、その述語が席の履歴に回数 1 以上なら当てはまる。伏せられた子は「見えていない枠」。
                  同定と、話すときの支持（定義の選び方・τ の門）にだけ効く。tools/fix2.py
   --lowmem       状態の正準形の控えを、前の試行で触った物だけに絞る（tools/lowmem.py）。★ 2026-09-25 から既定。
                  7 本で台帳が一字一句同じと確かめた。外すときは --no-lowmem
   --compare-to D 指定した走行根の同じ台帳と、全試行の指紋・台帳全体を比べる（旗の組み合わせによらず）
   --fast         台帳の記録を速くする（tools/fastledger.py。lowmem の控え方を含む）。★ 台帳は一字一句同じ（2026-09-26、
                  v3.1a・v3.1b・v3 の各 1 本で、展開した台帳の sha256 が旗なしと一致することを確かめた）
   --no-public-history  public_history を状態から外す（tools/nohist.py）。★ 指紋と state_snapshot が変わるので、
                  今までの台帳と一字一句を比べる確かめでは付けない（本番の走行だけで使う）。
                  外した版の指紋は「外す前の状態から public_history の欄を除いたもの」の指紋と全試行で一致する（2026-09-26）
   --greedy       生まれ方：共通構造の全体から、外すと儲けの合計 Σ(V−θ′) が一番増える行を一本ずつ外す（2026-09-25 決定）
   --extgreedy    比べ：取り込み（空いた位置への足し込み）で、儲けの合計が増える限り一本ずつ足す
★ 全部オフ（--nohash なし・--nsim なし・--vt なし・--greedy なし）のときだけ、既存の台帳（runs/）と全試行の指紋を比べ、
   一致しなければ止める。
★ 台帳ごとの最大メモリ：一台帳ごとに新しいプロセスで走らせ（max_tasks_per_child=1）、終わりに ru_maxrss を記録する。
★ 記録（side/）：登録（誕生・同化）ごとに、試行・R・経路・改名元・土台の枚の番号（base_written_at）を書く。
使い方
  python3.12 v3_run.py <config.json> <出力の根> [--nohash] [--nsim X] [--vt X] [--workers N] [--seeds 1,2] [--cells v2のセル名,...]
"""
from __future__ import annotations

import argparse
import copy
import gzip
import hashlib
import json
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Mapping

ROOT = Path(__file__).resolve().parent.parent   # ★ v3.1：置き場所から決める（worktree・クラウドでも同じ）
sys.path.insert(0, str(ROOT))

_REAL = {}
_LAST_ALIVE: dict = {}
_LAST_STATE: dict = {}   # ★ --dump-slot-history：各試行の削除の後の状態を指すだけ（写しは作らない。台帳には何も書かない）
_STATS: dict = {}

EPS = 1e-9


def _pool_pairs(base, target, alignment):
    """m1 と同じ手順（abstraction.py:74-85）で、構造の対で述語が一致するものを並び順どおりに返す。"""
    from abm.abstraction import _structural_relation_ids
    base_by_id = {r.relation_id: r for r in base.relations}
    target_by_id = {r.relation_id: r for r in target.relations}
    raw = [(base_by_id[l], target_by_id[r]) for l, r in sorted(alignment.relation_mapping.items())
           if l in base_by_id and r in target_by_id]
    sids = _structural_relation_ids(base)
    return [p for p in raw if p[0].relation_id in sids and p[0].predicate == p[1].predicate]


def _v0(relation, scope, p_hat, pricing_rule, predicate_of=None):
    """生まれた直後の V ＝ 1 ＋ c/ℓ（参加率 1・例外 0・w＝0。accounting.py:42-51・:201-235 に当てはめた値）。"""
    from abm.abstraction import _new_slot_count
    ns = _new_slot_count(relation, tuple(scope), pricing_rule=pricing_rule, predicate_of=predicate_of)
    c = 1 + 3 * len(relation.arguments) - 3 * ns
    ell = p_hat.code_length(relation.predicate)
    return (ell + c) / ell


def _profit(rels, p_hat, pricing_rule, theta, predicate_of=None, scope_extra=()):
    scope = tuple(rels) + tuple(scope_extra)
    return sum(_v0(r, scope, p_hat, pricing_rule, predicate_of) - theta for r in rels)


def _closure(q, S):
    """q を外すとき、q（や外れる行）を引数に持つ高階の行も一緒に外す（2026-09-25 決定 Q5）。"""
    out = {q.relation_id}
    changed = True
    while changed:
        changed = False
        for r in S:
            if r.relation_id not in out and any(a in out for a in r.arguments):
                out.add(r.relation_id); changed = True
    return out


def _conn(q, S):
    """組の中で、q と引数を一つ以上共有する他の行の数（つながり）。"""
    qa = set(q.arguments)
    return sum(1 for r in S if r.relation_id != q.relation_id and qa & set(r.arguments))


def _drop_childless(S, base_ids):
    """子（土台の関係 ID の引数）が組に無い高階の行を外す（繰り返し）。"""
    S = list(S); dropped = 0
    while True:
        ids = {r.relation_id for r in S}
        bad = [r for r in S if any(a in base_ids and a not in ids for a in r.arguments)]
        if not bad:
            return S, dropped
        dropped += len(bad)
        bad_ids = {r.relation_id for r in bad}
        S = [r for r in S if r.relation_id not in bad_ids]


def prune_birth(pool_lefts, base, p_hat, pricing_rule, theta):
    """2026-09-25 の決定：共通構造の全体から、外すと儲けの合計（Σ(V−θ′)）が一番増える行を一本ずつ外す。"""
    base_ids = {r.relation_id for r in base.relations}
    S, dropped0 = _drop_childless(pool_lefts, base_ids)
    info = {"pool": len(pool_lefts), "childless_dropped_at_start": dropped0, "steps": 0,
            "tie_group": 0, "tie_weak": 0, "tie_unresolved": 0}
    G = _profit(S, p_hat, pricing_rule, theta)
    info["profit_start"] = G
    while S:
        cands = []
        for q in S:
            R = _closure(q, S)
            S2 = [r for r in S if r.relation_id not in R]
            cands.append((_profit(S2, p_hat, pricing_rule, theta), q, R))
        best = max(g for g, _, _ in cands)
        if not best > G + EPS:
            break
        tied = [c for c in cands if abs(c[0] - best) <= EPS]
        if len(tied) == 1:
            R = tied[0][2]
        else:
            U = set().union(*(c[2] for c in tied))
            SU = [r for r in S if r.relation_id not in U]
            if _profit(SU, p_hat, pricing_rule, theta) > G + EPS:
                R = U; info["tie_group"] += 1
            else:
                m = min(_conn(c[1], S) for c in tied)
                weak = [c for c in tied if _conn(c[1], S) == m]
                if len(weak) == 1:
                    R = weak[0][2]; info["tie_weak"] += 1
                else:
                    info["tie_unresolved"] += 1   # ★ 決めていない同点。止める（記録して報告する）
                    break
        S = [r for r in S if r.relation_id not in R]
        info["steps"] += 1
        G = _profit(S, p_hat, pricing_rule, theta)
    info["final"] = len(S); info["profit_end"] = G if S else 0.0
    return S, info


def greedy_extend(old, pool, base, p_hat, pricing_rule, theta):
    """比べの版（Q4）：取り込みで、儲けの合計が増える限り一本ずつ足す。★ 容量は空いた位置の数（案イ′）。"""
    live = [row.relation for row in old.constituents if row.alive]
    live_preds = {r.predicate for r in live}
    additions = [l for l, _ in pool if l.predicate not in live_preds]
    occupied = {row.slot_index for row in old.constituents if row.alive}
    cap = len({row.slot_index for row in old.constituents if not row.alive and row.slot_index not in occupied})
    predicate_of = {item.relation_id: item.predicate for item in base.relations}
    base_ids = set(predicate_of)
    info = {"additions": len(additions), "capacity": cap, "tie_group": 0, "tie_strong": 0, "tie_unresolved": 0}

    def ok(c, A):
        ids = {a.relation_id for a in A} | {c.relation_id}
        return all(not (a in base_ids) or a in ids or predicate_of.get(a) in live_preds for a in c.arguments)

    def gain(A):
        return _profit(A, p_hat, pricing_rule, theta, predicate_of, scope_extra=live)

    A = []; G = 0.0
    while len(A) < cap:
        cands = [(gain(A + [c]), c) for c in additions if c not in A and ok(c, A)]
        if not cands:
            break
        best = max(g for g, _ in cands)
        if not best > G + EPS:
            break
        tied = [c for g, c in cands if abs(g - best) <= EPS]
        if len(tied) == 1:
            A.append(tied[0])
        elif len(A) + len(tied) <= cap and gain(A + tied) > G + EPS and all(ok(c, A + tied) for c in tied):
            A.extend(tied); info["tie_group"] += 1
        else:
            m = max(_conn(c, A + live + [c]) for c in tied)
            strong = [c for c in tied if _conn(c, A + live + [c]) == m]
            if len(strong) == 1:
                A.append(strong[0]); info["tie_strong"] += 1
            else:
                info["tie_unresolved"] += 1
                break
        G = gain(A)
    info["chosen"] = len(A)
    return [l for l, _ in pool if l in A or l.predicate in live_preds], info


def _restrict(alignment, keep_ids):
    from dataclasses import replace
    return replace(alignment, relation_mapping={k: v for k, v in alignment.relation_mapping.items() if k in keep_ids})


def _install(side_path: Path, nohash: bool, prune: bool = False, extgreedy: bool = False, theta: float = 0.0):
    import abm.loop as loop
    from abm.abstraction import _definition_name, _structural_relation_ids

    real_m1 = _REAL.setdefault("m1", loop.m1)
    real_theta = _REAL.setdefault("theta", loop.apply_theta)
    fo = open(side_path, "w", encoding="utf-8")
    _LAST_ALIVE.clear()
    _STATS.clear()
    _STATS.update(removed=0)

    def hash_name(state, base, target, alignment):
        # ★ abm/abstraction.py:74-88 と同じ手順（対の作り方・構造の絞り・述語一致）で名前だけ作る。
        base_by_id = {r.relation_id: r for r in base.relations}
        target_by_id = {r.relation_id: r for r in target.relations}
        raw = [(base_by_id[l], target_by_id[r]) for l, r in sorted(alignment.relation_mapping.items())
               if l in base_by_id and r in target_by_id]
        sids = _structural_relation_ids(base)
        pairs = [p for p in raw if p[0].relation_id in sids and p[0].predicate == p[1].predicate]
        return _definition_name(pairs) if len(pairs) >= 2 else None

    def wrapped(state, base, target, alignment, trial, **kw):
        name = kw.get("name")
        v32m = sys.modules.get("v32")
        if v32m is not None and v32m.STATS.get("commons") and v32m.STATS.get("shadow"):
            # ★ 確かめ（旗C ＋ shadow のときだけ）：同定に使った共通構造の行 ＝ m1 の対の今の場面の側の行（2 行以上のとき）。誕生の削りより前で見る
            pool_ids = frozenset(t.relation_id for _, t in _pool_pairs(base, target, alignment))
            if len(pool_ids) >= 2 and pool_ids != v32m.LAST.get("commons_ids"):
                raise RuntimeError(f"共通構造が m1 の対と食い違う 試行 {trial}")
            v32m.STATS["commons_checked"] = v32m.STATS.get("commons_checked", 0) + (len(pool_ids) >= 2)
        if "v31" in sys.modules:
            sys.modules["v31"].CFG["target"] = target   # ★ v3.1a の席の照合に使う（今の場面）
        renamed_from = None
        sel = None
        if prune and name is None:
            pool = _pool_pairs(base, target, alignment)
            if len(pool) >= 2:
                chosen, sel = prune_birth([l for l, _ in pool], base, state.p_hat, kw.get("pricing_rule", "legacy"), theta)
                sel["kind"] = "prune"; sel["trial"] = trial
                if len(chosen) < 2:
                    fo.write(json.dumps({**sel, "result": "none"}) + "\n")
                    return state, None
                alignment = _restrict(alignment, {r.relation_id for r in chosen})
        elif extgreedy and name is not None and name in state.definitions:
            pool = _pool_pairs(base, target, alignment)
            if len(pool) >= 2:
                keep, sel = greedy_extend(state.definitions[name], pool, base, state.p_hat, kw.get("pricing_rule", "legacy"), theta)
                sel["kind"] = "extgreedy"; sel["trial"] = trial; sel["R"] = name
                if len(keep) < 2:
                    sel["fallback_lt2"] = True   # ★ 絞ると 2 本未満になり m1 が何もしない（v2 なら同化していた）
                alignment = _restrict(alignment, {l.relation_id for l in keep})
        hn = hash_name(state, base, target, alignment) if name is None else None
        if nohash and name is None:
            if hn is not None and hn in state.definitions:
                new = f"{hn}_t{trial}"
                if new in state.definitions:
                    raise RuntimeError(f"改名先 {new} が既にある")
                kw = dict(kw, name=new)
                renamed_from = hn
        out_state, reg = real_m1(state, base, target, alignment, trial, **kw)
        if sel is not None:
            fo.write(json.dumps({**sel, "result": "registered" if reg is not None else "noop",
                                 "R_out": reg["R"] if reg else None}) + "\n")
        if name is None and renamed_from is None and reg is not None and reg["R"] != hn:
            # ★ 名前の作り方を m1 と同じに写せているかの検算（旗オフでも毎回）
            raise RuntimeError(f"ハッシュ名の写しが m1 と食い違う {hn} != {reg['R']}")
        if renamed_from is not None and reg is not None:
            if reg["was_extension"]:
                raise RuntimeError("改名したのに既存へ入った")
            reg["name_source"] = "hash"
            reg["renamed_from"] = renamed_from
        if reg is None:
            fo.write(json.dumps({"kind": "nsim_noop" if name is not None else "hash_noop", "trial": trial}) + "\n")
        else:
            fo.write(json.dumps({"kind": "assim" if reg["was_extension"] else "birth", "trial": trial,
                                 "R": reg["R"], "route": reg["name_source"],
                                 "renamed_from": renamed_from,
                                 "base_written_at": kw.get("base_written_at"),
                                 "m_alloc": reg.get("m_alloc"), "m_live": reg.get("m_live")}) + "\n")
        return out_state, reg

    def theta_wrapped(state, *a, **kw):
        after, events = real_theta(state, *a, **kw)
        _STATS["removed"] += sum(1 for R in state.definitions if R not in after.definitions)
        for R, d in after.definitions.items():
            if d.m_live > 0:
                _LAST_ALIVE[R] = sorted(row.relation.predicate for row in d.constituents if row.alive)
        _LAST_ALIVE["__alive__"] = sorted(R for R, d in after.definitions.items() if d.m_live > 0)
        _LAST_STATE["state"] = after
        return after, events

    loop.m1 = wrapped
    loop.apply_theta = theta_wrapped
    return fo


def worker(task: dict) -> dict:
    import sweep
    out_root = Path(task["out_root"])
    side_dir = out_root / "side" / task["cell"]
    side_dir.mkdir(parents=True, exist_ok=True)
    fo = _install(side_dir / f"seed{task['seed']:03d}.jsonl", task["nohash"],
                  task.get("prune", False), task.get("extgreedy", False), float(task["theta_prime"]))
    if task.get("nohist"):
        # ★ 2026-09-26 の試し：public_history を状態から外す（tools/nohist.py）。lowmem・fast より先に入れる。
        sys.path.insert(0, str(ROOT / "tools"))
        import nohist
        nohist.install()
    if task.get("fast"):
        # ★ 2026-09-26 の試し：台帳の記録を速くする書き直し（tools/fastledger.py）。lowmem の控え方を含むので、lowmem の代わりに入れる。
        sys.path.insert(0, str(ROOT / "tools"))
        import fastledger
        fastledger.install()
    elif task.get("lowmem"):
        sys.path.insert(0, str(ROOT / "tools"))
        import lowmem
        lowmem.install()
    if task.get("extend_rule", "v2") != "v2" or task.get("charge1", "v2") != "v2":
        sys.path.insert(0, str(ROOT / "tools"))
        import v31
        fx = task["cfg"]["fixed"]
        v31.install(task.get("extend_rule", "v2"), task.get("charge1", "v2"), float(task["theta_prime"]),
                    float(fx.get("w", 0.0)), float(fx.get("kappa", 1.0)), float(fx.get("beta", 0.0)), fo=fo)
    if task.get("proj_first"):
        # ★ 穴埋めの同点で投影を捨てない（2026-09-26 夜）：tools/projfirst.py
        sys.path.insert(0, str(ROOT / "tools"))
        import projfirst
        projfirst.install()
    if task.get("fix_order"):
        # ★ 名前の順番の直し（2026-09-26 夜）：map_graphs を差し替える（tools/fixorder.py）。ほかの差し替えより先に入れる。
        sys.path.insert(0, str(ROOT / "tools"))
        import fixorder
        fixorder.install()
    if task.get("fix2"):
        # ★ 直し②（2026-09-26 夕）：墓石を子に持つ高階の行の照らし方（tools/fix2.py）。話すときの支持はここで差し替え、
        #   同定の側は tools/v32.py の同定の中で使う（下で v32 を必ず入れる）。
        sys.path.insert(0, str(ROOT / "tools"))
        import fix2
        fix2.install()
    if (task.get("ident_rho") is not None or task.get("ident_argmax") or task.get("ident_commons")
            or task.get("ident_shadow") or task.get("fix2") or task.get("rename_check")):
        # ★ 二つ目の実験（2026-09-26）：同化先の決め方の旗 A・B・C（tools/v32.py）
        sys.path.insert(0, str(ROOT / "tools"))
        import v32
        v32.install(task.get("ident_rho"), bool(task.get("ident_argmax")), bool(task.get("ident_shadow")),
                    bool(task.get("ident_commons")), bool(task.get("fix2")), bool(task.get("rename_check")))
    rec = sweep.run_one(task)
    if "v32" in sys.modules:
        rec["v32"] = dict(sys.modules["v32"].STATS)
    if "fix2" in sys.modules:
        rec["fix2"] = dict(sys.modules["fix2"].STATS)
    if "fixorder" in sys.modules:
        rec["fixorder"] = dict(sys.modules["fixorder"].STATS)
    if "projfirst" in sys.modules:
        rec["projfirst"] = dict(sys.modules["projfirst"].STATS)
    if "v31" in sys.modules:
        rec["v31"] = dict(sys.modules["v31"].STATS)
    if task.get("fast"):
        rec["fast"] = {"evictions": fastledger.STATE["evictions"], "max_cache": fastledger.STATE["max_cache"]}
    elif task.get("lowmem"):
        rec["lowmem"] = {"evictions": lowmem.STATE["evictions"], "max_cache": lowmem.STATE["max_cache"]}
    rec["nohist"] = bool(task.get("nohist"))
    import resource
    rec["peak_rss_mb"] = round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1e6, 1)  # macOS はバイト
    alive_end = _LAST_ALIVE.pop("__alive__", [])
    final = {"kind": "final", "alive_end": alive_end, "removed_defs": _STATS["removed"],
             "last_alive_preds": _LAST_ALIVE}
    if task.get("dump_slot_history"):
        # ★ v3.1-slotdump（2026-09-26）：走行末の全定義の slot_history（墓石の席も含む）と、各定義の行（位置・登録試行・述語・生死）を
        #   side の最後の行に書く。記録だけ。台帳（ledgers/）には何も書かない。
        st_end = _LAST_STATE.get("state")
        sh = {}
        cons = {}
        if st_end is not None:
            for (R, slot), val in st_end.slot_history.items():
                sh.setdefault(R, {})[str(slot)] = (dict(sorted(val.items())) if isinstance(val, Mapping)
                                                   else sorted(val))
            for R, d in st_end.definitions.items():
                cons[R] = [[row.slot_index, row.registered_at, row.relation.predicate, bool(row.alive)]
                           for row in d.constituents]
        final["slot_history_end"] = sh
        final["constituents_end"] = cons
    fo.write(json.dumps(final, ensure_ascii=False) + "\n")
    fo.close()
    rec["nohash"] = task["nohash"]
    if task["compare"]:
        rec["compare"] = compare(task)
    return rec


def _snap_hashes(path: Path):
    hs, body = [], hashlib.sha256()
    with gzip.open(path, "rt", encoding="utf-8") as f:
        for i, line in enumerate(f):
            if i == 0:
                continue
            body.update(line.encode())
            hs.append(json.loads(line).get("agent_state_snapshot_hash"))
    return hs, body.hexdigest()


def compare(task: dict) -> dict:
    stem = f"seed{task['seed']:03d}.jsonl.gz"
    h1, b1 = _snap_hashes(Path(task["cfg"]["output"]["dir"]) / "cells" / task["cell"] / stem)
    h2, b2 = _snap_hashes(Path(task["orig_dir"]) / "cells" / task["cell"] / stem)
    return {"records_new": len(h1), "records_old": len(h2), "snapshot_hash_equal": h1 == h2,
            "first_diff_record": next((i for i, (a, b) in enumerate(zip(h1, h2)) if a != b), None),
            "body_sha_equal": b1 == b2}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("config")
    ap.add_argument("out_root")
    ap.add_argument("--nohash", action="store_true")
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--seeds", default=None)
    ap.add_argument("--cells", default=None)
    ap.add_argument("--no-compare", action="store_true")
    ap.add_argument("--nsim", type=float, default=None)
    ap.add_argument("--vt", type=float, default=None)
    ap.add_argument("--greedy", action="store_true", help="生まれ方：共通構造の全体から儲けが増える限り外す（2026-09-25 決定）")
    ap.add_argument("--extgreedy", action="store_true", help="比べ：取り込みで儲けが増える限り一本ずつ足す")
    # ★ 2026-09-25 アストラさんの決定：--lowmem を既定にする（7 本で台帳が一字一句同じと確かめたため）。
    #   外すときは --no-lowmem。--lowmem は後方互換のために残す（付けても付けなくても同じ）。
    ap.add_argument("--lowmem", dest="lowmem", action="store_true", default=True, help="状態の正準形の控えを絞る（既定）")
    ap.add_argument("--no-lowmem", dest="lowmem", action="store_false", help="控えを絞らない（書き直し前の持ち方）")
    ap.add_argument("--compare-to", default=None, help="比べる相手の走行根（ledgers の親）")
    ap.add_argument("--extend-rule", default="v2", choices=["v2", "profit", "none"])
    ap.add_argument("--charge1", default="v2", choices=["v2", "d32"])
    ap.add_argument("--trial-count", type=int, default=None, help="試しの短い走行だけに使う（比べはしない）")
    ap.add_argument("--ident-rho", type=float, default=None,
                    help="旗A 両側で測る：比 ＝ 点(定義,相手) ÷（点(定義,定義) ＋ ρ × 相手の側だけの点）（tools/v32.py）")
    ap.add_argument("--ident-argmax", action="store_true",
                    help="旗B 一番高い定義を選び、基準に届けば同化・届かなければ誕生（tools/v32.py）")
    ap.add_argument("--ident-commons", action="store_true",
                    help="旗C 照らす相手を、今の場面全体ではなく、土台と今の場面で一致した構造（案 C1）にする（tools/v32.py）")
    ap.add_argument("--ident-shadow", action="store_true",
                    help="確かめ：元の同定も毎回呼んで比べる（旗A・B が切れていれば、違えば止める）")
    ap.add_argument("--proj-first", action="store_true",
                    help="穴埋めが同点でも、投影が一本出ていれば投影を使う（tools/projfirst.py）")
    ap.add_argument("--fix-order", action="store_true",
                    help="名前の順番の直し：親の中身として一緒に対になった子も、述語が一致すれば自分の番の点を数える（tools/fixorder.py）")
    ap.add_argument("--rename-check", action="store_true",
                    help="確かめ：同定のたびに、述語の名前を付け替えて判断をやり直し、違った回を数える（記録だけ。tools/v32.py）")
    ap.add_argument("--fix2", action="store_true",
                    help="直し②：墓石を子に持つ高階の行を、墓石の席の slot_history で照らす（同定と話すときの支持。tools/fix2.py）")
    ap.add_argument("--fast", action="store_true", help="2026-09-26 の試し：台帳の記録を速くする（台帳は同じ。tools/fastledger.py）")
    ap.add_argument("--no-public-history", dest="nohist", action="store_true",
                    help="2026-09-26 の試し：public_history を状態から外す（指紋と state_snapshot が変わる。tools/nohist.py）")
    ap.add_argument("--dump-slot-history", action="store_true",
                    help="走行末の全定義の slot_history（墓石の席も含む）と行を side の最後の行に書く（記録だけ。台帳は変えない）")
    args = ap.parse_args()
    import sweep
    cfg = json.load(open(args.config, encoding="utf-8"))
    orig_dir = cfg["output"]["dir"]
    out_root = Path(args.out_root).resolve()
    cfg2 = copy.deepcopy(cfg)
    cfg2["output"]["dir"] = str(out_root / "ledgers")
    if args.trial_count is not None:
        cfg2["trial_count"] = args.trial_count
        args.no_compare = True
    if args.nsim is not None:
        cfg2["fixed"]["nsim_threshold"] = args.nsim
    if args.vt is not None:
        cfg2["axes"]["verbatim_theta"] = [args.vt]
    assert not cfg2["output"]["dir"].startswith(str(ROOT / "runs")), "runs/ に書かない"
    runs = sweep.enumerate_runs(cfg2)
    if args.seeds:
        keep = {int(s) for s in args.seeds.split(",")}
        runs = [r for r in runs if r["seed"] in keep]
    if args.cells:
        # ★ v2 のセル名（vt を付けない名前）で選ぶ
        keep_c = set(args.cells.split(","))
        runs = [r for r in runs if sweep.cell_name(r["f"], r["theta_prime"], r["repair_scope"], None,
                                                   r["fill_selection"]) in keep_c]
    # ★ 種の順に並べる（締め切りで打ち切っても、終わった種は 4 セルがそろいやすいように）。
    runs.sort(key=lambda r: (r["seed"], r["cell"]))
    seed = sweep.load_seed(cfg["seed_file"])
    commit = sweep.code_commit()
    all_off = ((not args.nohash) and args.nsim is None and args.vt is None and not args.greedy and not args.extgreedy
               and args.extend_rule == "v2" and args.charge1 == "v2"
               and args.ident_rho is None and not args.ident_argmax and not args.ident_commons and not args.ident_shadow
               and not args.fix2 and not args.fix_order and not args.rename_check and not args.proj_first
               and not args.nohist)   # ★ public_history を外すと指紋が変わるので、runs/ とは比べない
    do_compare = (all_off or args.compare_to is not None) and (not args.no_compare)
    if args.compare_to is not None:
        orig_dir = str(Path(args.compare_to).resolve())
    tasks = [{**r, "cfg": cfg2, "code_commit": commit, "orig_dir": orig_dir, "out_root": str(out_root),
              "seed_file_sha256": getattr(seed, "file_sha256", None),
              "nohash": args.nohash, "prune": args.greedy, "extgreedy": args.extgreedy, "lowmem": args.lowmem,
              "extend_rule": args.extend_rule, "charge1": args.charge1,
              "dump_slot_history": args.dump_slot_history,
              "ident_rho": args.ident_rho, "ident_argmax": args.ident_argmax, "ident_shadow": args.ident_shadow,
              "ident_commons": args.ident_commons,
              "fast": args.fast, "nohist": args.nohist, "fix2": args.fix2,
              "fix_order": args.fix_order, "rename_check": args.rename_check, "proj_first": args.proj_first,
              "compare": do_compare} for r in runs]
    out_root.mkdir(parents=True, exist_ok=True)
    (out_root / "flag.json").write_text(json.dumps({"nohash": args.nohash, "nsim": args.nsim, "vt": args.vt,
                                                    "greedy": args.greedy, "extgreedy": args.extgreedy, "lowmem": args.lowmem,
                                                    "extend_rule": args.extend_rule, "charge1": args.charge1,
                                                    "compare_to": args.compare_to, "dump_slot_history": args.dump_slot_history, "config": args.config,
                                                    "ident_rho": args.ident_rho, "ident_argmax": args.ident_argmax, "ident_shadow": args.ident_shadow,
                                                    "ident_commons": args.ident_commons,
                                                    "fast": args.fast, "nohist": args.nohist, "fix2": args.fix2,
                                                    "fix_order": args.fix_order, "rename_check": args.rename_check, "proj_first": args.proj_first,
                                                    "commit": commit, "driver": "tools/v3_run.py",
                                                    "workers": args.workers}) + "\n")
    man = out_root / "manifest.jsonl"
    print(f"{time.strftime('%F %T')} 開始 {cfg['name']} nohash={args.nohash} nsim={args.nsim} vt={args.vt} "
          f"greedy={args.greedy} extgreedy={args.extgreedy} lowmem={args.lowmem} extend={args.extend_rule} charge1={args.charge1} ρ={args.ident_rho} argmax={args.ident_argmax} commons={args.ident_commons} shadow={args.ident_shadow} fix2={args.fix2} fix_order={args.fix_order} proj_first={args.proj_first} rename_check={args.rename_check} fast={args.fast} nohist={args.nohist} 走行 {len(tasks)} 並列 {args.workers} 比べる={do_compare}", flush=True)
    with ProcessPoolExecutor(max_workers=args.workers, max_tasks_per_child=1) as ex:
        futs = {ex.submit(worker, t): t for t in tasks}
        for fu in as_completed(futs):
            t = futs[fu]
            try:
                rec = fu.result()
            except Exception as e:  # noqa
                rec = {"cell": t["cell"], "seed": t["seed"], "error": repr(e)}
            with open(man, "a", encoding="utf-8") as fm:
                fm.write(json.dumps(rec, ensure_ascii=False) + "\n")
            c = rec.get("compare", {})
            print(f"{time.strftime('%F %T')} {rec['cell']} seed{rec['seed']:03d} 秒={rec.get('elapsed_sec')} "
                  f"最大メモリMB={rec.get('peak_rss_mb')} 定義末={rec.get('final_def_count')} "
                  f"一致={c.get('snapshot_hash_equal')} err={rec.get('error')}", flush=True)
            if rec.get("error") or (c and not c.get("snapshot_hash_equal")):
                print("★★ エラーまたは不一致。止める", flush=True)
                ex.shutdown(wait=False, cancel_futures=True)
                sys.exit(3)
    print(f"{time.strftime('%F %T')} ALLDONE {cfg['name']}", flush=True)


if __name__ == "__main__":
    main()

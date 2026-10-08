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
   --fill-norestate v3.5 の穴埋めの直し（2026-09-27 判断 1、案 B）：選んだ述語が、席を写した位置で見えている関係と同じなら、その席を埋めない
                  （選び直さない）。同じ物の組にほかの関係が見えていても、選んだ述語が見えていなければ埋める。--fill-unseen とは一緒に使わない。tools/fillnorestate.py
   --no-charge2   v3.7 の直し（2026-09-28、案1）：② の罰をやめる（classify_row の ② を ③ と同じに扱う。tools/nocharge2.py）
   --own-evidence v3.8（2026-09-28 夕）：本人が受け取った証拠だけで学ぶ会計（D-08〜D-11。--no-charge2 と一緒に。tools/v38.py）
   --death-terms  v3.7：死んだ行の V の項（参加率など）を side に書く。記録だけ（tools/deathterms.py）
   --v39          v3.9（2026-09-29 深夜）：記憶予算・三段階の忘却（F・H・U の席、局所の三答え、ビットの費用と予算。tools/v39.py）。
                  v3.8 の旗一式（--own-evidence・--no-charge2・--charge1 d32・--fix2-full・--fix-order2・--extend-rule none）と一緒に、--greedy なしで使う。
                  --v39-budget inf|<ビット>（既定 inf）・--v39-init two|zero（生まれたときの初期成績、既定 two）・--v39-a 0.5|1（既定 0.5）・
                  --v39-u global|abstain（U の答え、既定 global）
                  v3.10（2026-09-29 朝）：--v39-decay uniform|actr（点数の記録の 16 本の平均の重み。actr は τₖ^(−0.5) ∝、既定 uniform）・
                  --v39-price λ（1 ビットの値段。予算無限で、V＜λ の変換を候補がなくなるまで行う）・--v39-dump-cands（較正用：各試行の終わりの候補の正の点数を書き出す）
   --checks       v3.7：決まりごとの検査（罰を受けた行の写し先が伏せ辺そのものでない・当たりの試行に罰が付かない）。記録だけ（tools/checks_v37.py）
   --fill-unseen  v3.4 の穴埋めの直し（2026-09-27）：席を写した位置に見えている関係が一本でもあれば、述語によらずその席を埋めない。
                  伏せ辺の位置（見えていない位置）は今までどおり埋める。tools/fillunseen.py
   --proj-first   穴埋めの同点で投影を捨てない（2026-09-26 夜）：投影が一本出ていれば、穴埋めが同点でも投影を使う。tools/projfirst.py
   --fix-order    名前の順番の直し（2026-09-26 夜）：親の中身として一緒に対になった子も、述語が一致していれば、
                  自分の番で対にしたのと同じ点を数える。map_graphs を差し替え、使っている所すべてに効く。tools/fixorder.py
   --fix-order2   名前・番号に依らない写し（2026-09-26 夜、案 1）。--fix-order の代わりに使う（両方は付けない）。
                  候補の順番を構造だけで決め（子が先・構造に埋まった対が先）、同じ順位で食い違う候補は、最大の組すべてに共通するものだけ採る。
                  伝播は一通りに決まる対応だけ。tools/fixorder2.py
   --rename-check 確かめ：同定のたびに述語の名前を付け替えて（二通り）判断をやり直し、違った回を数える（記録だけ）
   --fix2-full    直し②を予測と会計にも広げる（2026-09-26 夜）：選んだ定義の投影・穴埋め・会計にも直し②の写しを渡す。--fix2 を含む
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

    _REAL.pop("theta_impl", None)

    def theta_wrapped(state, *a, **kw):
        # ★ v3.9（--v39）：削除の段を tools/v39.py の apply に差し替える（旗を切れば real_theta のまま）
        after, events = (_REAL.get("theta_impl") or real_theta)(state, *a, **kw)
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
    if task.get("hist_role"):
        # ★ v3.10h（2026-09-29 夜）：m1 の一階の席の履歴を、親の行の写しで集める（tools/histrole.py）。
        #   abm.abstraction.m1 そのものを包むので、loop.m1 を控える _install より前に入れる。
        sys.path.insert(0, str(ROOT / "tools"))
        import histrole
        histrole.install()
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
    if task.get("fill_norestate"):
        # ★ v3.5 の穴埋めの直し（2026-09-27 判断 1、案 B）：tools/fillnorestate.py。projfirst より前に入れる。
        if task.get("fill_unseen"):
            raise ValueError("--fill-unseen と --fill-norestate は一緒に使わない")
        sys.path.insert(0, str(ROOT / "tools"))
        import fillnorestate
        fillnorestate.install()
    if task.get("fill_unseen"):
        # ★ v3.4 の穴埋めの直し（2026-09-27）：tools/fillunseen.py。projfirst は install の時点の穴埋めを包むので、その前に入れる。
        sys.path.insert(0, str(ROOT / "tools"))
        import fillunseen
        fillunseen.install()
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
    if task.get("fix_order2"):
        # ★ 名前・番号に依らない写し（2026-09-26 夜、案 1）：map_graphs を差し替える（tools/fixorder2.py）。--fix-order の代わり。
        if task.get("fix_order"):
            raise ValueError("--fix-order と --fix-order2 は一緒に使わない")
        sys.path.insert(0, str(ROOT / "tools"))
        import fixorder2
        fixorder2.install()
    if task.get("fix2") or task.get("fix2_full"):
        # ★ 直し②（2026-09-26 夕）：墓石を子に持つ高階の行の照らし方（tools/fix2.py）。話すときの支持はここで差し替え、
        #   同定の側は tools/v32.py の同定の中で使う（下で v32 を必ず入れる）。--fix2-full は予測と会計にも同じ写しを渡す。
        sys.path.insert(0, str(ROOT / "tools"))
        import fix2
        fix2.install(full=bool(task.get("fix2_full")))
    if (task.get("ident_rho") is not None or task.get("ident_argmax") or task.get("ident_commons")
            or task.get("ident_shadow") or task.get("fix2") or task.get("fix2_full") or task.get("rename_check")):
        # ★ 二つ目の実験（2026-09-26）：同化先の決め方の旗 A・B・C（tools/v32.py）
        sys.path.insert(0, str(ROOT / "tools"))
        import v32
        v32.install(task.get("ident_rho"), bool(task.get("ident_argmax")), bool(task.get("ident_shadow")),
                    bool(task.get("ident_commons")), bool(task.get("fix2") or task.get("fix2_full")), bool(task.get("rename_check")))
    if task.get("no_charge2"):
        # ★ v3.7（2026-09-28、委任書「v3.7（② の罰をやめる）」、案1）：classify_row の ② を ③ にする（tools/nocharge2.py）。
        sys.path.insert(0, str(ROOT / "tools"))
        import nocharge2
        nocharge2.install()
    if task.get("own_evidence"):
        # ★ v3.8（2026-09-28 夕）：本人が受け取った証拠だけで学ぶ会計（tools/v38.py）。--no-charge2 の包みの外、--death-terms・--checks より前に入れる
        #   （deathterms は install の時点の participation を読むので、その前に差し替える）。
        if not task.get("no_charge2") or task.get("charge1") != "d32":
            raise ValueError("--own-evidence は --no-charge2 と --charge1 d32 と一緒に使う")
        sys.path.insert(0, str(ROOT / "tools"))
        import v38
        v38.install(fo)
    if task.get("death_terms"):
        # ★ v3.7：死んだ行の V の項を side に書く（記録だけ）。apply_theta の一番外側を包むので、ほかの差し替えのあとに入れる。
        sys.path.insert(0, str(ROOT / "tools"))
        import deathterms
        deathterms.install(fo)
    if task.get("checks"):
        # ★ v3.7：決まりごとの検査（記録だけ）。_update_accounting の一番外側（v31 の d32 のあと）を包むので、最後に入れる。
        sys.path.insert(0, str(ROOT / "tools"))
        import checks_v37
        checks_v37.install()
    if task.get("v39"):
        # ★ v3.9（2026-09-29 深夜）：記憶予算・三段階の忘却（tools/v39.py）。ほかの差し替えのあとに入れる（予測・同定・会計・m1 の一番外）。
        if (not task.get("own_evidence") or not task.get("no_charge2") or task.get("charge1") != "d32" or not task.get("fix2_full")
                or not task.get("fix_order2") or task.get("extend_rule") != "none" or task.get("prune")):
            raise ValueError("--v39 は v3.8 の旗一式（--own-evidence --no-charge2 --charge1 d32 --fix2-full --fix-order2 --extend-rule none）と、"
                             "--greedy なしで使う")
        sys.path.insert(0, str(ROOT / "tools"))
        import v39
        v39.install(fo, seed=int(task["seed"]), horizon=int(task["cfg"]["trial_count"]),
                    seed_file=str(ROOT / task["cfg"]["seed_file"]), budget=task["v39_budget"], init=task["v39_init"],
                    a=task["v39_a"], u=task["v39_u"], decay_mode=task.get("v39_decay", "uniform"), price=task.get("v39_price"),
                    dump_cands=(str(side_dir / f"seed{task['seed']:03d}.v39cands.f64") if task.get("v39_dump_cands") else None))
        if task.get("horizon") is not None:
            # ★ 時間の幅の旗（--horizon H、2026-10-03）：古さの重み・平均の重み・誕生の初期の成績の時間の幅を、走行の長さ T でなく H に（tools/horizon.py）
            import horizon
            horizon.install(int(task["horizon"]))
        if task.get("v310_be"):
            # ★ v3.10 B＋E（書き直しの費用で結ぶ統合版、2026-09-29 午後、マック）：tools/v310be.py。v39 の上、削除の段を取る前に入れる
            if task.get("v311c"):
                import abm.loop as _loop
                _REAL["m1_before_be"] = _loop.m1
            import v310be
            if task.get('logp_eps') is not None:
                v310be.EPSILON = task['logp_eps']
            v310be.install(fo, seed=int(task["seed"]), nohash=bool(task["nohash"]), score_role=bool(task.get("score_role")),
                           **({"score_logp": True, "score_logp_e": bool(task.get("score_logp_e"))}
                              if task.get("score_logp") else {}))
            if task.get("e_price") is not None:
                # ★ まとめの値段（--e-price、2026-10-01 午前・改訂の段 2）：E（tools/v310be.py choose_and_register の K＝A＋r＋λ dC）の λ だけを
                #   別の値にする。B（忘れる判断）は --v39-price のまま
                v310be.CFG["lam"] = float(task["e_price"])
                v310be.STATS["cfg"]["lam"] = v310be.CFG["lam"]
        _REAL["theta_impl"] = v39.CTX["apply"]
        if task.get("v311c"):
            import v311c
            v311c.install(fo, task, _REAL)
        if task.get("u_struct"):
            # ★ U の照合（--u-struct）と覚え直しの初期の評価（--relearn-init）：tools/ustruct.py・tools/relearninit.py。v39・v310be のあとに入れる
            import ustruct
            ustruct.install(fo)
            if task.get("relearn_init"):
                import relearninit
                relearninit.install(fo)
        if task.get("amb_local"):
            # ★ 候補ごとの棄権（--amb-local）：tools/v39.py amb_blocks。穴埋めの「あいまい」で、決まった候補まで止めない
            v39.CFG["amb_local"] = True
        if task.get("tie_struct"):
            # ★ 同点の並べ方（--tie-struct）：tools/tiestruct.py。変換の同点を構造だけの鍵で並べる
            import tiestruct
            tiestruct.install()
        if task.get("answer_gap"):
            # ★ 欠けた位置にだけ答える（--answer-gap、2026-09-30 夜の委任書）：tools/answergap.py。話す答えを選ぶ所（fill_decision）だけを包む
            import answergap
            answergap.install()
    if task.get("strict_pc"):
        # ★ 照合の直し：親子の並行連結（--strict-pc、2026-10-01 朝の委任書）：tools/strictpc.py。候補の差し替え（fix2・v39・ustruct）のすべてのあと、
        #   照合を使う前に入れる（sme._alignment_candidates をいちばん外側で包む）
        sys.path.insert(0, str(ROOT / "tools"))
        import strictpc
        strictpc.install()
    if task.get("world_cue"):
        # ★ 世界 v4（型の変種、2026-09-30 深夜の追記 B-2）：tools/worldvariant.py。世界を作る前に入れる。v39 の固定辞書に新しい述語を足す
        sys.path.insert(0, str(ROOT / "tools"))
        import worldvariant
        worldvariant.install(float(task.get("world_cue_p", 0.8)))
        if "v39" in sys.modules:
            worldvariant.extend_dictionary()
    if task.get("score_arg_order"):
        import argorder
        argorder.install()
    if task.get("select_n3"):
        # 旧い照合との対照に、従来のN3をそのまま使う。
        import selectn3
        selectn3.install_n3()
    if task.get("sme2017"):
        import smeshared
        smeshared.install(side_dir / f"seed{task['seed']:03d}.sme.jsonl.gz", tie_seed=int(task["seed"]), call_seed=task.get("sme_call_seed", False),
                          **({"tie_uniform": True} if task.get("sme_tie_uniform") else {}))
        if task.get("sme_reuse") or task.get("sme_prune"):
            import smeopt
            smeopt.install(reuse=task.get("sme_reuse", False), prune=task.get("sme_prune", False))
        if task.get("sme_intern_cache"):
            import smeintern
            smeintern.install()
        if task.get("sme_evict_trial_cache"):
            import smeevict
            smeevict.install(out_root / "evictions" / task["cell"] / f"seed{task['seed']:03d}.keys.jsonl.gz",
                            tombstone=task.get("sme_evict_tombstone", False))
        if task.get("cstar_options"):
            import cstar_runtime
            cstar_runtime.install(**task["cstar_options"])
    if task.get("shop_world"):
        # ★ お店の世界（2026-10-01 未明の予約の委任書「手がかりの世界」）：tools/shopworld.py。世界を作る前、試験の旗より前に入れる。
        #   v39 の固定辞書に新しい述語を足す
        if not (task.get("v39") and task.get("v310_be")):
            raise ValueError("--shop-world は --v39 --v310-be と一緒に使う")
        sys.path.insert(0, str(ROOT / "tools"))
        import shopworld
        shopworld.install(fo, world=int(task["shop_world"]), exc=float(task["shop_exc"]), keep_cue=bool(task.get("shop_keep_cue")),
                          side_path=str(side_dir / f"seed{task['seed']:03d}.shop.jsonl"))
        shopworld.extend_dictionary()
        if task.get("shop_scatter"):
            import shopscatter
            shopscatter.install()
    if task.get("probe_world"):
        # ★ 内的世界の試験（--probe-world、記録だけ）：tools/probeworld.py。世界の旗のあと、答えごとの記録より前、世界を作る前に入れる
        if not task.get("v39"):
            raise ValueError("--probe-world は --v39 と一緒に使う")
        sys.path.insert(0, str(ROOT / "tools"))
        import probeworld
        probeworld.install(side_dir / f"seed{task['seed']:03d}.probe.jsonl", run_seed=task["seed"], agent_ids=tuple(task["cfg"]["agent_ids"]),
                           seed_file=str(ROOT / task["cfg"]["seed_file"]), horizon=int(task["cfg"]["trial_count"]),
                           holdout_second=bool(task["cfg"]["fixed"].get("holdout_include_second_order", False)))
        if task.get("shop_world"):
            # ★ お店の世界の試験（対になった試験・共有部分の試験）を足す：tools/shopworld.py add_probes
            shopworld.add_probes(probeworld.ST, run_seed=task["seed"], agent_ids=tuple(task["cfg"]["agent_ids"]),
                                 holdout_second=bool(task["cfg"]["fixed"].get("holdout_include_second_order", False)))
    if task.get("cf_value"):
        # ★ 反実仮想の保持価値の診断（--cf-value、記録だけ。2026-10-01 午前の返事の段 5）：tools/cfvalue.py。試験の旗のあと、答えごとの記録より前
        if not (task.get("v39") and task.get("v310_be")):
            raise ValueError("--cf-value は --v39 --v310-be と一緒に使う")
        sys.path.insert(0, str(ROOT / "tools"))
        import cfvalue
        cfvalue.install(str(side_dir / f"seed{task['seed']:03d}.cfvalue.jsonl"), agent_id=tuple(task["cfg"]["agent_ids"])[0])
    if task.get("cf_learn"):
        # ★ 反実仮想で学ぶ腕 C（--cf-learn、2026-10-01 午前・改訂の段 3）：tools/cflearn.py。v310be のあと、--cf-value のあと、答えごとの記録より前
        if not (task.get("v39") and task.get("v310_be")):
            raise ValueError("--cf-learn は --v39 --v310-be と一緒に使う")
        sys.path.insert(0, str(ROOT / "tools"))
        import cflearn
        cflearn.install(str(side_dir / f"seed{task['seed']:03d}.cflearn.jsonl"), agent_id=tuple(task["cfg"]["agent_ids"])[0])
    if task.get("dump_answers"):
        # ★ 答えごとの記録（2026-09-30 朝の委任書の 2・3）：tools/answerlog.py。記録だけ（台帳は変わらない）。ほかの差し替えのあと、世界を作る前に入れる
        if not task.get("v39"):
            raise ValueError("--dump-answers は --v39 と一緒に使う")
        sys.path.insert(0, str(ROOT / "tools"))
        import answerlog
        answerlog.install(side_dir / f"seed{task['seed']:03d}.answers.csv", seed=int(task["seed"]),
                          seed_file=str(ROOT / task["cfg"]["seed_file"]))
    if task.get("dump_routing"):
        # ★ 証拠の届け先の記録（2026-09-30 夕方、委任書「外挿の印」の案 (1)）：tools/routelog.py。記録だけ（台帳・side は変わらない）。
        #   ほかの差し替えのすべてのあとに入れる（m1 と採点を一番外で包む）。書くのは side/<セル>/seed<種>.routing.jsonl だけ
        if not (task.get("v39") and task.get("v310_be") and task.get("hist_role")):
            raise ValueError("--dump-routing は --v39 --v310-be --hist-role と一緒に使う")
        sys.path.insert(0, str(ROOT / "tools"))
        import routelog
        routelog.install(str(side_dir / f"seed{task['seed']:03d}.routing.jsonl"))
    if task.get("use_forget") is not None:
        import useforget
        useforget.install(str(side_dir / f"seed{task['seed']:03d}.useforget.jsonl"),
                          tau=float(task["use_forget"]), horizon=int(task["cfg"]["trial_count"]))
    if task.get("sme2017"):
        import smereplay
        researcher_dir = out_root / "researcher" / task["cell"]
        if task.get("sme_online_candidates") or task.get("no_forget_exec"):
            researcher_dir.mkdir(parents=True, exist_ok=True)
        if task.get("sme_online_candidates"):
            import smeonline
            smeonline.install(researcher_dir / f"seed{task['seed']:03d}.candidates.jsonl.gz",
                              check=task.get("sme_online_check", False))
        if task.get("no_forget_exec"):
            import calibration
            calibration.install(researcher_dir / f"seed{task['seed']:03d}.calibration.jsonl.gz",
                                world=task.get("shop_world"), seed=int(task["seed"]))
        smereplay.install(side_dir / f"seed{task['seed']:03d}.sme.states.jsonl.gz", replay=task.get("sme_replay"),
                          **({"fast_encode": True} if task.get("sme_fast_encode") else {}))
    connection={}
    if task.get('attn_allin'):
        import attncstar
        from attnstage2_distribution import Readout
        connection=dict(feature_policy=attncstar.Features(task['logp_eps']),readout_policy=Readout())
    if task.get("attn_sme"):
        # 注意は選びだけを包む。既存sideと状態記録の外へ追加記録を書く。
        import attnsme
        attnsme.install(out_root / "attention" / task["cell"] / f"seed{task['seed']:03d}.jsonl.gz",
                        mode=task["attn_sme"], position=task["attn_position"], eta=task["attn_eta"],
                        fixed_zero=task.get("attn_fixed_zero", False), agent_ids=tuple(task["cfg"]["agent_ids"]),
                        epsilon=task.get('logp_eps',.5),**connection,
                        **(dict(learning_policy=attncstar.learn,prediction_context=attncstar.prediction_context)
                           if task.get('attn_allin') else {}))
    if task.get("v311c") and (task.get("cstar_options") or task.get("attn_sme")):
        # 診断は実際の問いの計数の外から、最終の注意の選びを呼ぶ。
        import abm.loop as _loop
        v311c.CFG["prepared_predict"] = _loop.predict
    if task.get('stage2') == 'on':
        import attnstage2_runtime
        attnstage2_runtime.install(out_root/'stage2'/task['cell']/f"seed{task['seed']:03d}.jsonl.gz",
                                  loss_mode=task['stage2_loss'],epsilon=task.get('logp_eps',.5),
                                  initial_mode=task['stage2_init'],scope=task['stage2_scope'],**connection,
                                  rematch_reuse=task.get('stage2_reuse',False),
                                  **({'measure_birth_hu':True} if task.get('stage2_birth_hu') else {}),
                                  **(dict(session_class=attncstar.Session) if task.get('attn_allin') else {}))
    if task.get("v311c") and (task.get("cstar_options") or task.get("attn_sme") or task.get("stage2") == "on"):
        import v311c_allin
        v311c_allin.install(task, side_dir)
    # 指示14で取り込んだ高速化枝の探索旗。既定はGC閾値を変えない。
    old_gc_threshold = None
    if task.get("sme_gc_threshold") is not None:
        import gc
        old_gc_threshold = gc.get_threshold()
        gc.set_threshold(task["sme_gc_threshold"], *old_gc_threshold[1:])
    try:
        rec = sweep.run_one(task)
    except Exception as e:  # noqa
        if task.get("v39") and type(e).__name__ == "Unfit":
            # ★ 容量不適合（仕様 8 節）：走行を止めて記録する。台帳は途中まで（完走分だけで成功を主張しない）
            fo.write(json.dumps({"kind": "v39_unfit", "detail": str(e)}, ensure_ascii=False) + "\n")
            fo.close()
            return {"cell": task["cell"], "seed": task["seed"], "v39_unfit": str(e), "v39": dict(sys.modules["v39"].STATS)}
        raise
    finally:
        if old_gc_threshold is not None:
            gc.set_threshold(*old_gc_threshold)
    if "v39" in sys.modules:
        rec["v39"] = dict(sys.modules["v39"].STATS)
    if task.get("sme2017"):
        rec["sme2017"] = sys.modules["smeshared"].close()
        rec["smereplay"] = sys.modules["smereplay"].close()
        if task.get("sme_online_candidates"):
            sys.modules["smeonline"].close()
        if task.get("no_forget_exec"):
            sys.modules["calibration"].close()
        if task.get("sme_evict_trial_cache"):
            sys.modules["smeevict"].close()
    if task.get("attn_sme"):
        rec["attn_sme"] = sys.modules["attnsme"].close()
    if task.get('stage2') == 'on':
        rec['stage2'] = sys.modules['attnstage2_runtime'].close()
    if task.get("v311c") and "v311c_allin" in sys.modules:
        sys.modules["v311c_allin"].close()
    if task.get("use_forget") is not None:
        rec["useforget"] = sys.modules["useforget"].close()
    if task.get("select_n3"):
        rec["select_n3"] = sys.modules["selectn3"].close()
    if task.get("v310_be"):
        rec["v310be"] = dict(sys.modules["v310be"].STATS)
    if task.get("hist_role"):
        rec["histrole"] = dict(sys.modules["histrole"].STATS)
    if task.get("u_struct"):
        rec["ustruct"] = dict(sys.modules["ustruct"].STATS)
    if task.get("relearn_init"):
        rec["relearninit"] = dict(sys.modules["relearninit"].STATS)
    if task.get("tie_struct"):
        rec["tiestruct"] = dict(sys.modules["tiestruct"].STATS)
    if task.get("answer_gap"):
        rec["answergap"] = dict(sys.modules["answergap"].STATS)
    if task.get("world_cue"):
        rec["worldvariant"] = dict(sys.modules["worldvariant"].STATS)
    if task.get("dump_answers"):
        rec["answerlog"] = sys.modules["answerlog"].close()
    if task.get("dump_routing"):
        rec["routelog"] = dict(sys.modules["routelog"].STATS)
        sys.modules["routelog"].close()
    if task.get("probe_world"):
        rec["probeworld"] = sys.modules["probeworld"].close()
    if task.get("shop_world"):
        rec["shopworld"] = sys.modules["shopworld"].close()
    if task.get("strict_pc"):
        rec["strictpc"] = sys.modules["strictpc"].stats()
    if task.get("cf_value"):
        rec["cfvalue"] = sys.modules["cfvalue"].close()
    if task.get("cf_learn"):
        rec["cflearn"] = sys.modules["cflearn"].close()
    if "nocharge2" in sys.modules:
        rec["nocharge2"] = dict(sys.modules["nocharge2"].STATS)
    if "v38" in sys.modules:
        rec["v38"] = dict(sys.modules["v38"].STATS)
    if "deathterms" in sys.modules:
        rec["deathterms"] = dict(sys.modules["deathterms"].STATS)
    if "checks_v37" in sys.modules:
        rec["checks_v37"] = dict(sys.modules["checks_v37"].STATS)
    if "v32" in sys.modules:
        rec["v32"] = dict(sys.modules["v32"].STATS)
    if "fix2" in sys.modules:
        rec["fix2"] = dict(sys.modules["fix2"].STATS)
    if "fixorder" in sys.modules:
        rec["fixorder"] = dict(sys.modules["fixorder"].STATS)
    if "fillnorestate" in sys.modules:
        rec["fillnorestate"] = dict(sys.modules["fillnorestate"].STATS)
    if "fillunseen" in sys.modules:
        rec["fillunseen"] = dict(sys.modules["fillunseen"].STATS)
    if "projfirst" in sys.modules:
        rec["projfirst"] = dict(sys.modules["projfirst"].STATS)
    if "fixorder2" in sys.modules:
        rec["fixorder2"] = dict(sys.modules["fixorder2"].STATS)
    if "v31" in sys.modules:
        rec["v31"] = dict(sys.modules["v31"].STATS)
    if task.get("fast"):
        rec["fast"] = {"evictions": fastledger.STATE["evictions"], "max_cache": fastledger.STATE["max_cache"]}
    elif task.get("lowmem"):
        rec["lowmem"] = {"evictions": lowmem.STATE["evictions"], "max_cache": lowmem.STATE["max_cache"]}
    rec["nohist"] = bool(task.get("nohist"))
    import resource
    if task.get("v311c"):
        rec["v311c"] = dict(sys.modules["v311c"].STATS)
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


def _run_collective(args, tasks, out_root: Path, man: Path) -> None:
    """★ v3.11c：集団の走行。走行（集団）ごとに、まとめ役を一つのプロセスで動かし、その中で個体ごとのプロセスを歩調を合わせて走らせる。"""
    import multiprocessing as mp
    import v311c
    if len({t["cell"] for t in tasks}) != 1:
        raise SystemExit(f"--v311c はセルを一つに絞って使う（--cells）。いま {len({t['cell'] for t in tasks})} セル")
    tmpl = tasks[0]
    fs = [float(x) for x in args.v311c_f.split(",")]
    n = len(fs)
    groups = [int(x) for x in args.v311c_groups.split(",")] if args.v311c_groups else [0] * n
    if len(groups) != n:
        raise SystemExit("--v311c-groups の長さが個体の数と違う")
    comm = out_root / "comm"
    comm.mkdir(parents=True, exist_ok=True)
    pops = []
    for r in [int(x) for x in args.v311c_runs.split(",")]:
        ts = [dict(tmpl, seed=r + 1000 * i, f=fs[i], compare=False,
                   v311c={"run": r, "agent": i, "n": n, "q": args.v311c_q, "m": args.v311c_m, "recv": args.v311c_recv,
                          "groups": groups, "tags": not args.v311c_no_tags, "b_n": args.v311c_b_n}) for i in range(n)]
        for key in ("probe_shop", "audit", "serial"):
            if getattr(args, "v311c_" + key):
                for task in ts:
                    task["v311c"][key] = True
        if args.v311c_sme_replay:
            for task in ts:
                task["sme_replay"] = str(Path(args.v311c_sme_replay) / f"seed{task['seed']:03d}.sme.states.jsonl.gz")
        pops.append((r, ts))

    def one(r, ts):
        s = v311c.coordinate(ts, comm / f"run{r:03d}.jsonl", probe_every=args.v311c_probe_every)
        if args.v311c_lineage and not s["errors"]:
            from v311c_lineage import write_lineage
            write_lineage(comm / f"run{r:03d}.jsonl", comm / f"run{r:03d}.lineage.jsonl", groups)
        (comm / f"run{r:03d}.summary.json").write_text(json.dumps(s, ensure_ascii=False, default=str) + "\n", encoding="utf-8")

    ctx = mp.get_context("fork")
    running = []
    queue = list(pops)
    while queue or running:
        while queue and len(running) < max(1, args.workers):
            r, ts = queue.pop(0)
            p = ctx.Process(target=one, args=(r, ts))
            p.start()
            running.append((r, p))
            print(f"{time.strftime('%F %T')} 集団 run{r:03d} を始めた（個体 {n}）", flush=True)
        r, p = running.pop(0)
        p.join()
        sp = comm / f"run{r:03d}.summary.json"
        s = json.loads(sp.read_text(encoding="utf-8")) if sp.exists() else {"errors": ["summary が無い"], "exitcode": p.exitcode}
        with open(man, "a", encoding="utf-8") as fm:
            for i, a in enumerate(s.get("agents") or []):
                fm.write(json.dumps({"run": r, "agent": i, **(a if isinstance(a, dict) else {"raw": str(a)})}, ensure_ascii=False, default=str) + "\n")
        print(f"{time.strftime('%F %T')} 集団 run{r:03d} 終わり 試行 {s.get('trials')} 束 {s.get('bundles')} 送信 {s.get('sent')} "
              f"受信 {s.get('recv')} 失敗 {len(s.get('errors') or [])}", flush=True)



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
    ap.add_argument("--fill-norestate", action="store_true",
                    help="v3.5：選んだ述語が、席を写した位置で見えている関係と同じなら埋めない（tools/fillnorestate.py）")
    ap.add_argument("--no-charge2", action="store_true",
                    help="v3.7：② の罰をやめる（classify_row の ② を ③ にする。tools/nocharge2.py）")
    ap.add_argument("--own-evidence", action="store_true",
                    help="v3.8：本人が受け取った証拠だけで学ぶ会計（D-08〜D-11。--no-charge2 と一緒に。tools/v38.py）")
    ap.add_argument("--v39", action="store_true",
                    help="v3.9：記憶予算・三段階の忘却（tools/v39.py）")
    ap.add_argument("--v39-budget", default="inf", help="v3.9 の予算（ビット）。inf は無限")
    ap.add_argument("--v39-init", default="two", choices=["two", "zero"], help="v3.9 の生まれたときの初期成績（二場面／0）")
    ap.add_argument("--v39-a", default="0.5", choices=["0.5", "1"], help="v3.9 の a（少量の成績の補正）")
    ap.add_argument("--v39-u", default="global", choices=["global", "abstain"], help="v3.9 の U の答え（全体最頻／棄権）")
    ap.add_argument("--v39-decay", default="uniform", choices=["uniform", "actr"], help="v3.10：点数の記録の平均の重み")
    ap.add_argument("--v39-price", type=float, default=None, help="v3.10：1 ビットの値段 λ（予算無限で V＜λ の変換）")
    ap.add_argument("--v310-be", action="store_true", help="v3.10 B＋E（書き直しの費用で結ぶ統合版、tools/v310be.py）。--v39-decay actr・予算無限・--v39-price λ と一緒に")
    ap.add_argument("--score-logp", action="store_true", help="保持の採点を開示前の確率の対数費用にする（epsilon=1/2）")
    ap.add_argument("--score-logp-e", action="store_true", help="EのH席の費用も対数にする（--score-logpと一緒に）")
    ap.add_argument("--probe-world", action="store_true",
                    help="内的世界の試験（記録だけ）：100 試行ごとに、固定した試験の場面の骨組みの関係を一本ずつ伏せた問いに答えさせる（学習しない。tools/probeworld.py）")
    ap.add_argument("--dump-answers", action="store_true",
                    help="答えごとの記録（記録だけ）：実際に答えた試行ごとに side/<セル>/seed<種>.answers.csv へ一行（tools/answerlog.py）")
    ap.add_argument("--dump-routing", action="store_true",
                    help="証拠の届け先の記録（記録だけ）：m1 が席に足した観察と出どころ・採点の届け先と届かなかった理由を side/<セル>/seed<種>.routing.jsonl へ（tools/routelog.py）")
    ap.add_argument("--world-cue", action="store_true",
                    help="世界 v4（型の変種）：場面ごとの変種 A／B で、二つの部分木の最初の一階の葉の述語を切り替える（tools/worldvariant.py）")
    ap.add_argument("--cf-learn", action="store_true",
                    help="反実仮想で学ぶ腕 C：B の R̄F・R̄H・R̄U を、席自身の答えでなく、その席を F・H・U にした写しで言う最終的な答えの書き直し費用で積む（tools/cflearn.py）")
    ap.add_argument("--horizon", type=int, default=None,
                    help="時間の幅：古さの重みのはしご・平均の重み・誕生の初期の成績で、走行の長さ T の代わりに H を使う（tools/horizon.py。--v39 と一緒に）")
    ap.add_argument("--e-price", type=float, default=None,
                    help="まとめの値段：E（新しい場面を既存の定義にまとめるか新しく作るか）の λ を、--v39-price（B の忘れる値段）と別に与える（--v310-be と一緒に）")
    ap.add_argument("--cf-value", action="store_true",
                    help="反実仮想の保持価値の診断（記録だけ）：開示のあった試行で、選ばれた定義の席を一段薄くした写しで答え直し、書き直し費用の差を書く（tools/cfvalue.py）")
    ap.add_argument("--strict-pc", action="store_true",
                    help="照合の直し：親の候補の対は、その子の対がすべて（見えていない相手か、採れる直接の候補）のときだけ採る（tools/strictpc.py）")
    ap.add_argument("--shop-world", type=int, choices=(1, 2), default=None,
                    help="お店の世界：種は M1（甲）・M2（乙）だけのもの（tools/shop/U-011_seed_shop.json）。シールと link を足し、ドアの述語を世界 1／2 の表で決める（tools/shopworld.py）")
    ap.add_argument("--shop-exc", type=float, default=0.2, help="お店の世界：例外のシールの割合（既定 0.2）")
    ap.add_argument("--shop-keep-cue", action="store_true", help="お店の世界の診断：B の変換の候補からシールと link の席を外す")
    ap.add_argument("--world-cue-p", type=float, default=0.8, help="世界 v4（型の変種）：変種 A の確率（既定 0.8）")
    ap.add_argument("--u-struct", action="store_true",
                    help="U の照合：U の席を名前の条件を持たない関係の位置として照合に参加させる（--v39 --hist-role と一緒に。tools/ustruct.py）")
    ap.add_argument("--relearn-init", action="store_true",
                    help="覚え直しの初期の評価：U→H の覚え直しの観察一回を H と U で採点して初期値に入れる（--u-struct --v310-be と一緒に。tools/relearninit.py）")
    ap.add_argument("--amb-local", action="store_true",
                    help="候補ごとの棄権：穴埋めで決まった候補があれば、ほかの席の同点（あいまい）で答え全体を止めない（--v39 と一緒に。tools/v39.py amb_blocks）")
    ap.add_argument("--answer-gap", action="store_true",
                    help="欠けた位置にだけ答える：投影・穴埋めの候補を、対応先が提示の場面の欠けた位置（ぶら下がった参照）に入るものに絞ってから今の決まりで選ぶ（--v39 --v310-be と一緒に。tools/answergap.py）")
    ap.add_argument("--tie-struct", action="store_true",
                    help="同点の並べ方：変換の同点を、名前や番号ではなく構造だけの鍵（生まれた試行・階・親の述語と位置）で並べる（--v39 と一緒に。tools/tiestruct.py）")
    ap.add_argument("--score-role", action="store_true",
                    help="v3.10hs：B の採点を、席の親が対応した場面の関係の同じ位置の子（関係 ID）が開示の関係と一致する席だけにする（--v310-be と一緒に。tools/v310be.py）")
    ap.add_argument("--score-arg-order", action="store_true",
                    help="A の採点と初期採点、E の書換費用で対応後の引数の順も比べる（--v310-be --hist-role --score-role と一緒に）")
    ap.add_argument("--sme2017", action="store_true", help="SME2017の順つき照合と、同じ採点の関数によるN3を使う（--v39と一緒に）")
    ap.add_argument("--sme-call-seed", action="store_true", help="SMEの同点を走行の種・試行・正準形・種類から呼び出しごとの種で選ぶ（--sme2017と一緒に）")
    ap.add_argument("--sme-reuse", action="store_true", help="同点なしの証拠のある照合を使い回す探索の旗")
    ap.add_argument("--sme-prune", action="store_true", help="N3と門の厳密な上限で負ける候補を省く探索の旗")
    ap.add_argument("--sme-intern-cache", action="store_true", help="型と全ての内容が同じ不変の照合結果の実体を共有する探索の旗")
    ap.add_argument("--sme-evict-trial-cache", action="store_true", help="完了した試行の呼び出し種を持つ照合の控えだけを捨てる探索の旗")
    ap.add_argument("--sme-evict-tombstone", action="store_true", help="捨てた完全な鍵が後で引かれたら止める検査の旗")
    ap.add_argument("--attn-sme", choices=("binary", "global", "position"), default=None, help="ドア課題の定義選びに位置の案1／案2′を用いる")
    ap.add_argument("--attn-position", choices=("k1", "k2"), default="k1", help="祖先の鍵／採用済みSME対応先の鍵")
    ap.add_argument("--attn-eta", type=float, default=0.1, help="位置の注意の更新幅")
    ap.add_argument('--attn-allin',action='store_true',help='指示8の共通基底・主の分布・mixture学習を接続する別版')
    ap.add_argument("--attn-fixed-zero", action="store_true", help="費用を測るがa=0を保つ全バイト一致の検査")
    ap.add_argument('--stage2',choices=('off','on'),default='off',help='全候補の答えの損の差で保持を値付けする')
    ap.add_argument('--stage2-loss',choices=('alpha','top1','mixture','arm'),default='arm',help='第二段の損：0/ℓ、選んだ席の分布、混合分布、土台の採点に従う')
    ap.add_argument('--stage2-init',choices=('virtual','zero','A'),default='virtual',help='第二段の誕生の初期値：仮の問い（主）、0、局所A（比べ）')
    ap.add_argument('--stage2-scope',choices=('all','chosen'),default='all',help='最終損の差を測る席：全定義（主）、実際に選ばれた定義だけ（Cの新しい版）')
    ap.add_argument('--stage2-reuse',choices=('off','on'),default='off',help='C*の第二段で点に依らない照合の土台を試行内で使い回す')
    ap.add_argument('--stage2-birth-hu',choices=('off','on'),default='off',help='準備の旗：出生のF席をHにした後のH→Uの差も同じ仮問いで測る（使用は別承認）')
    ap.add_argument("--sme-tie-uniform", action="store_true", help="構造の鍵で同点を狭めず、照合・定義・逐語の残った同点全体を一様抽選する（--sme-call-seedと一緒に）")
    ap.add_argument("--sme-gc-threshold", type=int, default=None,
                    help="探索用：GCの世代0の閾値だけを変える（世代1・2は現行のまま、既定は無変更）")
    ap.add_argument("--sme-fast-encode", action="store_true", help="探索用：保存状態のスカラーを先に判別して同じ記録を速く組み立てる")
    ap.add_argument("--match-cstar", action="store_true", help="予測の照合とN3に固定対応の期待点C*を使う")
    ap.add_argument("--match-cstar-e", action="store_true", help="Eの逐語の材料選びと同化の照合にC*を使う")
    ap.add_argument("--h-dirichlet", type=int, choices=(1,), default=None, help="Hの分布を履歴の回数と背景bのディリクレ型（α=1）にする")
    ap.add_argument("--match-eps", choices=("0", "shared"), default="0", help="C*のqに背景bへの混ぜを入れない0、値付けのPとそろえるshared")
    ap.add_argument("--logp-eps", type=float, default=0.5, help="背景分布bに戻る混合率ε（既定0.5）")
    ap.add_argument("--birth-score", choices=("fit", "seq"), default=None, help="二材料を観察後に当てるfit、一材料ずつ順に当てるseq")
    ap.add_argument("--select-n3", action="store_true", help="旧い照合の対照用に従来のN3を使う（--v39、SME2017と同時には使わない）")
    ap.add_argument("--sme-replay", default=None, help="順を保った状態の記録から、同じ予測と更新を再生する検査（--sme2017、種1本だけ）")
    ap.add_argument("--sme-online-candidates", action="store_true", help="予測の実際の対応から候補の答えと正誤を研究者だけの別記録に残す")
    ap.add_argument("--sme-online-check", action="store_true", help="候補の記録の逆順・二回の一致を毎試行で検査する")
    ap.add_argument("--no-forget-exec", action="store_true", help="本番と同じVと参照H→Uを記録し、F→H・H→Uの実行だけを止める較正の旗")
    ap.add_argument("--use-forget", type=float, default=None, help="既存のD-最小fe8d567の名前の使用による忘却、強さの門τ")
    ap.add_argument("--shop-scatter", action="store_true", help="お店の四葉を二経路の物の配置にする（--shop-worldと一緒に）")
    ap.add_argument("--v311c", action="store_true", help="v3.11c：集団化・事例伝達（tools/v311c.py）。B＋E の旗一式と一緒に")
    ap.add_argument("--v311c-f", default="0.5,0.5", help="v3.11c：個体ごとの f（開示の確率）。個体の数はこの並びの長さ")
    ap.add_argument("--v311c-groups", default=None, help="v3.11c：個体ごとの組（既定は全員 0）")
    ap.add_argument("--v311c-q", type=float, default=0.2, help="v3.11c：実際に答えた人が束を送る確率 q")
    ap.add_argument("--v311c-m", type=float, default=0.0, help="v3.11c：別の組の相手を選ぶ確率 m（二体では使わない）")
    ap.add_argument("--v311c-recv", default="B", choices=["A", "B"], help="v3.11c：受信 A（名前を使わない）／受信 B（同じ名札を優先）")
    ap.add_argument("--v311c-runs", default="1", help="v3.11c：走行（集団）の番号。個体 i の世界の種は 走行＋1000×i")
    ap.add_argument("--v311c-b-n", type=int, default=None, help="v3.11c：名札の固定長 b を決める個体の数（既定は集団の個体数。単独の比べの走行で集団と同じ b にするとき）")
    ap.add_argument("--v311c-no-tags", action="store_true", help="v3.11c の検査 ① 用：集団化の機能を全部切る（名札も通信もしない）")
    ap.add_argument("--v311c-probe-every", type=int, default=100, help="v3.11c：回答の一致の試験の間隔（0 で試験しない）")
    ap.add_argument("--v311c-probe-shop", action="store_true", help="一致の試験を店×日ごとの固定20問にする（学習には戻さない）")
    ap.add_argument("--v311c-audit", action="store_true", help="研究者用：各試行の状態・乱数の指紋と試験の非干渉を検査する")
    ap.add_argument("--v311c-lineage", action="store_true", help="研究者用：走行後に通信記録から定義ごとの出どころ候補の系譜を書く")
    ap.add_argument("--v311c-sme-replay", default=None, help="集団化の個体別SME状態記録のディレクトリから再生する（集団の種一本）")
    ap.add_argument("--v311c-serial", action="store_true", help="個体の重い計算を全体で一つずつ実行する（試行の歩調は同じ）")
    ap.add_argument("--hist-role", action="store_true",
                    help="v3.10h：m1 の一階の席の履歴を、親の行が写った場面の関係の同じ位置の子で集める（物の組で集めない。tools/histrole.py）")
    ap.add_argument("--v39-dump-cands", action="store_true", help="v3.10 の較正用：各試行の終わりの候補の正の点数を side に書き出す")
    ap.add_argument("--death-terms", action="store_true",
                    help="v3.7：死んだ行の V の項を side に書く（記録だけ。tools/deathterms.py）")
    ap.add_argument("--checks", action="store_true",
                    help="v3.7：決まりごとの検査（罰の写し先が伏せ辺そのものでない・当たりの試行に罰が付かない。記録だけ。tools/checks_v37.py）")
    ap.add_argument("--fill-unseen", action="store_true",
                    help="v3.4：席を写した位置に見えている関係があれば、述語によらず埋めない（tools/fillunseen.py）")
    ap.add_argument("--proj-first", action="store_true",
                    help="穴埋めが同点でも、投影が一本出ていれば投影を使う（tools/projfirst.py）")
    ap.add_argument("--fix-order", action="store_true",
                    help="名前の順番の直し：親の中身として一緒に対になった子も、述語が一致すれば自分の番の点を数える（tools/fixorder.py）")
    ap.add_argument("--fix-order2", action="store_true",
                    help="名前・番号に依らない写し（--fix-order の代わり。tools/fixorder2.py）")
    ap.add_argument("--rename-check", action="store_true",
                    help="確かめ：同定のたびに、述語の名前を付け替えて判断をやり直し、違った回を数える（記録だけ。tools/v32.py）")
    ap.add_argument("--fix2-full", action="store_true",
                    help="直し②を予測と会計にも広げる（選び方・投影・穴埋め・会計が同じ写しを使う。--fix2 を含む。tools/fix2.py）")
    ap.add_argument("--fix2", action="store_true",
                    help="直し②：墓石を子に持つ高階の行を、墓石の席の slot_history で照らす（同定と話すときの支持。tools/fix2.py）")
    ap.add_argument("--fast", action="store_true", help="2026-09-26 の試し：台帳の記録を速くする（台帳は同じ。tools/fastledger.py）")
    ap.add_argument("--no-public-history", dest="nohist", action="store_true",
                    help="2026-09-26 の試し：public_history を状態から外す（指紋と state_snapshot が変わる。tools/nohist.py）")
    ap.add_argument("--dump-slot-history", action="store_true",
                    help="走行末の全定義の slot_history（墓石の席も含む）と行を side の最後の行に書く（記録だけ。台帳は変えない）")
    args = ap.parse_args()
    if args.v311c and not (args.v39 and args.v310_be):
        ap.error("--v311c は --v39 --v310-be と一緒に使う")
    if args.v311c_probe_shop and args.shop_world is None:
        ap.error("--v311c-probe-shop は --shop-world と一緒に使う")
    if args.v311c_sme_replay and not (args.v311c and args.sme2017 and len(args.v311c_runs.split(",")) == 1):
        ap.error("--v311c-sme-replay は --v311c --sme2017 と集団の種一本で使う")
    if args.v311c and args.sme_replay:
        ap.error("集団化の再生は個体別の受信段階を含む別の記録を使う")
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
    if args.score_logp and not args.v310_be:
        raise SystemExit("--score-logp は --v310-be と一緒に使う")
    if args.score_logp_e and not args.score_logp:
        raise SystemExit("--score-logp-e は --score-logp と一緒に使う")
    cstar_options = {}
    if (args.match_cstar or args.match_cstar_e or args.h_dirichlet is not None
            or args.birth_score is not None or args.logp_eps != .5):
        if not (args.sme2017 and args.v310_be and args.score_arg_order):
            raise SystemExit("C*と共通分布の旗は--sme2017 --v310-be --score-arg-orderと一緒に使う")
        if not 0 <= args.logp_eps <= 1:
            raise SystemExit("--logp-epsは0以上1以下")
        cstar_options = dict(match_cstar=args.match_cstar,match_cstar_e=args.match_cstar_e,
                             h_dirichlet=args.h_dirichlet,match_eps=args.match_eps,
                             logp_eps=args.logp_eps,birth_score=args.birth_score)
    if args.score_role and not args.v310_be:
        raise SystemExit("--score-role は --v310-be と一緒に使う")
    if args.u_struct and (not args.v39 or not args.hist_role):
        raise SystemExit("--u-struct は --v39 と --hist-role と一緒に使う")
    if args.amb_local and not args.v39:
        raise SystemExit("--amb-local は --v39 と一緒に使う")
    if args.tie_struct and not args.v39:
        raise SystemExit("--tie-struct は --v39 と一緒に使う")
    if args.answer_gap and not (args.v39 and args.v310_be):
        raise SystemExit("--answer-gap は --v39 --v310-be と一緒に使う")
    if args.relearn_init and (not args.u_struct or not args.v310_be):
        raise SystemExit("--relearn-init は --u-struct と --v310-be と一緒に使う")
    if args.v310_be and (not args.v39 or args.v39_decay != "actr" or args.v39_budget != "inf" or args.v39_price is None):
        raise SystemExit("--v310-be は --v39 --v39-decay actr --v39-budget inf --v39-price λ と一緒に使う")
    seed = sweep.load_seed(cfg["seed_file"])
    if args.horizon is not None and not args.v39:
        raise SystemExit("--horizon は --v39 と一緒に使う（時間の幅を差し替える先が v39 の時間の設定のため）")
    commit = sweep.code_commit()
    all_off = ((not args.nohash) and args.nsim is None and args.vt is None and not args.greedy and not args.extgreedy
               and args.extend_rule == "v2" and args.charge1 == "v2"
               and args.ident_rho is None and not args.ident_argmax and not args.ident_commons and not args.ident_shadow
               and not args.fix2 and not args.fix2_full and not args.fix_order and not args.fix_order2 and not args.rename_check and not args.proj_first
               and not args.fill_unseen and not args.fill_norestate and not args.no_charge2 and not args.own_evidence
               and not args.v39 and not args.hist_role and not args.world_cue and not args.u_struct and not args.tie_struct and not args.amb_local and not args.answer_gap and not args.probe_world and args.shop_world is None and not args.strict_pc and not args.cf_value and args.e_price is None and not args.cf_learn
               and args.horizon is None and not args.score_logp and not args.nohist)   # ★ public_history を外すと指紋が変わるので、runs/ とは比べない
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
              "fix_order": args.fix_order, "fix_order2": args.fix_order2, "rename_check": args.rename_check, "proj_first": args.proj_first,
              "fix2_full": args.fix2_full, "fill_unseen": args.fill_unseen, "fill_norestate": args.fill_norestate,
              "no_charge2": args.no_charge2, "death_terms": args.death_terms, "checks": args.checks,
              "own_evidence": args.own_evidence,
              "v39": args.v39, "v39_budget": (None if args.v39_budget == "inf" else int(args.v39_budget)),
              "v39_init": args.v39_init, "v39_a": float(args.v39_a), "v39_u": args.v39_u,
              "v39_decay": args.v39_decay, "v39_price": args.v39_price, "v39_dump_cands": args.v39_dump_cands,
              "v310_be": args.v310_be, "hist_role": args.hist_role, "score_role": args.score_role,
              "world_cue": args.world_cue, "world_cue_p": args.world_cue_p, "dump_answers": args.dump_answers, "dump_routing": args.dump_routing,
              "u_struct": args.u_struct, "relearn_init": args.relearn_init, "tie_struct": args.tie_struct, "amb_local": args.amb_local,
              "answer_gap": args.answer_gap, "probe_world": args.probe_world,
              "shop_world": args.shop_world, "shop_exc": args.shop_exc, "shop_keep_cue": args.shop_keep_cue, "strict_pc": args.strict_pc, "cf_value": args.cf_value, "e_price": args.e_price, "cf_learn": args.cf_learn, "compare": do_compare,
              **({"horizon": args.horizon} if args.horizon is not None else {})} for r in runs]
    out_root.mkdir(parents=True, exist_ok=True)
    if args.score_logp:
        for task in tasks:
            task.update(score_logp=True, score_logp_e=args.score_logp_e)
    if cstar_options:
        for task in tasks:
            task["cstar_options"] = cstar_options
    if args.score_arg_order:
        if not (args.v310_be and args.hist_role and args.score_role):
            raise SystemExit("--score-arg-order は --v310-be --hist-role --score-role と一緒に使う")
        for task in tasks:
            task["score_arg_order"] = True
    if args.sme_evict_tombstone and not args.sme_evict_trial_cache:
        raise SystemExit("--sme-evict-tombstoneは控えを捨てる旗と一緒に使う")
    if (args.sme_reuse or args.sme_prune or args.sme_intern_cache or args.sme_evict_trial_cache) and not (args.sme2017 and args.sme_call_seed):
        raise SystemExit("控えの探索の旗は--sme2017 --sme-call-seedと一緒に使う")
    if args.sme_call_seed and not args.sme2017:
        raise SystemExit("--sme-call-seed は --sme2017 と一緒に使う")
    if args.sme_tie_uniform and not args.sme_call_seed:
        raise SystemExit("--sme-tie-uniform は --sme2017 --sme-call-seed と一緒に使う")
    if args.sme_gc_threshold is not None and (not args.sme2017 or args.sme_gc_threshold <= 0):
        raise SystemExit("--sme-gc-threshold は --sme2017 と正の整数で使う")
    if args.sme_fast_encode and not args.sme2017:
        raise SystemExit("--sme-fast-encode は --sme2017 と一緒に使う")
    if args.sme2017 and not (args.v39 and args.u_struct and args.strict_pc):
        raise SystemExit("--sme2017は--v39 --u-struct --strict-pcと一緒に使う（保持したUの引数と型の控えを使うため）")
    if args.select_n3 and (not args.v39 or args.sme2017):
        raise SystemExit("--select-n3は旧い照合の対照用。--v39と一緒に、--sme2017とは別に使う")
    if args.shop_scatter and (args.shop_world is None or args.world_cue):
        raise SystemExit("--shop-scatterはお店の世界だけで使う")
    if args.sme_replay is not None and (not args.sme2017 or len(tasks) != 1):
        raise SystemExit("--sme-replayはSMEの走行一本にだけ使う")
    if (args.sme_online_candidates or args.no_forget_exec) and not (args.sme2017 and args.v310_be):
        raise SystemExit("候補の記録と忘却停止は--sme2017 --v310-beと一緒に使う")
    if args.sme_online_check and not args.sme_online_candidates:
        raise SystemExit("--sme-online-checkは--sme-online-candidatesと一緒に使う")
    if args.attn_sme and not (args.sme2017 and args.shop_world and args.sme_call_seed):
        raise SystemExit("--attn-smeは--sme2017 --sme-call-seedとお店の世界で使う")
    if args.attn_fixed_zero and not args.attn_sme:
        raise SystemExit("--attn-fixed-zeroは注意の旗と一緒に使う")
    if args.attn_allin and not (args.attn_sme=='global' and args.attn_position=='k2' and
                               args.attn_eta==.1 and args.logp_eps==.01):
        raise SystemExit('--attn-allinはglobal・k2・eta0.1・logp-eps0.01で使う')
    if args.stage2 == 'on' and not (args.attn_sme and args.v310_be):
        raise SystemExit('--stage2 onは--attn-smeと--v310-beと一緒に使う')
    if args.stage2 == 'on' and (args.cf_learn or args.cf_value or args.use_forget is not None):
        raise SystemExit('第二段をほかの保持の置換と合算しない')
    if args.stage2_reuse == 'on' and not (args.stage2 == 'on' and args.attn_allin and args.match_cstar):
        raise SystemExit('--stage2-reuse onはC*・全部入り・第二段onと一緒に使う')
    if args.stage2_birth_hu == 'on' and not (args.stage2 == 'on' and args.stage2_init == 'virtual'):
        raise SystemExit('--stage2-birth-hu onは第二段on・virtual初期値と一緒に使う')
    if args.logp_eps is not None and not 0 <= args.logp_eps <= 1:
        raise SystemExit('--logp-epsは0以上1以下')
    for task in tasks:
        for opt in ("sme_online_candidates", "sme_online_check", "no_forget_exec"):
            if getattr(args, opt):
                task[opt] = True
        if args.attn_allin:task['attn_allin']=True
        if args.stage2 == 'on':
            task.update(stage2='on',stage2_loss=args.stage2_loss,stage2_init=args.stage2_init,stage2_scope=args.stage2_scope)
            if args.stage2_reuse == 'on':task['stage2_reuse']=True
            if args.stage2_birth_hu == 'on':task['stage2_birth_hu']=True
        if args.logp_eps != .5:
            task['logp_eps'] = args.logp_eps
        if args.use_forget is not None:
            if not (args.v39 and args.v310_be):
                raise SystemExit("--use-forgetは--v39 --v310-beと一緒に使う")
            task["use_forget"] = args.use_forget
        if args.sme2017:
            task["sme2017"] = True
            for opt in ("sme_reuse", "sme_prune", "sme_intern_cache", "sme_evict_trial_cache", "sme_evict_tombstone"):
                if getattr(args, opt):
                    task[opt] = True
            if args.sme_call_seed:
                task["sme_call_seed"] = True
            if args.sme_tie_uniform:
                task["sme_tie_uniform"] = True
            if args.sme_gc_threshold is not None:
                task["sme_gc_threshold"] = args.sme_gc_threshold
            if args.sme_fast_encode:
                task["sme_fast_encode"] = True
            if args.sme_replay is not None:
                task["sme_replay"] = args.sme_replay
        if args.select_n3:
            task["select_n3"] = True
        if args.shop_scatter:
            task["shop_scatter"] = True
        if args.attn_sme:
            task.update(attn_sme=args.attn_sme, attn_position=args.attn_position,
                        attn_eta=args.attn_eta, attn_fixed_zero=args.attn_fixed_zero)
    (out_root / "flag.json").write_text(json.dumps({**{opt: True for opt in ("sme_reuse", "sme_prune", "sme_intern_cache", "sme_evict_trial_cache", "sme_evict_tombstone") if getattr(args, opt)},
                                                    **{opt: True for opt in ("sme_online_candidates", "sme_online_check", "no_forget_exec") if getattr(args, opt)},
                                                    **({"sme_gc_threshold": args.sme_gc_threshold} if args.sme_gc_threshold is not None else {}),
                                                    **({"sme_fast_encode": True} if args.sme_fast_encode else {}),
                                                    **({"score_logp": True, "score_logp_e": args.score_logp_e, "score_logp_epsilon": args.logp_eps} if args.score_logp else {}),
                                                    **cstar_options,
                                                    **({'attn_allin':True} if args.attn_allin else {}),
                                                    **({'stage2_reuse':True} if args.stage2_reuse=='on' else {}),
                                                    **({'stage2_birth_hu':True} if args.stage2_birth_hu=='on' else {}),
                                                    **({'stage2':'on','stage2_loss':args.stage2_loss,'stage2_init':args.stage2_init,'stage2_scope':args.stage2_scope} if args.stage2=='on' else {}),
                                                    **({"attn_sme": args.attn_sme, "attn_position": args.attn_position,
                                                        "attn_eta": args.attn_eta, "attn_fixed_zero": args.attn_fixed_zero} if args.attn_sme else {}),
                                                    **({"sme2017": True} if args.sme2017 else {}),
                                                    **({"sme_call_seed": True} if args.sme_call_seed else {}),
                                                    **({"sme_tie_uniform": True} if args.sme_tie_uniform else {}),
                                                    **({"select_n3": True} if args.select_n3 else {}),
                                                    **({"use_forget": args.use_forget} if args.use_forget is not None else {}),
                                                    **({"shop_scatter": True} if args.shop_scatter else {}),
                                                    **({"score_arg_order": True} if args.score_arg_order else {}), "nohash": args.nohash, "nsim": args.nsim, "vt": args.vt,
                                                    "greedy": args.greedy, "extgreedy": args.extgreedy, "lowmem": args.lowmem,
                                                    "extend_rule": args.extend_rule, "charge1": args.charge1,
                                                    "compare_to": args.compare_to, "dump_slot_history": args.dump_slot_history, "config": args.config,
                                                    "ident_rho": args.ident_rho, "ident_argmax": args.ident_argmax, "ident_shadow": args.ident_shadow,
                                                    "ident_commons": args.ident_commons,
                                                    "fast": args.fast, "nohist": args.nohist, "fix2": args.fix2,
                                                    "fix_order": args.fix_order, "fix_order2": args.fix_order2, "rename_check": args.rename_check, "proj_first": args.proj_first,
                                                    "fix2_full": args.fix2_full, "fill_unseen": args.fill_unseen, "fill_norestate": args.fill_norestate,
                                                    "no_charge2": args.no_charge2, "death_terms": args.death_terms, "checks": args.checks,
                                                    "own_evidence": args.own_evidence,
                                                    "v39": args.v39, "v39_budget": args.v39_budget, "v39_init": args.v39_init,
                                                    "v39_a": args.v39_a, "v39_u": args.v39_u,
                                                    "v39_decay": args.v39_decay, "v39_price": args.v39_price,
                                                    "v310_be": args.v310_be, "hist_role": args.hist_role, "score_role": args.score_role,
                                                    "world_cue": (args.world_cue_p if args.world_cue else None), "dump_answers": args.dump_answers, "dump_routing": args.dump_routing,
                                                    "u_struct": args.u_struct, "relearn_init": args.relearn_init, "tie_struct": args.tie_struct, "amb_local": args.amb_local,
                                                    "answer_gap": args.answer_gap, "probe_world": args.probe_world,
                                                    "shop_world": args.shop_world, "shop_exc": (args.shop_exc if args.shop_world else None), "shop_keep_cue": args.shop_keep_cue,
                                                    "strict_pc": args.strict_pc, "cf_value": args.cf_value, "e_price": args.e_price, "cf_learn": args.cf_learn,
                                                    "v38_from": __import__("os").environ.get("V38_FROM"),   # ★ 検査用の環境変数（本番では None）
                                                    "commit": commit, "driver": "tools/v3_run.py",
                                                    **({"v311c": {"f": args.v311c_f, "groups": args.v311c_groups, "q": args.v311c_q, "m": args.v311c_m,
                                                                  "recv": args.v311c_recv, "runs": args.v311c_runs, "no_tags": args.v311c_no_tags,
                                                                  "probe_every": args.v311c_probe_every,
                                                                  **({"sme_replay": args.v311c_sme_replay} if args.v311c_sme_replay else {}),
                                                                  **{k: True for k in ("probe_shop", "audit", "serial", "lineage")
                                                                     if getattr(args, "v311c_" + k)}}} if args.v311c else {}),
                                                    "workers": args.workers,
                                                    **({"horizon": args.horizon} if args.horizon is not None else {})}) + "\n")
    man = out_root / "manifest.jsonl"
    print(f"{time.strftime('%F %T')} 開始 {cfg['name']} nohash={args.nohash} nsim={args.nsim} vt={args.vt} "
          f"greedy={args.greedy} extgreedy={args.extgreedy} lowmem={args.lowmem} extend={args.extend_rule} charge1={args.charge1} ρ={args.ident_rho} argmax={args.ident_argmax} commons={args.ident_commons} shadow={args.ident_shadow} fix2={args.fix2} fix2_full={args.fix2_full} fix_order={args.fix_order} fix_order2={args.fix_order2} proj_first={args.proj_first} fill_unseen={args.fill_unseen} fill_norestate={args.fill_norestate} no_charge2={args.no_charge2} own_evidence={args.own_evidence} v39={args.v39}/{args.v39_budget}/{args.v39_init}/{args.v39_a}/{args.v39_u} death_terms={args.death_terms} checks={args.checks} rename_check={args.rename_check} fast={args.fast} nohist={args.nohist} 走行 {len(tasks)} 並列 {args.workers} 比べる={do_compare}", flush=True)
    if args.v311c:
        _run_collective(args, tasks, out_root, man)
        print(f"{time.strftime('%F %T')} ALLDONE {cfg['name']}", flush=True)
        return
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

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
        if task.get("v311c"):
            import abm.loop as _loop
            _REAL["m1_before_be"] = _loop.m1   # ★ v3.11c：B＋E の包みの内側（v39 の m1）を控える（集団化の E が名札の費用を足して呼ぶ）
        if task.get("v310_be"):
            # ★ v3.10 B＋E（書き直しの費用で結ぶ統合版、2026-09-29 午後、マック）：tools/v310be.py。v39 の上、削除の段を取る前に入れる
            import v310be
            v310be.install(fo, seed=int(task["seed"]), nohash=bool(task["nohash"]), score_role=bool(task.get("score_role")))
        _REAL["theta_impl"] = v39.CTX["apply"]
        if task.get("v311c"):
            # ★ v3.11c（集団化・事例伝達、2026-09-29 夕）：tools/v311c.py。予測・m1（E）・削除の段の一番外を包む（個体ごとのプロセスで）
            import v311c
            v311c.install(fo, task, _REAL)
    if task.get("world_cue"):
        # ★ 世界 v4（型の変種、2026-09-30 深夜の追記 B-2）：tools/worldvariant.py。世界を作る前に入れる。v39 の固定辞書に新しい述語を足す
        sys.path.insert(0, str(ROOT / "tools"))
        import worldvariant
        worldvariant.install(float(task.get("world_cue_p", 0.8)))
        if "v39" in sys.modules:
            worldvariant.extend_dictionary()
    if task.get("dump_answers"):
        # ★ 答えごとの記録（2026-09-30 朝の委任書の 2・3）：tools/answerlog.py。記録だけ（台帳は変わらない）。ほかの差し替えのあと、世界を作る前に入れる
        if not task.get("v39"):
            raise ValueError("--dump-answers は --v39 と一緒に使う")
        sys.path.insert(0, str(ROOT / "tools"))
        import answerlog
        answerlog.install(side_dir / f"seed{task['seed']:03d}.answers.csv", seed=int(task["seed"]),
                          seed_file=str(ROOT / task["cfg"]["seed_file"]))

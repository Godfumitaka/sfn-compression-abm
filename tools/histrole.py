"""席の履歴の直し（2026-09-29 夜の委任書「物の組で見分ける箇所の洗い出し・席の履歴の直し・直した B＋E の走らせ直し」の 2）：旗 --hist-role。
★ abm/ は変えない。旗を切れば何もしない（v3.10be-main と一字一句同じ）。

m1（abm/abstraction.py:121-140）の席の履歴の集め方のうち、一階の席のものだけを替える。
  今：定義のグラフ（v3.9 の F／H／U の表し方）を場面に写し、席の行の引数を写した物の組（_mapped_arguments）と
      引数が同じ場面の関係を「全部」その席の観察にしている（abstraction.py:137 observed.arguments == position）。
      一つの物の組に一階の関係が何本も乗る世界では、同じ物の組の別の関係の述語も、その席の履歴に入る。
  直し：
    高階の席（二階以上。abm/filling.py _is_higher：引数に同じ定義の行の関係 ID を含む）：今のまま。
    一階の席：物の組で集めるのをやめる。定義の中でその席を子に持つ親の行（引数にその席の関係 ID を持つ行。状態は問わない）が、
      同じ照合（m1 の中の map_graphs の写し）で場面の関係に対応づけられていれば、その場面の関係の同じ位置の子を、その席の観察とする。
      親が対応づけられない（親が無い・写らない・場面の関係に写らない）とき、又は子が場面に見えていないときは、その試行では観察を足さない。推測で足さない。
      親が二つ以上対応づけられたときは、それぞれの親から得た子を観察とする（同じ場面の関係は一度だけ。今の集め方と同じく、場面の関係一本につき一回）。
やり方：abm.abstraction.m1 そのものを包む（一番内側）。元の m1 をそのまま呼び、中の map_graphs の写し（履歴の照合）を控える。
  返ってきた状態の一階の席の履歴を、呼ぶ前の値に戻してから（今の集め方で足した分を取り消す）、上の規則の観察を observe_slot で足す。
  observe_slot は鍵（定義, 席）ごとに独立で、m1 は履歴の照合のあと履歴を読まないので、高階の席の履歴と、ほかの状態は元の m1 と同じになる。
  実際の鎖（tools/v3_run.py の包み → tools/v39.py → tools/v310be.py）と、E の仮の適用（tools/v310be.py hypo_m1 が abm.abstraction.m1 を直に呼ぶ）の両方に効く。
★ v3.8 の開示による席の観察（tools/v38.py）は替えない（委任書は m1 の席の履歴の直し）。
記録：STATS（実際の鎖の m1 だけ。E の仮の適用は数えない）。manifest の rec["histrole"]。
"""
from __future__ import annotations

STATS: dict = {}
CFG: dict = {}       # u_all_orders：tools/ustruct.py（--u-struct）が立てる。U の席は階を問わず親の子の規則で観察する


def _stats_zero():
    return dict(m1_calls=0, m1_registered=0, seats_first=0, seats_higher=0,
                first_no_parent=0, first_parent_unmapped=0, first_child_unseen=0, first_observed=0,
                first_multi_parent_mapped=0, first_multi_child=0,
                obs_old_first=0, obs_new_first=0, obs_new_same_as_old_pred=0,
                births=0, birth_rows=0, birth_first_rows=0, birth_first_parentless=0,
                **{f"first_{k}_{st}{x}": 0 for st in "FHU" for k, x in (("seats", ""), ("obs", ""), ("obs", "_same_pred"))})


def _count(h) -> int:
    from collections.abc import Mapping
    if h is None:
        return 0
    if isinstance(h, Mapping):
        return int(sum(h.values()))
    return len(h)


def make(orig, *, real: bool):
    import abm.abstraction as ab
    from abm.filling import _is_higher, observe_slot

    def m1(state, base, target, alignment, trial, **kw):
        mg = ab.map_graphs
        cap = []

        def capture(g, t, *a, **k):
            res = mg(g, t, *a, **k)
            cap.append((g, t, res))
            return res

        ab.map_graphs = capture
        try:
            out, reg = orig(state, base, target, alignment, trial, **kw)
        finally:
            ab.map_graphs = mg
        if real:
            STATS["m1_calls"] += 1
        if reg is None:
            return out, reg
        R = reg["R"]
        d = out.definitions[R]
        if not cap or cap[-1][0].graph_id != f"definition:{R}" or cap[-1][1] is not target:
            raise RuntimeError(f"--hist-role：m1 の履歴の照合を控えられなかった（試行 {trial}、定義 {R}）")
        al = cap[-1][2].alignment
        lam = kw.get("local_lambda", 0.0)
        rel_ids = {row.relation.relation_id for row in d.constituents}
        t_by_id = {r.relation_id: r for r in target.relations}
        pre = state.slot_history
        hist = dict(out.slot_history)
        S = STATS if real else None
        if S is not None:
            S["m1_registered"] += 1
            if not reg["was_extension"]:
                S["births"] += 1
                S["birth_rows"] += len(d.constituents)
        for row in d.constituents:
            key = (R, row.slot_index)
            if _is_higher(row.relation, rel_ids):
                if not (CFG.get("u_all_orders") and not row.alive and key not in pre):
                    if S is not None:
                        S["seats_higher"] += 1
                    continue
                if S is not None:
                    S["u_higher"] = S.get("u_higher", 0) + 1
            sid = row.relation.relation_id
            old_obs = _count(hist.get(key)) - _count(pre.get(key))
            # 今の集め方で足した分を取り消す（呼ぶ前の値に戻す。呼ぶ前に鍵が無ければ消す）
            if key in pre:
                hist[key] = pre[key]
            else:
                hist.pop(key, None)
            parents = [(p, k) for p in d.constituents for k, a in enumerate(p.relation.arguments) if a == sid]
            kids = []
            mapped = 0
            for p, k in parents:
                Q = t_by_id.get(al.relation_mapping.get(p.relation.relation_id))
                if Q is None or k >= len(Q.arguments):
                    continue
                mapped += 1
                c = t_by_id.get(Q.arguments[k])
                if c is not None and all(c.relation_id != x.relation_id for x in kids):
                    kids.append(c)
            for c in kids:
                hist = observe_slot(hist, R, row.slot_index, c.predicate, lam)
            if S is not None:
                S["seats_first"] += 1
                S["obs_old_first"] += old_obs
                S["obs_new_first"] += len(kids)
                S["obs_new_same_as_old_pred"] += sum(1 for c in kids if c.predicate == row.relation.predicate)
                st = "F" if row.alive else ("H" if key in pre else "U")
                S[f"first_seats_{st}"] += 1
                S[f"first_obs_{st}"] += len(kids)
                S[f"first_obs_{st}_same_pred"] += sum(1 for c in kids if c.predicate == row.relation.predicate)
                if not parents:
                    S["first_no_parent"] += 1
                elif mapped == 0:
                    S["first_parent_unmapped"] += 1
                elif not kids:
                    S["first_child_unseen"] += 1
                else:
                    S["first_observed"] += 1
                S["first_multi_parent_mapped"] += mapped > 1
                S["first_multi_child"] += len(kids) > 1
                if not reg["was_extension"]:
                    S["birth_first_rows"] += 1
                    S["birth_first_parentless"] += not parents
        from dataclasses import replace
        return replace(out, slot_history=hist), reg

    return m1


def install() -> None:
    """tools/v3_run.py の _install より前に呼ぶ（_install が loop.m1 を控えるので、そこに包みが入る）。"""
    import abm.abstraction as ab
    import abm.loop as loop
    STATS.clear()
    STATS.update(_stats_zero())
    orig = ab.m1
    if loop.m1 is not orig:
        raise RuntimeError("--hist-role：loop.m1 が既に差し替えられている（入れる順番の誤り）")
    loop.m1 = make(orig, real=True)      # 実際の鎖（tools/v3_run.py の _install がこれを控える）
    ab.m1 = make(orig, real=False)       # E の仮の適用（tools/v310be.py hypo_m1）

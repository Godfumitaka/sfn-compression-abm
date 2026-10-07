"""C*・Hのディリクレ型・誕生の採点に共通の分布の部品。

背景bの候補と重みは既存のv310beと同じ。α・εの混ぜはここで一回行う。
この段階では既存の予測・採点の入口には差し込まない。
"""
from __future__ import annotations

import math

BACKGROUND_SOURCE = None


def checked_distribution(distribution):
    values = dict(distribution)
    if not values or any(not math.isfinite(p) or p < 0 for p in values.values()):
        raise ValueError("分布の確率が不正")
    if not math.isclose(math.fsum(values.values()), 1.0, abs_tol=1e-12, rel_tol=1e-12):
        raise ValueError("分布の総和が1でない")
    return values


def dirichlet_history(background, counts, alpha=1):
    """n=0でb。名前と回数を保存し直さず、その時点の履歴から計算する。"""
    if alpha != 1:
        raise ValueError("委任書のαは1だけ")
    b = checked_distribution(background)
    counts = dict(counts)
    if any(not isinstance(n, int) or n < 0 for n in counts.values()):
        raise ValueError("履歴の回数が非負の整数でない")
    n = sum(counts.values())
    names = tuple(sorted((set(b) | set(counts)) - {None})) + ((None,) if None in b else ())
    q = {x: (counts.get(x, 0) + alpha * b.get(x, 0.0)) / (n + alpha) for x in names}
    return checked_distribution(q)


def value_distributions(background, history, fixed, epsilon=.5):
    """P_F=(1−ε)δ＋εb、P_H=(1−ε)q_H＋εb、P_U=b。"""
    if not math.isfinite(epsilon) or not 0 <= epsilon <= 1:
        raise ValueError("εが0〜1でない")
    b, q = checked_distribution(background), checked_distribution(history)
    names = tuple(sorted((set(b) | set(q) | {fixed}) - {None}))
    if None in b or None in q or fixed is None:
        names += (None,)
    out = {"U": b,
           "H": {x: (1 - epsilon) * q.get(x, 0.0) + epsilon * b.get(x, 0.0) for x in names},
           "F": {x: (1 - epsilon) * (x == fixed) + epsilon * b.get(x, 0.0) for x in names}}
    for distribution in out.values():
        checked_distribution(distribution)
    return out


def most_probable(distribution):
    """点予測は同じqの最頻名。同点と名の無い分布は棄権する。"""
    dist = checked_distribution(distribution)
    maximum = max(dist.values())
    winners = [name for name, p in dist.items() if p == maximum]
    return (winners[0], None) if len(winners) == 1 and winners[0] is not None else (None, "同点" if len(winners) > 1 else "候補名なし")


def seat_distributions(d, row, state, scene, config, *, alpha=None, epsilon=.5):
    """既存と同じ署名・階のb、履歴のHを作り、qとPを分けて返す。"""
    import v310be
    import v39
    # 既存の部品のUはεにもq_Hにも依存しない。bの定義を複製しない。
    source = BACKGROUND_SOURCE or v310be.probabilities
    b = source(d, row, state, scene, config)["U"]
    h = state.slot_history.get((d.name, row.slot_index))
    q = history_distribution(d,row,state,h,b,config,alpha=alpha)
    belief = {"F": {row.relation.predicate: 1.0}, "H": q, "U": b}
    return {"b": b, "q": belief,
            "P": value_distributions(b, q, row.relation.predicate, epsilon)}


def history_distribution(d,row,state,history,background,config,*,alpha=None):
    """答え・値付け・照合・仮の誕生で同じ履歴の分布を作る。"""
    from collections.abc import Mapping
    from abm.filling import _distribution
    import v39
    hp = v39._order_pool(frozenset(history or ()),d,row,config.higher_order_predicates)
    if alpha is None:
        q = dict(_distribution(hp,state.p_hat,config.local_lambda,history if isinstance(history,Mapping) else None))
        if not q or sum(q.values()) == 0:
            q = background.copy()
    else:
        counts = v39.hist_counts(history)
        counts = {name: counts[name] for name in hp}
        q = dirichlet_history(background,counts,alpha)
    return q


def birth_distributions(background, first_name, second_name, *, mode, alpha=1, epsilon=.5):
    """誕生二材料の手計算用の基準。正解を知らない先頭の予測はbだけ。"""
    b = checked_distribution(background)
    if mode == 'fit' and first_name != second_name:
        # この場合のFの固定名を決め直さない。呼ぶ側が件数と材料を報告する。
        raise ValueError("誕生のFの名前が二材料で一意でない")
    if mode == "fit":
        q = dirichlet_history(b, {first_name: 2}, alpha)
        after = value_distributions(b, q, first_name, epsilon)
        return after, after
    if mode == "seq":
        before = {s: b.copy() for s in ("F", "H", "U")}
        if first_name is None:
            return before, {s: b.copy() for s in ("F", "H", "U")}
        q = dirichlet_history(b, {first_name: 1}, alpha)
        after_first = value_distributions(b, q, first_name, epsilon)
        return before, after_first
    raise ValueError("誕生の採点はfitまたはseq")

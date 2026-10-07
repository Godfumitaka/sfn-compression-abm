"""(a) C* の点の参照の計算：対応 M を固定し、各席の名前の一致・不一致の全場合を列挙して、
通常の SME の点（古い版 tools/sme2017.py をそのまま使う）を確率で平均する。

仕様の出どころ（行番号は results の枝のファイル）：
- 委任書 41 ■2（control/2026-10-06_渡す委任書_Claude.md 789–797 行）：
  「対応 M を一つ固定し、各席 i の『場面の見えている名前 x_i と合う確率』q_i を使う。合わない席は対から外し、
   引数が欠けた親も並行な連結に従って外す。残った部分で今の局所の点と trickle-down を計算した点 S0 の、
   名前の引き方についての期待値を C* の点 S_P とする。各席は独立と置き、同じ席は一度だけ数える」
  「合った場合は、U の席にも通常の名前の局所の点を与える」「伏せられた名前の位置は一致を評価しない（周辺化。
   局所の名前の点は与えない）。物は席ではない」
  「N3 の分母は、名前が全部合った場合の構造の自己の点 T(g)（完全な一対一の自己対応を明示的に採点した値）に固定：
   Q_P＝2 S_P／(T(d)＋T(x))」
- GPT 照合の返事 §3（control/2026-10-06_GPTの返事_照合と分布の統一.md 70–104 行）：S_P(M;d,x)＝E_Z[S0(M;Z,x)]、
  名前を引く前に M を固定、おもちゃの基準値 S_P＝0.1175＋0.877p。
- GPT 照合の返事 §4（134–150 行）：T(g)、伏せた名前の周辺化。
- 委任書 41′ 1（912 行）：確率 0 の名前は C* では q＝0 として候補にしない。
- 委任書 41 ■2（793 行）：候補は q_i＞0 の組（確率のしきい値で切らない）。

上限なし（max_local_score＝None、sme2017 の既定）の点だけを扱う（GPT 照合の返事 §7 223 行：主変更に上限を混ぜない）。
"""
from __future__ import annotations

import itertools
import math
import random
from functools import lru_cache
from typing import Callable, Mapping

from refcommon import (MISMATCH, SETTINGS, Definition, Scene, def_graph, scene_graph, seat_dist, sme2017)


# ---------------------------------------------------------------- 固定した対応の S0（sme2017 の局所の点と trickle-down）
def score_fixed(L, R, pairs: Mapping) -> tuple[float, frozenset]:
    """左の図 L と右の図 R、関係の対 pairs（左の鍵→右の鍵）を固定し、名前が合わない対と、
    引数の対が欠けた親を外した残りの部分対応を、sme2017 の通常の点で採点する。

    - 各対の成立は sme2017 の _Engine._grow（関係の種類・引数の数・名前の共通部分・U/未知の分岐、
      子の対応から親を作る処理）で決める。名前が合わなければ空になり、その対を引数に持つ親も空になる
      （＝委任書 41 ■2「合わない席は対から外し、引数が欠けた親も並行な連結に従って外す」）。
    - parent の印：その対が M の中の他の対の引数として強制されるなら True（sme2017 の _grow の
      parent 引数。関係の種類が "relation" で ubiquitous でない席では効かない）。spec_notes の (a)-曖昧 4。
    - 点：sme2017 の _Engine._scores(members, global_=True) の総和（Candidate.score と同じ計算、
      sme2017.py 556–566 行）。
    返り値：(点, 残った対の集合)。
    """
    eng = sme2017._Engine(L, R, SETTINGS, random.Random(0))
    lb, rb = L.by_id, R.by_id
    forced = set()
    for l, r in pairs.items():
        if lb[l].kind in {"unknown", "entity"} or rb[r].kind in {"unknown", "entity"}:
            continue
        for a, b in zip(lb[l].args or (), rb[r].args or ()):
            if lb[a].kind != "entity":
                forced.add((a, b))
    hyps = {}
    for l, r in pairs.items():
        out = eng._grow(l, r, (l, r) in forced)
        if len(out) > 1:
            raise ValueError(("一つの対に複数の仮説（名前が一つでない）", l, r))
        if out:
            hyps[(l, r)] = out[0]
    members = set()
    for i in hyps.values():
        members |= eng.closures[i]
    members = frozenset(members)
    if not eng._consistent(members):
        raise ValueError("固定した対応が一対一・順つき引数を満たさない")
    scores = eng._scores(members, True)
    return math.fsum(scores.values()), frozenset(hyps)


# ---------------------------------------------------------------- 対応 M の検査
def check_mapping(defn: Definition, scene: Scene, M: Mapping) -> dict:
    """M（席の鍵→場面の関係の鍵。見えている関係か伏せた位置）が構造の制約を満たすかを確かめ、物の対応を返す。
    満たさなければ ValueError。
    - 一対一（席・場面の両側）。
    - 見えている関係への対：引数の数が同じ、各引数は物↔物（一対一）か、席↔場面の関係で、その対が M にある。
    - 伏せた位置への対：見えている親の引数として強制される場合だけ（sme2017 では伏せた位置だけの対は
      局所の点が 0 の核になり、候補にならない。sme2017.py 527–528 行）。spec_notes の (a)-曖昧 5。
    """
    if len(set(M.values())) != len(M):
        raise ValueError("右側が一対一でない")
    vis = {k: (n, tuple(a)) for k, n, a in scene.visible}
    hidden = set(scene.hidden)
    ent = {}
    forced_hidden = set()
    for l, r in M.items():
        s = defn.seat(l)
        if r in vis:
            _n, rargs = vis[r]
            if len(rargs) != len(s.args):
                raise ValueError(("引数の数", l, r))
            for a, b in zip(s.args, rargs):
                if a in defn.seat_keys:
                    if M.get(a) != b:
                        raise ValueError(("引数の対が M に無い", l, r, a, b))
                    if b in hidden:
                        forced_hidden.add(a)
                else:
                    if b not in scene.entities:
                        raise ValueError(("物と関係の対", l, r))
                    if ent.get(a, b) != b:
                        raise ValueError(("物の対応が二通り", a))
                    ent[a] = b
        elif r in hidden:
            pass
        else:
            raise ValueError(("場面に無い鍵", r))
    for l, r in M.items():
        if r in hidden and l not in forced_hidden:
            raise ValueError(("伏せた位置への対が親から強制されていない", l, r))
    if len(set(ent.values())) != len(ent):
        raise ValueError("物の対応が一対一でない")
    return ent


# ---------------------------------------------------------------- S0・S_P
def _names_for(defn: Definition, scene: Scene, M: Mapping, matched: Mapping) -> dict:
    """名前の割り当て：見えている関係に対した席は、合う場合は場面の名前、合わない場合は
    席ごとの別の印。対の無い席・伏せた位置に対した席は印（点に効かない）。"""
    names = {}
    for s in defn.seats:
        r = M.get(s.key)
        x = scene.name_of(r) if r is not None else None
        if x is not None and matched.get(s.key, False):
            names[s.key] = x
        else:
            names[s.key] = MISMATCH + s.key
    return names


def s0(defn: Definition, scene: Scene, M: Mapping, matched: Mapping) -> float:
    """S0(M;Z,x)：一致した席の集合 matched（席の鍵→True/False）を一つ決めたときの点。"""
    L = def_graph(defn, _names_for(defn, scene, M, matched))
    R = scene_graph(scene)
    return score_fixed(L, R, M)[0]


def uncertain_seats(defn: Definition, scene: Scene, M: Mapping) -> list:
    """一致を評価する席：見えている関係に対した席だけ（伏せた位置は周辺化。対の無い席は点に効かない）。"""
    vis = set(scene.visible_keys)
    return [s.key for s in defn.seats if M.get(s.key) in vis]


def cstar_score(defn: Definition, scene: Scene, M: Mapping, q: Mapping, *, return_cases: bool = False):
    """S_P＝Σ_Z Pr(Z)·S0(M;Z,x)。q は席の鍵→「場面の見えている名前と合う確率」。

    各席の一致・不一致の 2^k 通りを全部列挙する（各席は独立、同じ席は一度だけ：委任書 41 ■2）。
    q＝1 の席は常に一致、q＝0 の席は常に不一致として列挙から外す（確率 0 の場合を数えても 0 を足すだけ）。
    """
    check_mapping(defn, scene, M)
    seats = uncertain_seats(defn, scene, M)
    fixed_true = {k: True for k in seats if q[k] >= 1.0}
    fixed_false = {k: False for k in seats if q[k] <= 0.0}
    free = [k for k in seats if 0.0 < q[k] < 1.0]
    total = []
    cases = []
    for bits in itertools.product((True, False), repeat=len(free)):
        pr = 1.0
        matched = dict(fixed_true)
        matched.update(fixed_false)
        for k, hit in zip(free, bits):
            matched[k] = hit
            pr *= q[k] if hit else 1.0 - q[k]
        v = s0(defn, scene, M, matched)
        total.append(pr * v)
        if return_cases:
            cases.append((pr, dict(matched), v))
    sp = math.fsum(total)
    return (sp, cases) if return_cases else sp


def cstar_score_fullnames(defn: Definition, scene: Scene, M: Mapping, P: Mapping) -> float:
    """名前の全場合の列挙版：一致を評価する各席の名前を、その席の分布 P[席] の台（確率＞0 の名前）から
    全部引いて平均する（GPT 照合の返事 §3 70–80 行の定義そのもの）。cstar_score の照らし合わせ用。"""
    check_mapping(defn, scene, M)
    seats = uncertain_seats(defn, scene, M)
    supports = [[(x, p) for x, p in sorted(P[k].items()) if p > 0] for k in seats]
    R = scene_graph(scene)
    acc = []
    for combo in itertools.product(*supports):
        pr = math.prod(p for _x, p in combo)
        names = _names_for(defn, scene, M, {})
        for k, (x, _p) in zip(seats, combo):
            names[k] = x
        acc.append(pr * score_fixed(def_graph(defn, names), R, M)[0])
    return math.fsum(acc)


# ---------------------------------------------------------------- 自己の点 T と Q_P
def T_def(defn: Definition) -> float:
    """T(d)：定義の全ての席に名前を与え、全部合った完全な一対一の自己対応（恒等の対応）を明示的に採点した点。
    F/H/U の札と名前によらない（GPT 照合の返事 §4 134–142 行、§9 関門 7）。席を消せば縮む。
    名前は席ごとに別の仮の名前（"§鍵"）。spec_notes の (a)-曖昧 6。"""
    names = {s.key: "§" + s.key for s in defn.seats}
    g = def_graph(defn, names)
    return score_fixed(g, g, {s.key: s.key for s in defn.seats})[0]


def T_scene(scene: Scene) -> float:
    """T(x)：場面の恒等の自己対応の点。伏せた位置は名前の局所の点 0（sme2017 の unknown の扱い）で、
    親から渡る点は受ける。spec_notes の (a)-曖昧 7。"""
    g = scene_graph(scene)
    ident = {k: k for k in scene.visible_keys}
    ident.update({k: k for k in scene.hidden})
    return score_fixed(g, g, ident)[0]


def q_from_dists(defn: Definition, scene: Scene, M: Mapping, Pmatch: Mapping) -> dict:
    """q_i＝P_i(x_i)：見えている関係に対した席 i の照合用の分布での、場面の名前の確率。"""
    out = {}
    for k in uncertain_seats(defn, scene, M):
        out[k] = Pmatch[k].get(scene.name_of(M[k]), 0.0)
    return out


def match_dists(defn: Definition, b_of: Callable, *, eps: float, alpha: float = 1.0, match_eps: str = "0") -> dict:
    """各席の照合用の分布（委任書 41 ■4 (1)）。b_of(defn, seat) はその席に U が使う b。"""
    return {s.key: seat_dist(s, b_of(defn, s), eps=eps, alpha=alpha, purpose="match", match_eps=match_eps)
            for s in defn.seats}


def Q_P(S_P: float, T_d: float, T_x: float):
    """Q_P＝2 S_P／(T(d)＋T(x))。分母 0 なら None（古い版は N3 の分母 0 の定義を飛ばした：smeshared 339–342 行）。"""
    den = T_d + T_x
    if den == 0:
        return None
    return 2.0 * S_P / den


# ---------------------------------------------------------------- 総当たりの対応探し（(b) の選び直しで使う）
def enumerate_mappings(defn: Definition, scene: Scene, Pmatch: Mapping):
    """構造の制約を満たし、見えている関係への対は q＞0（委任書 41 ■2 794 行、41′ 1）の、全ての対応 M を列挙する。
    空の対応も含む。関係の種類は "relation" だけを扱う（function は (a)-曖昧 8）。"""
    seats = list(defn.seats)
    vis = {k: (n, tuple(a)) for k, n, a in scene.visible}
    targets = list(vis) + list(scene.hidden)

    def ok_pair(s, r):
        if r in vis:
            n, a = vis[r]
            return len(a) == len(s.args) and Pmatch[s.key].get(n, 0.0) > 0.0
        return True

    def rec(i, M, used):
        if i == len(seats):
            try:
                check_mapping(defn, scene, M)
            except ValueError:
                return
            yield dict(M)
            return
        s = seats[i]
        yield from rec(i + 1, M, used)
        for r in targets:
            if r in used or not ok_pair(s, r):
                continue
            M[s.key] = r
            used.add(r)
            yield from rec(i + 1, M, used)
            used.discard(r)
            del M[s.key]

    yield from rec(0, {}, set())


def best_mappings(defn: Definition, scene: Scene, Pmatch: Mapping, *, rel_tol: float = 1e-12):
    """max_M E_Z[S0(M;Z,x)] と、その最大を取る全ての M（総当たり）。
    実装は SME の貪欲な結合の近似なので（委任書 41 ■2 795 行、GPT 四つの判断 §5）、
    これは「数学的に最良の対応」の参照であって、実装の貪欲な照合器の再現ではない。"""
    best, arg = 0.0, []
    for M in enumerate_mappings(defn, scene, Pmatch):
        if not M:
            continue
        sp = cstar_score(defn, scene, M, q_from_dists(defn, scene, M, Pmatch))
        if sp > best * (1 + rel_tol) and not math.isclose(sp, best, rel_tol=rel_tol, abs_tol=1e-15):
            best, arg = sp, [M]
        elif math.isclose(sp, best, rel_tol=rel_tol, abs_tol=1e-15) and sp > 0:
            arg.append(M)
    return best, arg

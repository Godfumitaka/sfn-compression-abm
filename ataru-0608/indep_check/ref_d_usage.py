"""保持 D の「使用」の参照の計算：今の D、C* のもとでの D（使用＝合う確率 q）、D＋注意（使用の重み w）。

仕様の出どころ：
- 受け箱 注意の係_Codex2.md「## 指示 4」（53–63 行）：
  1.「C* のもとでの保持 D の『使用』：選ばれた定義の対応で、その席が場面と合う確率 q を、使用の回数として足す
     （期待値として数える）。今の D の他の決まり（減衰、しきい値 τ、誕生の初期の強さ）は変えない。
     旗を切れば今の D と全バイト一致。」
  2.「保持 D＋注意（台帳 D-04r の (a)）：D の使用を、その席の位置の鍵（k2）の注意の重みで重みづけて数える。
     重み w＝(1＋a_鍵)／(1＋ā)、ā はその学び手の全部の鍵の a の平均（平均の重みが 1 になり、記憶の全体の量が D と
     そろう）。旗 --use-forget-attn。手例の関門：a が全部 0 なら D と全バイト一致、a の平均を変えずに一つの鍵の a を
     上げるとその鍵の席だけ強さが増える。」
- docs/台帳/台帳追記_2026-10-04夕_夜.md 15 行（D-04r）：(a) 照合での使用を注意の重みで重みづけ。
- 今の D（古い版 10cd8bd の tools/useforget.py 1–27 行の説明と 38–61・236–297 行）：
  使用は試行ごとに一回まで。(a) 選ばれた定義（z／N3 の一位。門の判定の前）の採用された照合で、F は固定名が写った
  見えている関係の名と一致、H は写った関係の名が履歴（回数 1 以上）にある。門で黙った試行でも数える。
  (b) 話した答えの名前をその席から取り出した（F の投影・F/H の穴埋め）。数えない：伏せた位置に写っただけ、
  選ばれなかった定義、U の席。誕生の試行に一回の使用、D の判断は誕生の次の試行から。
  強さ S＝16 本の減衰の記録の mean16（v39._pow・mean16、--v39-decay actr なら τ^(−0.5) の重み）。使用のたびに
  今へ減衰させてから足す（v39.rec_add と同じ形）。S＜τ の席は名前をまとめて失う（F は H を経て U まで、H は U）。
- 減衰の 16 本：古い版 abm/accounting.decay_ladder（τ_k＝0.3·(3T/0.3)^(k/15)、係数 exp(−1/τ_k)）、
  重み：v39.actr_weights。
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable, Mapping

from refcommon import Definition, Scene


# ---------------------------------------------------------------- 減衰と強さ（古い版の式をそのまま写す）
def decay_ladder(horizon: int) -> tuple:
    return tuple(math.exp(-1.0 / (0.3 * ((max(horizon * 3, 0.3) / 0.3) ** (k / 15)))) for k in range(16))


def actr_weights(horizon: int) -> tuple:
    taus = [0.3 * ((max(horizon * 3, 0.3) / 0.3) ** (k / 15)) for k in range(16)]
    raw = [t ** -0.5 for t in taus]
    z = sum(raw)
    return tuple(r / z for r in raw)


@dataclass(frozen=True)
class Strength:
    """席の 16 本の記録：値は「試行 t0 の時点」の値。"""
    t0: int
    vec: tuple


def _decayed(rec: Strength | None, t: int, decay) -> list:
    if rec is None:
        return [0.0] * 16
    dt = max(t - rec.t0, 0)
    return [x * (f ** dt) for x, f in zip(rec.vec, decay)]


def strength(rec: Strength | None, t: int, decay, weights=None) -> float:
    """S＝mean16（均等の平均、又は actr の重み）。記録が無ければ 0。"""
    v = _decayed(rec, t, decay)
    if weights is None:
        return sum(v) / 16.0
    return sum(x * k for x, k in zip(v, weights))


def add_use(rec: Strength | None, t: int, inc: float, decay) -> Strength:
    """今へ減衰させてから inc を 16 本に足す（今の D は inc＝1）。"""
    return Strength(t, tuple(x + inc for x in _decayed(rec, t, decay)))


# ---------------------------------------------------------------- 一試行の使用の量
def attn_weight(key, a: Mapping) -> float:
    """w＝(1＋a_鍵)／(1＋ā)。ā は a の表の全部の鍵の単純平均（表が空なら 0）。
    鍵が決まらない席（key が None）は w＝1。鍵が決まるが a の表に無い席は a＝0（初期値）として w＝1/(1＋ā)。
    確定（台帳 D-07h、受け箱 注意の係 指示 5 の A）。spec_notes の (D)-3・4。"""
    if key is None:
        return 1.0
    abar = (math.fsum(a.values()) / len(a)) if a else 0.0
    return (1.0 + a.get(key, 0.0)) / (1.0 + abar)


_NO_KEY = object()


def trial_uses(defn: Definition, M: Mapping, scene: Scene, *, mode: str = "old", q: Mapping | None = None,
               answer_seat: str | None = None, a: Mapping | None = None, key_of: Callable | None = None,
               answer_weight: str = "one") -> dict:
    """選ばれた定義 defn（門の判定の前の一位）の、この試行の各席の使用の量（席の鍵→量）。U の席は入れない。

    mode="old"：今の D。見えている関係に写り、F は固定名＝場面の名、H は場面の名が履歴にあれば 1。
    mode="cstar"：照合の使用＝C* の q_i（その席の照合用の分布で場面の名が出る確率。--match-eps に従う）。
    答えの使用：answer_seat（話した答えの名前を取り出した席。F/H のとき）は 1。
    一試行に一回まで：照合と答えが同じ席なら max を取る（指示関数の和集合の期待値。答えが確かなら 1）。
    a を渡すと D＋注意：照合の使用に w(その席の位置の鍵) を掛ける。答えの使用は answer_weight="one" なら 1、
    "zero_key" なら表に無い鍵（a＝0）として 1/(1＋ā) を掛ける。spec_notes の (D)-曖昧 1・2・5。
    伏せた位置に写っただけの席は 0（今の D と同じ。C* でも伏せた位置は一致を評価しない）。"""
    out = {}
    for s in defn.seats:
        if s.state == "U":
            continue
        inc = 0.0
        r = M.get(s.key)
        x = scene.name_of(r) if r is not None else None
        if x is not None:
            if mode == "old":
                hit = (x == s.fixed) if s.state == "F" else (s.counts().get(x, 0) >= 1)
                inc = 1.0 if hit else 0.0
            elif mode == "cstar":
                inc = float(q[s.key])
            else:
                raise ValueError(mode)
            if a is not None and inc:
                inc *= attn_weight(key_of(scene, r), a)
        if s.key == answer_seat:
            ans = 1.0
            if answer_weight not in ("one", "zero_key"):
                raise ValueError(answer_weight)
            if a is not None and answer_weight == "zero_key":
                ans = attn_weight(_NO_KEY, a)          # 表に無い鍵＝a 0 の重み 1/(1＋ā)
            inc = max(inc, ans)
        out[s.key] = inc
    return out


def step(records: Mapping, t: int, uses: Mapping, decay, R: str) -> dict:
    """一試行の使用を記録に足した新しい表（元は変えない）。鍵は (定義の名前, 席の鍵)。
    量 0 の席は足さない（今の D は使わなかった席の記録に触れない。減衰は読むときに掛かるので結果は同じ）。"""
    out = dict(records)
    for k, inc in uses.items():
        if inc > 0:
            out[(R, k)] = add_use(out.get((R, k)), t, inc, decay)
    return out


def birth(records: Mapping, t: int, R: str, seat_keys, decay) -> dict:
    """誕生（覚え直しを含む）の試行に一回の使用（量 1。注意の重みは掛けない：誕生の初期の強さは変えない）。"""
    out = dict(records)
    for k in seat_keys:
        out[(R, k)] = add_use(None, t, 1.0, decay)
    return out


def forget_targets(memory: list, records: Mapping, t: int, tau: float, decay, weights=None, born: Mapping = ()) -> list:
    """S＜τ の F/H の席（誕生の試行の席は除く）。返り値：(定義, 席, S, 行き先 "U")。
    F は H を経て U まで同じ判断の中で進むので行き先は U（空くビットが 0 以下で候補にならない席は変換されない：
    その判定は実装の側。ここでは対象の席だけを返す）。"""
    out = []
    born = dict(born)
    for d in memory:
        for s in d.seats:
            if s.state == "U":
                continue
            if born.get((d.name, s.key)) == t:
                continue
            S = strength(records.get((d.name, s.key)), t, decay, weights)
            if S < tau:
                out.append((d.name, s.key, S, "U"))
    return out


def uses_from_prediction(pred: dict, memory: list, scene: Scene, *, mode: str, q: Mapping | None = None, a=None,
                         key_of=None, answer_weight: str = "one") -> tuple:
    """ref_delta_r.predict の出力から、選ばれた定義（門の前の一位）の使用を作る。
    答えの席：門を通って答えに使われた定義の答える席のうち、最頻が一つに決まる最初の席（ref_delta_r._spoken と同じ順）。
    返り値：(定義の名前, {席: 量})。選ばれた定義が無ければ (None, {})。"""
    R = pred["selected"]
    if R is None:
        return None, {}
    ev = next(e for e in pred["evals"] if e["R"] == R)
    d = next(x for x in memory if x.name == R)
    ans = None
    if pred["used"] == R and pred["spoken"] is not None:
        for k, P in zip(ev["answer_seats"], ev["answer_dists"]):
            mx = max(P.values())
            top = [x for x, p in P.items() if p == mx]
            if len(top) == 1:
                ans = k
                break
    if mode == "cstar" and q is None:
        raise ValueError("C* の q（選ばれた定義の各席）を渡す。ref_cstar.q_from_dists で作れる")
    return R, trial_uses(d, ev["M"], scene, mode=mode, q=q, answer_seat=ans, a=a, key_of=key_of,
                         answer_weight=answer_weight)

"""(c) 誕生の初期値（委任書 42″ 2・42‴）の参照の計算と、(c′) 誕生の採点（委任書 41 ■4 (2)・41′ 2）の手計算。

(c) 第二段の誕生の初期値（control/2026-10-06_渡す委任書_Claude.md 955–962 行、42‴ 1025–1035 行）：
  - 生まれた定義について、一つ目の材料までの名前の情報を持つ仮の新しい定義を、予測前の記憶に加える
    （41 番の --birth-score seq と同じ情報の規則）。
  - 二つ目の材料の場面で、本人に見えていた関係を一つずつ伏せて仮の問いにし、各席を一段薄くする前後で、
    最終の答えの損（top1、0/ℓ の腕は 0/ℓ の形）の差を出す。
  - 仮の問いの重みは、その位置の種類（ドア／非ドアの二種類：42‴）の問いが、それまでに本人に実際に問われた頻度。
    ドア・非ドアの実際の頻度を、それぞれの種類に入る仮の問いの数で等分する。問いの記録が全く無いときは
    見えている関係に一様。まだ一度も問われていない種類は重み 0。
  - 一つ目の材料は全状態が b で当てるので差に入らない。本人が見ていない名前は正解に使わない。
  - 作った値を、今の A の誕生の初期値と同じ場所・同じ減衰の重みで入れる（入れる所は実装の側。ここでは値だけ）。
  41′ 2（913–918 行）：仮の F の名前は一つ目の材料でその席に観察した名前。一つ目で見えていなかった
  （伏せられ、開示もされていない）席は仮の F に名前を入れず b に戻す。F・H・U は同じ b のスナップショット。
  GPT 四つの判断 §2（93–125 行）。

(c′) 誕生の採点 --birth-score fit|seq（41 ■4 (2) 811 行、41′ 2、41 ■5 の手計算 825 行）：
  fit：二つの材料を観察した後の記憶で両方を採点。seq：一つ目は局所の情報なし（F も H も U も b）、
  二つ目は一つ目だけを観察した仮の記憶で採点。
"""
from __future__ import annotations

import math
from dataclasses import replace
from typing import Callable, Mapping

from refcommon import Definition, Question, Scene, Seat, mix_eps, q_H, seat_dist, thin
from ref_delta_r import Knowledge, Params, predict


# ---------------------------------------------------------------- (c′) 誕生の採点（席自身の名前の局所の損）
def birth_local_bits(state: str, x1: str | None, x2: str, b: Mapping, *, eps: float, alpha: float = 1.0,
                     mode: str = "seq", w1: float = 1.0, w2: float = 1.0) -> float:
    """一つの席の、二つの材料（古い x1・今 x2）での名前の損（ビット）。w1・w2 は減衰の重み（古い材料は元の経験時刻から）。
    x1＝None は一つ目の材料でその席の名前が本人に見えていなかった場合。

    fit：F の固定名・H の履歴は二つの観察の後（F の固定名は x2 と読む。x1≠x2 の fit は仕様に無い：(c)-曖昧 7）。
    seq：一つ目は b、二つ目は F＝固定名 x1（x1 が無ければ b）、H＝履歴 {x1:1}（x1 が無ければ空＝b）、U＝b。
    """
    lg = lambda p: -math.log2(p)
    if state == "U":
        return w1 * (lg(b[x1]) if x1 is not None else 0.0) + w2 * lg(b[x2])
    if mode == "fit":
        counts = {}
        for x in (x1, x2):
            if x is not None:
                counts[x] = counts.get(x, 0) + 1
        P = mix_eps({x2: 1.0}, b, eps) if state == "F" else mix_eps(q_H(counts, b, alpha), b, eps)
        return w1 * (lg(P[x1]) if x1 is not None else 0.0) + w2 * lg(P[x2])
    if mode != "seq":
        raise ValueError(mode)
    first = w1 * lg(b[x1]) if x1 is not None else 0.0
    if x1 is None:
        P2 = dict(b)
    elif state == "F":
        P2 = mix_eps({x1: 1.0}, b, eps)
    else:
        P2 = mix_eps(q_H({x1: 1}, b, alpha), b, eps)
    return first + w2 * lg(P2[x2])


# ---------------------------------------------------------------- (c) 第二段の誕生の初期値
def provisional_definition(shape: Definition, names1: Mapping, *, unseen_state: str = "H_empty") -> Definition:
    """一つ目の材料までの名前の情報を持つ仮の新しい定義（41′ 2 の情報の規則）。
    names1[席]＝一つ目の材料でその席に観察した名前（見えていなければ None）。
    名前のある席：F（固定名＝その名前、履歴 {名前:1}）。名前の無い席：既定は履歴の空の H（q_H＝b に戻る）、
    unseen_state="U" なら U。spec_notes (c)-曖昧 1。"""
    seats = []
    for s in shape.seats:
        x = names1.get(s.key)
        if x is not None:
            seats.append(replace(s, state="F", fixed=x, hist=((x, 1),)))
        elif unseen_state == "H_empty":
            seats.append(replace(s, state="H", fixed=None, hist=()))
        elif unseen_state == "U":
            seats.append(replace(s, state="U", fixed=None, hist=()))
        else:
            raise ValueError(unseen_state)
    return replace(shape, seats=tuple(seats))


def provisional_questions(material2: Scene) -> list:
    """二つ目の材料の場面で、見えていた関係を一つずつ伏せた仮の問い：(場面, 問い) の並び。
    伏せた関係が他の見えている関係の引数なら、伏せた位置（unknown）として場面に残す。"""
    out = []
    for k, x, a in material2.visible:
        vis = tuple(v for v in material2.visible if v[0] != k)
        referenced = any(k in va for _vk, _vx, va in vis)
        hidden = tuple(material2.hidden) + ((k,) if referenced else ())
        out.append((Scene(material2.entities, vis, hidden), Question(k, tuple(a), x)))
    return out


def question_weights(questions: list, kinds: list, asked: Mapping) -> list:
    """42‴ 3：ドア・非ドアの実際の頻度を、各種類に入る仮の問いの数で等分。問いの記録が全く無ければ一様。
    「頻度」は割合（ドアの回数／全回数）と読む（spec_notes (c)-曖昧 3）。kinds[i] は "door" か "nondoor"。"""
    K = len(questions)
    total = sum(asked.get(t, 0) for t in ("door", "nondoor"))
    if K == 0:
        return []
    if total == 0:
        return [1.0 / K] * K
    cnt = {t: kinds.count(t) for t in ("door", "nondoor")}
    return [(asked.get(t, 0) / total) / cnt[t] for t in kinds]


def birth_init(memory: list, shape: Definition, names1: Mapping, material2: Scene, kn: Knowledge, params: Params,
               *, asked: Mapping, is_door: Callable, loss: str = "top1", unseen_state: str = "H_empty") -> dict:
    """生まれた定義の各席の第二段の初期値＝Σ_仮の問い w_v·[r(薄くした仮の定義を加えた記憶) − r(仮の定義を加えた記憶)]。
    loss は "top1"（log P の腕）か "zero_ell"（0/ℓ の腕）。memory は予測前の記憶（変えない）。
    is_door(場面, 問い) は本人に見えている情報と、それまでの開示だけで決める分類（42‴ 2。既定の読みは
    door_kind_by_disclosed）。返り値：{"init": {席: 値}, "table": [...]}。"""
    prov = provisional_definition(shape, names1, unseen_state=unseen_state)
    qs = provisional_questions(material2)
    kinds = ["door" if is_door(sc, q) else "nondoor" for sc, q in qs]
    ws = question_weights(qs, kinds, asked)
    p = replace(params, loss=loss)
    init = {s.key: 0.0 for s in prov.seats}
    table = []
    for (sc, q), kind, w in zip(qs, kinds, ws):
        base = predict(list(memory) + [prov], sc, q, kn, p)
        for s in prov.seats:
            t = thin(s)
            if t is None:
                continue
            alt = predict(list(memory) + [prov.replace_seat(t)], sc, q, kn, p)
            d = alt["r"] - base["r"]
            init[s.key] += w * d
            table.append({"question": q.key, "y": q.y, "kind": kind, "w": w, "seat": s.key, "state": s.state,
                          "r_before": base["r"], "r_after": alt["r"], "delta": d,
                          "used_before": base["used"], "used_after": alt["used"]})
    return {"init": init, "table": table, "weights": dict(zip([q.key for _s, q in qs], ws)),
            "kinds": dict(zip([q.key for _s, q in qs], kinds))}


def door_kind_by_disclosed(door_answer_names: set) -> Callable:
    """42‴ 2 の例の読み：その関係の名前が、それまでにドアの課題の答えとして開示されたことがあればドア。"""
    return lambda scene, q: q.y in door_answer_names

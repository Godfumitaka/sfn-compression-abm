"""独立点検の参照の計算：共通の部品（記憶・場面の形、分布、符号長、sme2017 の図への変換）。

この参照は、仕様（委任書 41・41′・42・42′・42″・42‴・42⁗・42⁵、受け箱の注意の係の指示 2、
GPT の返事三通）だけから書いた。新しい版の実装のコードは読んでいない（reading_log.md）。
通常の SME の点は、古い版 10cd8bd の tools/sme2017.py（blob 03dfbadeb7977722120ecb54e71a2854e0918f75）を
そのまま import して使う（委任書の指示 1 (a)）。ファイルは変えない。

速さは考えない。総当たりで書く。
"""
from __future__ import annotations

import hashlib
import math
import os
import sys
from dataclasses import dataclass, field, replace
from typing import Callable, Mapping

SME2017_DIR = os.environ.get("SME2017_DIR", "/home/tatsu/sfn/audit/_read/smeevict/tools")
SME2017_BLOB = "03dfbadeb7977722120ecb54e71a2854e0918f75"
if SME2017_DIR not in sys.path:
    sys.path.insert(0, SME2017_DIR)
import sme2017  # noqa: E402  （古い版のまま。変えない）


def sme2017_blob_sha() -> str:
    """読み込んだ sme2017.py の git blob の SHA-1（版の確かめ用）。"""
    with open(os.path.join(SME2017_DIR, "sme2017.py"), "rb") as fh:
        data = fh.read()
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


# ---------------------------------------------------------------- 記憶と場面の形
@dataclass(frozen=True)
class Seat:
    """定義の一つの席（関係）。

    state: "F"（固定名 fixed と履歴 hist）、"H"（履歴 hist）、"U"（名前の情報なし）。
    hist は席の履歴の回数 n_x（(名前, 回数) の組）。F→H では hist を残し、H→U で消す
    （古い版 v39.py の説明文 1 の三段。委任書 42 ■1「今の保持の候補と同じ一段」）。
    args は物の鍵か、同じ定義の席の鍵（順つき）。
    """
    key: str
    args: tuple
    state: str
    fixed: str | None = None
    hist: tuple = ()
    kind: str = "relation"
    ubiquitous: bool = False
    slot: int = 0

    def __post_init__(self):
        if self.state not in {"F", "H", "U"}:
            raise ValueError(self.state)
        if self.state == "F" and not self.fixed:
            raise ValueError("F は固定名を持つ")
        if self.state != "F" and self.fixed is not None:
            raise ValueError("F 以外は固定名を持たない")
        if self.state == "U" and self.hist:
            raise ValueError("U は履歴を持たない")

    def counts(self) -> dict:
        return {x: int(n) for x, n in self.hist}


@dataclass(frozen=True)
class Definition:
    name: str
    registered_at: int
    entities: tuple
    seats: tuple

    def seat(self, key) -> Seat:
        return next(s for s in self.seats if s.key == key)

    @property
    def seat_keys(self):
        return {s.key for s in self.seats}

    def n_FH(self) -> int:
        """門の分母：F＋H の席の数（委任書 41′ 3、古い版 v39.n_FH）。"""
        return sum(s.state != "U" for s in self.seats)

    def replace_seat(self, new: Seat) -> "Definition":
        return replace(self, seats=tuple(new if s.key == new.key else s for s in self.seats))


@dataclass(frozen=True)
class Scene:
    """本人に見えている場面。

    visible: (鍵, 名前, 引数) の組。hidden: 見えている親の引数として現れる、名前の見えない関係の鍵
    （sme2017 では kind="unknown"・args=None の節。古い版 smeshared.typed_graph と同じ扱い）。
    """
    entities: tuple
    visible: tuple
    hidden: tuple = ()

    def name_of(self, key):
        for k, n, _a in self.visible:
            if k == key:
                return n
        return None

    def args_of(self, key):
        for k, _n, a in self.visible:
            if k == key:
                return tuple(a)
        return None

    @property
    def visible_keys(self):
        return [k for k, _n, _a in self.visible]


@dataclass(frozen=True)
class Question:
    """問い（開示された正解 y を持つ）。key は場面での鍵、args は引数（物か場面の関係の鍵）。"""
    key: str
    args: tuple
    y: str
    door: bool | None = None


def thin(seat: Seat) -> Seat | None:
    """一段薄くする：F→H（履歴は残す）、H→U（履歴を消す）。U は薄くできない（None）。
    委任書 42 ■1「一段薄くした記憶（F→H、H→U。今の保持の候補と同じ一段）」。"""
    if seat.state == "F":
        return replace(seat, state="H", fixed=None)
    if seat.state == "H":
        return replace(seat, state="U", hist=())
    return None


# ---------------------------------------------------------------- 分布
def normalize(d: Mapping) -> dict:
    z = math.fsum(d.values())
    if z <= 0:
        raise ValueError("総和が 0 の分布")
    return {k: v / z for k, v in d.items()}


def q_H(counts: Mapping, b: Mapping, alpha: float = 1.0) -> dict:
    """H のディリクレ型：q_H(x)＝(n_x＋α·b(x))／(n＋α)。委任書 41 ■3、GPT 照合の返事 §5（158 行）。
    n＝0 なら b に戻る（GPT 照合の返事 §9 関門 1）。"""
    n = math.fsum(counts.values())
    keys = set(b) | {x for x, c in counts.items() if c > 0}
    return {x: (counts.get(x, 0) + alpha * b.get(x, 0.0)) / (n + alpha) for x in keys}


def mix_eps(core: Mapping, b: Mapping, eps: float) -> dict:
    """(1−ε)·core＋ε·b。GPT 照合の返事 §5（168–170 行）、四つの判断 §1（37–38 行）。"""
    keys = set(core) | set(b)
    return {x: (1 - eps) * core.get(x, 0.0) + eps * b.get(x, 0.0) for x in keys}


def seat_dist(seat: Seat, b: Mapping, *, eps: float, alpha: float = 1.0, purpose: str = "score",
              match_eps: str = "0") -> dict:
    """席の予測分布。

    purpose="score"（値付け・答え・注意の m・第二段の損）：
        P_F＝(1−ε)δ_f＋εb、P_H＝(1−ε)q_H＋εb、P_U＝b（GPT 照合の返事 §5 168–170 行、委任書 41 ■3）。
    purpose="match"（C* の照合の q）：
        match_eps="0" なら F は固定名に 1・他 0、H は q_H、U は b（委任書 41 ■4 (1)）。
        match_eps="shared" なら値付けと同じ P（同上）。
    b はその席に U が使う分布（腕 L の絞った b。呼ぶ側が渡す）。
    """
    if seat.state == "U":
        return dict(b)
    if seat.state == "F":
        core = {seat.fixed: 1.0}
    else:
        core = q_H(seat.counts(), b, alpha)
    if purpose == "match" and match_eps == "0":
        return dict(core)
    if purpose == "match" and match_eps != "shared":
        raise ValueError(match_eps)
    return mix_eps(core, b, eps)


# ---------------------------------------------------------------- 符号長（古い版 v39.py 71–108 行の規則を仕様として写す）
def code_lengths(p_hat_counts: Mapping) -> dict:
    """L(p)＝ceil(−log2(N_p/N))。語彙一つなら 0（v39.code_lengths）。"""
    vocab = {p: n for p, n in p_hat_counts.items() if n > 0}
    N = sum(vocab.values())
    if len(vocab) <= 1:
        return {p: 0 for p in vocab}
    return {p: int(math.ceil(-math.log2(n / N))) for p, n in vocab.items()}


def L_of(p: str, L: Mapping) -> int:
    """退避符号の長さ：未観察の名前は max(L)＋1（v39.L_of）。委任書 41′ 1・42″ 1・42⁵ 1 の「今の規則」。"""
    v = L.get(p)
    if v is None:
        return max(L.values(), default=0) + 1
    return v


def p_hat_dist(p_hat_counts: Mapping) -> dict:
    """本人の全体の名前の頻度表 p̂（形と階で絞らない）。委任書 42⁵ 1。"""
    return normalize({p: float(n) for p, n in p_hat_counts.items() if n > 0})


def bits_of(P: Mapping, y: str, L: Mapping) -> tuple[float, bool]:
    """−log2 P(y)。P(y)＝0 なら L_of の退避符号の長さ（委任書 42″ 1）。返り値 (ビット, 退避したか)。"""
    p = P.get(y, 0.0)
    if p > 0:
        return -math.log2(p), False
    return float(L_of(y, L)), True


# ---------------------------------------------------------------- sme2017 の図への変換
MISMATCH = "⟂"   # 「場面の名前と合わない」名前の代わり（席ごとに別の印にする）


def def_graph(defn: Definition, names: Mapping) -> "sme2017.Graph":
    """名前の割り当て Z（席の鍵→名前）を入れた定義の図。全席を F（名前一つ）として渡す。
    C* では各場合に名前が決まっているので、F/H/U の札は点に効かない（GPT 照合の返事 §3 86 行）。"""
    nodes = [sme2017.Node(e, "entity") for e in defn.entities]
    for s in defn.seats:
        nodes.append(sme2017.Node(s.key, s.kind, frozenset({names[s.key]}), tuple(s.args), "F", s.ubiquitous))
    return sme2017.Graph(tuple(nodes))


def scene_graph(scene: Scene, ubiquitous: frozenset = frozenset()) -> "sme2017.Graph":
    """場面の図。伏せた位置は kind="unknown"（名前も引数も持たない。sme2017 の決まり）。"""
    nodes = [sme2017.Node(e, "entity") for e in scene.entities]
    for k, n, a in scene.visible:
        nodes.append(sme2017.Node(k, "relation", frozenset({n}), tuple(a), "F", k in ubiquitous))
    for k in scene.hidden:
        nodes.append(sme2017.Node(k, "unknown", args=None))
    return sme2017.Graph(tuple(nodes))


SETTINGS = sme2017.Settings()

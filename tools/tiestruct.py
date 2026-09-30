"""同点の並べ方（旗 --tie-struct）。2026-09-30 午後の追記「U の照合の直しの続きに、同点の並べ方の直しを足す」。
★ abm/ は変えない。旗を切れば何もしない。ほかの旗と独立に使える（--v39 の変換の段に効く）。
今：変換の同点の候補を（定義の名前, 席の番号, 種類）で並べてから、独立の乱数（種・試行・変換の番号）で添え字を一つ引く（tools/v39.py:859-866 _pick）。
  定義の名前は述語の名前の sha256、席の番号は誕生の対を関係の ID の順に並べて振った番号なので、名前や番号の付け替えで選ばれる席が変わる。
直し：同点の候補を、構造だけで決まる鍵で並べてから、今と同じ独立の乱数で一つ選ぶ。
  鍵＝（定義が生まれた試行, 席の階, 親の（述語, 引数の位置）の並び, 種類 F→H／H→U）。
    階：一階＝1、高階＝1＋子の行の階の最大（定義の中の行で数える）。
    親の述語の順：模型の固定辞書の並び（種の marginal の順、tools/v39.py の dict_index）。辞書の外の名（墓石の「⟨消去⟩」など）は −1。
      ★ 仕様は「親の述語」までで、述語どうしの順は決めていない。文字列の順だと名前の付け替えで順が変わるので、辞書の順にした。
    親が無い席は空の並び。親が二つ以上なら（辞書の位置, 引数の位置）を並べたもの。
  鍵が同じ候補が残ったときは、今の並び（定義の名前, 席の番号, 種類）で並べる（その回数を STATS tie_struct_unresolved に数える）。
状態は変換の段の中で一段ずつ変わる（F→H で行の述語が消える）ので、鍵はその段の状態で作る。
"""
from __future__ import annotations

from hashlib import sha256
from random import Random

STATS: dict = {}
TCTX: dict = {}


def _levels(d):
    rel_ids = {row.relation.relation_id: row for row in d.constituents}
    memo = {}

    def lv(rid, seen=()):
        if rid in memo:
            return memo[rid]
        row = rel_ids[rid]
        kids = [a for a in row.relation.arguments if a in rel_ids and a not in seen]
        v = 1 + max((lv(a, seen + (rid,)) for a in kids), default=0)
        memo[rid] = v
        return v
    return {row.slot_index: lv(row.relation.relation_id) for row in d.constituents}


def struct_key(state, c):
    import v39
    _V, kind, R, slot = c[0], c[1], c[2], c[3]
    d = state.definitions[R]
    idx = v39.CFG.get("dict_index") or {}
    row = next(r for r in d.constituents if r.slot_index == slot)
    rid = row.relation.relation_id
    parents = sorted((idx.get(p.relation.predicate, -1), k) for p in d.constituents for k, a in enumerate(p.relation.arguments) if a == rid)
    return (d.registered_at, _levels(d)[slot], tuple(parents), kind)


def install() -> None:
    import v39
    STATS.clear()
    TCTX.clear()
    STATS.update(tie_groups=0, tie_struct_unresolved=0)
    real_rc = v39.run_conversions

    def run_conversions(state, trial):
        TCTX["state"] = state
        try:
            return real_rc(state, trial)
        finally:
            TCTX.pop("state", None)

    v39.run_conversions = run_conversions
    real_convert = v39._convert

    def _convert(state, kind, R, slot, trial):
        out = real_convert(state, kind, R, slot, trial)
        TCTX["state"] = out[0]
        return out

    v39._convert = _convert

    def _pick(cands, trial, k):
        vmin = min(c[0] for c in cands)
        tied = [c for c in cands if c[0] == vmin]
        if len(tied) == 1:
            return tied[0], 1
        rnd = Random(int.from_bytes(sha256(f"v39-tie\x1f{v39.CFG['seed']}\x1f{trial}\x1f{k}".encode()).digest()[:8], "big"))
        st = TCTX["state"]
        keyed = [(struct_key(st, c), (c[2], c[3], c[1]), c) for c in tied]
        STATS["tie_groups"] += 1
        if len({x[0] for x in keyed}) < len(keyed):
            STATS["tie_struct_unresolved"] += 1
        keyed.sort(key=lambda x: (x[0], x[1]))
        return keyed[rnd.randrange(len(keyed))][2], len(keyed)

    v39._pick = _pick

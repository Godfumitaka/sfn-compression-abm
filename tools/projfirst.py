"""穴埋めの同点で投影を捨てる件の直し（2026-09-26 夜、アストラさんの指示）。旗 --proj-first（既定オフ）。★ abm/ は変えない。

今の動き（旗オフ、abm/agent_runtime.py:125-170）
  話す定義が決まると、まず投影（project、:125-130）、次に穴埋め（fill_missing_slots、:135-146）を行う。
  穴埋めが同点（filling.ambiguous）なら、投影が一本出ていても棄権する（ambiguous_projection、:158-159）。
直し（旗オン）
  投影が一本出ていれば（EdgePrediction）、穴埋めが同点でも投影を使う（:169-170 の分岐に進み、経路は projection）。
  理由（アストラさん）：生きている行は死んでいないので、メモ帳（墓石の席の履歴からの穴埋め）より優先する。
  投影が出ていない（棄権）ときは今と同じ（穴埋めが同点なら棄権）。
入れ方：agent_runtime の名前 project と fill_missing_slots を包む。project の結果を控え、直後の fill_missing_slots の結果が同点で、
  控えた投影が一本出ていれば、結果の ambiguous だけを False にして返す（ほかの欄は変えない）。predict の中身は写さない。
  loop.py などほかのモジュールの project・fill_missing_slots には触れない（予測の中だけに効く）。
"""
from __future__ import annotations

STATS: dict = {}


def install() -> None:
    from dataclasses import replace
    import abm.agent_runtime as ar
    from abm.domains import EdgePrediction

    STATS.clear()
    STATS.update(projections=0, fill_ambiguous=0, kept_projection=0)
    real_project = ar.project
    real_fill = ar.fill_missing_slots
    last: dict = {}

    def project(*a, **k):
        res = real_project(*a, **k)
        last["proj"] = res
        STATS["projections"] += isinstance(res, EdgePrediction)
        return res

    def fill_missing_slots(*a, **k):
        res = real_fill(*a, **k)
        proj = last.pop("proj", None)
        if res.ambiguous:
            STATS["fill_ambiguous"] += 1
            if isinstance(proj, EdgePrediction):
                STATS["kept_projection"] += 1
                return replace(res, ambiguous=False)
        return res

    ar.project = project
    ar.fill_missing_slots = fill_missing_slots

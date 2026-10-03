"""時間の幅の旗 --horizon H（委任書 2026-10-03「時間の幅の旗」）。★ abm/ は変えない（外側から差し込む。ほかの旗と同じ作り）。旗を切れば何もしない。
付けたとき、時間の幅として走行の長さ T を使う次の所だけ、T の代わりに H を使う：
  1 古さの重みのはしご（abm/accounting.py:71,75 decay_ladder）のうち、v39 の時間の設定が持つもの（tools/v39.py:987 の CFG["decay"]）。
  2 平均の重み（tools/v39.py:220,222 actr_weights。--v39-decay actr のとき tools/v39.py:995 の CFG["mean_weights"]）。
  3 v39 の時間の設定（tools/v39.py:970〜995）：上の 1・2。v39 の古さの重みの冪の控え（_POW）は空にして作り直させる。
  4 誕生の初期の成績（abm/loop.py:114 → abm/abstraction.py:67,118 → abm/accounting.py:84,86 initial_merit の horizon）：
    abm/abstraction.py が取り込んだ名前 initial_merit を包み、horizon を H に替える。
T のまま残す所（時間の幅以外の目的、又は委任書の四か所に無い経路。場所を記録する。変えない）：
  ・tools/v39.py:124 と tools/strictpc.py:356：定義の構造の記憶費用の clog2(CFG["T"])（CFG["T"] は実際の T のまま）。
  ・abm/loop.py:93 → abm/loop.py:187,197（_update_accounting の update_merit が使う decay_ladder(len(world.trials))）。
  ・abm/loop.py:119 → abm/deletion.py:17,23,25（削除。β が 0 でないときの decay_ladder）、tools/deathterms.py:32,33。
  ・tools/v39.py:1018,1021 ほかの会計の包み（horizon を内側へ渡すだけ）、tools/probeworld.py の診断の末尾の時刻、世界の生成・台帳の見出し。
入れる所：tools/v3_run.py worker の v39.install の直後（v310be ほかより前）。"""
from __future__ import annotations

STATS: dict = {}


def install(H: int) -> None:
    import abm.abstraction as ab
    import v39
    from abm.accounting import decay_ladder
    H = int(H)
    if H <= 0:
        raise ValueError("--horizon は正の整数")
    STATS.clear()
    STATS.update(H=H, T=v39.CFG.get("T"))
    v39.CFG["decay"] = decay_ladder(H)
    v39._POW.clear()
    if "mean_weights" in v39.CFG:
        v39.CFG["mean_weights"] = v39.actr_weights(H)
    real = ab.initial_merit

    def initial_merit(slot_index, registered_at, base_age, horizon):
        return real(slot_index, registered_at, base_age, H)

    ab.initial_merit = initial_merit

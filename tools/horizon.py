"""時間の幅の旗 --horizon H（委任書 2026-10-03「時間の幅の旗」と、その続き）。★ abm/ は変えない（外側から差し込む。ほかの旗と同じ作り）。旗を切れば何もしない。
目的：エージェントの振る舞いが実験の長さに依存しないこと。付けたとき、模型の中で走行の長さ T を使う所は全部 H を使う：
  1 古さの重みのはしご（abm/accounting.py:71,75 decay_ladder）：関数そのものを「引数によらず decay_ladder(H)」に替える。
    名前で取り込んだ所も替える：abm/loop.py:12（旧会計 abm/loop.py:93 → :187,197）、abm/deletion.py:7（削除の入口 abm/loop.py:119 → :17,23,25）。
    abm/accounting.py の中の呼び出し（:86 initial_merit＝誕生の初期の成績、abm/loop.py:114 → abm/abstraction.py:67,118 の経路）と、
    呼ぶときに abm.accounting から取り込む tools/deathterms.py:21,33 は、関数を替えたことで H になる。
  2 v39 の時間の設定（tools/v39.py:970〜995）：古さの重み CFG["decay"]（:987）を decay_ladder(H)、平均の重み CFG["mean_weights"]（:995、
    tools/v39.py:220,222 actr_weights）を actr_weights(H) に。冪の控え _POW は空にして作り直させる。
  3 構造の記憶費用の clog2(T)（tools/v39.py:124、tools/strictpc.py:356。どちらも呼ぶときに v39.CFG["T"] を読む）：CFG["T"] を H に。
    v39 の STATS の cfg（tools/v39.py の install の末尾で写す記録）は、install の時点の値（実際の T）のまま。
  会計・削除の包み（tools/v39.py:1018,1021 ほか）は horizon を内側へ渡すだけなので、1 で H になる。
実際の T のまま残す所：世界の生成・台帳の見出し・走行の結果の試行数（sweep.py・abm/world.py・abm/ledger.py・abm/loop.py:45,126,155）、
  診断の末尾の時刻（tools/v3_run.py:497 → tools/probeworld.py）。
入れる所：tools/v3_run.py worker の v39.install の直後（v310be ほかより前）。"""
from __future__ import annotations

STATS: dict = {}


def install(H: int) -> None:
    import abm.accounting as acc
    import abm.deletion as dele
    import abm.loop as loop
    import v39
    H = int(H)
    if H <= 0:
        raise ValueError("--horizon は正の整数")
    STATS.clear()
    STATS.update(H=H, T=v39.CFG.get("T"))
    real = acc.decay_ladder
    ladder = real(H)

    def decay_ladder(horizon):
        return ladder

    acc.decay_ladder = decay_ladder
    loop.decay_ladder = decay_ladder
    dele.decay_ladder = decay_ladder
    v39.CFG["decay"] = ladder
    v39._POW.clear()
    if "mean_weights" in v39.CFG:
        v39.CFG["mean_weights"] = v39.actr_weights(H)
    v39.CFG["T"] = H

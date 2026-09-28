"""v3.7（2026-09-28、委任書「v3.7（② の罰をやめる）」、アストラさんの決定 案1）：旗 --no-charge2。
loop.classify_row を包み、元の判定が「②」なら「③」を返す。★ abm/ は変えない。旗を切れば何もしない（v3.5 と一字一句同じ）。

classify_row を呼んでいるのは abm/loop.py:250（_update_accounting の中）の一か所だけ（abm/・tools/ を探した。2026-09-28）。
そこでの判定の使い道と、この包みで変わること：
  (1) 記録 constituent_reason_123：② だった行が ③ と書かれる（台帳の欄が変わる）。
  (2) 功績の更新 update_merit(matched=reason == "充足")：② も ③ も matched=False なので変わらない（分子 0・分母 +1）。
  (3) 未決の主張（config.pending_claims がオンのときの ③）：本番の設定ではオフ（config の fixed に鍵が無く、sweep.py:195 の既定 False）。
      オンなら ③ から主張が立つので、この旗は使わないこと。
  (4) ② の罰：例外費用の課金・charge_source の「②」と「衝突」・type2_fired。これが無くなる。
参加率は ② のときと同じになる（(2) のとおり）。① と棄権課金の判定は classify_row を使わないので変わらない。"""
from __future__ import annotations

STATS: dict = {"calls": 0, "two_to_three": 0}
_REAL: dict = {}


def install() -> None:
    import abm.loop as loop

    real = _REAL.setdefault("classify_row", loop.classify_row)
    STATS.update(calls=0, two_to_three=0)

    def classify_row(row, scene, entity_mapping, relation_mapping):
        STATS["calls"] += 1
        reason = real(row, scene, entity_mapping, relation_mapping)
        if reason == "②":
            STATS["two_to_three"] += 1
            return "③"
        return reason

    loop.classify_row = classify_row

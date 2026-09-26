"""public_history を状態から外す試し（2026-09-26。旗 --no-public-history、既定オフ）。★ abm/ は変えない。
★ public_history はエージェントも解析の道具も読まない（agent_runtime.py:268・:288 で積むだけ）。
★ 外し方：
   1 update（agent_runtime.py:263-294）の後で public_history を () に戻す。予測・会計・m1・削除には一切効かない。
   2 状態の正準形から public_history の欄を落とす（_SNAPSHOT_OMIT_IF_EMPTY に足す。空のときだけ落ちる）。
     → 状態の指紋は「外す前の状態から public_history の欄だけを除いたもの」の指紋になる。
★ lowmem・fastledger は install の時点で _SNAPSHOT_OMIT_IF_EMPTY を読むので、それより先に install すること。
"""
from __future__ import annotations

from dataclasses import replace


def install() -> None:
    import abm.loop as loop

    loop._SNAPSHOT_OMIT_IF_EMPTY = frozenset(loop._SNAPSHOT_OMIT_IF_EMPTY | {"public_history"})
    real_update = loop.update

    def update(pending, feedback):
        return replace(real_update(pending, feedback), public_history=())

    loop.update = update

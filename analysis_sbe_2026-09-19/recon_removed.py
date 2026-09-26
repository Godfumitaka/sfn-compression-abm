#!/usr/bin/env python3
"""OO-2  MultisetReconstructor に 計装1（definition_removed）への対応だけを足す。
★★ 位置対応の論理（ordered_signature の zip・raw_identity の照合・例外の条件）には一切触れない。
★ 元のクラスを継承し、登録の記帳が済んだあと（_materialize の直前）に
  「消えた定義の登録メタデータ」を落とすだけ。
★ 同じ試行で 登録→削除→definition_removed が並ぶため（実測 試行19）、
  落とすのは registration の記帳より後でなければならない。"""
from __future__ import annotations
import pathlib,sys
ROOT=pathlib.Path("/Users/tatsu-admin/sfn/sfn-compression-abm")
sys.path.insert(0,str(ROOT)); sys.path.insert(0,str(ROOT/"analysis_v3a2cf_2026-09-17"))
from rext_port_stage1 import MultisetReconstructor

class MultisetReconstructorWithRemoval(MultisetReconstructor):
    """★ 計装1 に対応した版。★ 追加は下の 2 メソッドのみ。"""
    def consume(self, row, *, verify_world: bool = True):
        self._pending_removals = tuple(
            event["R"] for event in (row.get("reg_del_events") or ())
            if event.get("kind") == "definition_removed")
        return super().consume(row, verify_world=verify_world)

    def _materialize(self, t):
        for name in getattr(self, "_pending_removals", ()):
            self.registration_rows.pop(name, None)
            if name in self.definition_order: self.definition_order.remove(name)
            self.statistics["definitions_removed"] = self.statistics.get("definitions_removed", 0) + 1
        self._pending_removals = ()
        return super()._materialize(t)

#!/usr/bin/env python3
"""台帳から §3 の各読みを計算する共通モジュール。読み取りのみ。

構造の出典（規範22）
  abm/loop.py:517  reg_del_events = [registration, *deletions]  ★ 登録が先
  abm/loop.py:511  constituent_states = _constituent_states(state)
                   ★ state は apply_theta 適用後。よって試行末の生死である
  abm/loop.py:_constituent_states  生存行と墓石行の両方を列挙する
  abm/abstraction.py:147-163  registration の m_live は登録直後（同試行の削除前）
  abm/deletion.py:56  deletion の欄は kind/R/slot_index/registered_at/trial/V
  abm/loop.py:459-465  state_snapshot の kind は full / skipped / delta
                       ★ skipped は「記録省略」であって「変化なし」ではない
                       ★ snapshot_every=1 の走行では発生しない（loop.py:117-123）
  abm/loop.py:479  hit は整数（int(score.hit)）。トップ階層にある
  abm/loop.py:441  abstain_reason は Abstain のときだけ非 None
"""
import collections, gzip, json


def scan_ledger(path):
    """一走行を読み、R ごとの系列と走行全体の計数を返す。"""
    end = collections.defaultdict(list)     # R -> [(t, L(t))]  L は 0 を含む
    reg = collections.defaultdict(list)     # R -> [(t, 登録時 m_live)]
    rows = collections.defaultdict(set)     # R -> {(slot_index, registered_at)}
    cnt = collections.Counter()
    snap_kinds = collections.Counter()

    with gzip.open(path, "rt", encoding="utf-8") as fh:
        header = json.loads(fh.readline())
        for line in fh:
            rec = json.loads(line)
            if rec.get("record_type") != "trial":
                continue
            t = rec["prediction_order"]
            cnt["trials"] += 1

            ss = rec.get("state_snapshot")
            snap_kinds[ss.get("kind") if isinstance(ss, dict) else None] += 1

            for ev in rec.get("reg_del_events") or []:
                cnt["event_" + str(ev.get("kind"))] += 1
                if ev.get("kind") == "registration":
                    reg[ev["R"]].append((t, ev["m_live"]))

            live = collections.Counter()
            present = set()
            for st in rec.get("constituent_states") or []:
                R = st["R"]
                present.add(R)
                rows[R].add((st["slot_index"], st["registered_at"]))
                if st.get("alive"):
                    live[R] += 1
            for R in present:
                end[R].append((t, live[R]))

            if rec.get("abstain_reason"):
                cnt["abstain"] += 1
            elif rec.get("hit") is not None:
                if int(rec["hit"]) == 1:
                    cnt["hit"] += 1
                else:
                    cnt["miss"] += 1
    return header, end, reg, rows, cnt, snap_kinds


def classify(R, end_seq, reg_seq, row_set):
    """§3 の各読みを一つの定義について判定する。"""
    ts = [v for _, v in end_seq]
    if not ts and not reg_seq:
        return None

    # 出生試行 t0 と、そのときの二つの厚み
    t0 = min([t for t, _ in end_seq] + [t for t, _ in reg_seq])
    L_t0 = next((v for t, v in end_seq if t == t0), None)
    m_reg0 = reg_seq[0][1] if reg_seq else None

    # 緩い読みの系列：各試行で 登録 m_live → 試行末 L(t) の順
    by_t = collections.defaultdict(list)
    for t, v in reg_seq:
        by_t[t].append(v)
    for t, v in end_seq:
        by_t[t].append(v)
    loose = [v for t in sorted(by_t) for v in by_t[t]]

    final = ts[-1] if ts else None
    max_end = max(ts) if ts else None
    max_loose = max(loose) if loose else None

    # 主判定（厳しい読み）
    a = max_end is not None and max_end >= 6
    b = final in (1, 2)
    drops = None
    c = False
    if a:
        last_ge6 = max(i for i, v in enumerate(ts) if v >= 6)
        drops = sum(1 for i in range(last_ge6 + 1, len(ts)) if ts[i] < ts[i - 1])
        c = drops >= 2
    strict = bool(a and b and c)

    loose_hit = bool(max_loose is not None and max_loose >= 6
                     and final is not None and final <= 2)

    reached = bool(a and any(v <= 2 for v in ts))
    refilled = bool(reached and final is not None and final >= 3)

    return dict(
        R=R, t0=t0, L_t0=L_t0, m_reg0=m_reg0,
        final=final, max_end=max_end, max_loose=max_loose,
        strict=strict, drops=drops,
        loose=loose_hit,
        birth_collapse=bool(loose_hit and L_t0 is not None and L_t0 <= 2),
        gradual=bool(loose_hit and L_t0 is not None and L_t0 >= 3),
        sudden=bool(a and b and not c),
        final_zero=bool(final == 0),
        reached=reached, refilled=refilled,
        total_rows=len(row_set),
        readd=sum(1 for _, ra in row_set if ra > min(r for _, r in row_set)) if row_set else 0,
        end_seq=end_seq,
    )

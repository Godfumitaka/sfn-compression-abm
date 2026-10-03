"""集団化：例外の日の場面から来た束の中身と、受け手が取り込んだ定義の答え（委任書 2026-10-03 の追加）。★ 記録を読むだけ。数を並べるだけ。
対象：Codex の集団化の一対一（世界 2、A・C、通信あり、集団の種 1〜20）の exception_receipts（Codex の analyze_collective20.py の
  counts.json。送信元の実場面が例外で、受け手に届いた束）。
一件ごとに：
  1 束の中の話し手の答え（通信の記録 comm/run<種>.jsonl の kind＝bundle の pred：[関係 ID, 述語, 引数]）。
    話し手の台帳のその試行の行（shop_type・shop_cue・held_out_is_door・held_out_content）と比べて：
      伏せた関係がドアで、答えの述語が held_out の述語（＝その店の例外の答え）→「例外の答え」、
      その店の通常の答え（tools/shopworld.py door_pred(2, 店, n)）→「通常の答え（神話）」、ほか→「その他」。
      伏せた関係がドアでない→「ドアでない関係の答え」。答えが束から外された（pred_excluded）→「束から外された」。答えが無い→「答え無し」。
    あわせて、束の中のドアの関係（述語 hold・hold_b の関係。どの束にも 1 本以下）の述語を、同じ二つと比べる。束の関係の ID は付け替えてあるので、
    話し手の場面で伏せたのがドアなら「話し手の答え」、そうでなければ「見えた関係」とする（伏せた関係は答えとしてしか束に入らないため）。
  2 束にシールの関係が入っていたか（束の関係の述語に sig_e・sig_n があるか）。Codex の has_sig_e も並べる。
  3 受け手が取り込んだ定義（名前と生まれた試行）：受け手の台帳を受け取った試行の終わり（その行の状態。受信はその試行の終わりに入る）まで
    当て直し（状態の sha256 を台帳と比べる）、その定義のドアの席（F の述語が hold・hold_b、又は H の履歴の名に hold・hold_b がある席）の答え：
      F の席の述語・H の席の履歴の名のうち、例外の答え（送り手の場面の店の例外の答え）・通常の答えのどちらを持つか
      →「例外の答えだけ」「通常の答えだけ」「両方」「ドアの席が無い（又は U だけ）」。定義が無ければ「定義が無い」。
使い方  python3.12 tools/collbundles.py <出力の .json> <集団化の走行根（outputs/pilot_…recvA…）> <counts.json>"""
import gzip
import hashlib
import json
import os
import sys

W = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [os.path.join(W, "tools"), W]
X, Y = "hold", "hold_b"


def door_pred(typ, cue):
    return X if (typ == "甲") == (cue == "n") else Y


def walk(path, want_rows, want_states):
    """台帳を当て直す。want_rows：行を返す試行、want_states：状態を返す試行（その行の終わりの状態）。"""
    from abm.loop import _apply, _json_bytes
    rows, states = {}, {}
    last = max(list(want_rows) + list(want_states) + [-1])
    st = None
    with gzip.open(path, "rt", encoding="utf-8") as f:
        next(f)
        for line in f:
            row = json.loads(line)
            if row.get("record_type", "trial") != "trial":
                continue
            t = row["prediction_order"]
            ss = row["state_snapshot"]
            st = ss["value"] if ss["kind"] == "full" else _apply(st, ss["changes"])
            assert hashlib.sha256(_json_bytes(st)).hexdigest() == row["agent_state_snapshot_hash"], (path, t)
            if t in want_rows:
                rows[t] = {k: row.get(k) for k in ("shop_type", "shop_cue", "held_out_is_door", "held_out_content", "door_pred")}
            if t in want_states:
                states[t] = json.loads(json.dumps(st))
            if t >= last:
                break
    return rows, states


def door_answers(st, R, born):
    d = (st.get("definitions") or {}).get(R)
    if d is None or d.get("registered_at") != born:
        return None
    sh, seats = st.get("slot_history") or {}, st.get("v39_seats") or {}
    out = []
    for c in d["constituents"]:
        k = str((R, c["slot_index"]))
        state = (seats.get(k) or {}).get("state") or ("F" if c["alive"] else "H")
        p = c["relation"]["predicate"]
        h = sh.get(k) or {}
        if state == "F" and p in (X, Y):
            out.append({"席": c["slot_index"], "状態": "F", "名": {p: None}})
        elif state != "F" and any(n in (X, Y) for n in h):
            out.append({"席": c["slot_index"], "状態": state, "名": {n: v for n, v in h.items() if n in (X, Y)}})
    return out


def main():
    dest, root, cpath = sys.argv[1], sys.argv[2], sys.argv[3]
    assert not os.path.exists(dest), ("既存の出力を上書きしない", dest)
    cnt = json.load(open(cpath, encoding="utf-8"))
    g = cnt["group_seed"]
    comm = [json.loads(l) for l in open(os.path.join(root, "comm", f"run{g:03d}.jsonl"), encoding="utf-8")]
    summary = next(r for r in comm if r["kind"] == "summary")
    bundles = {r["bundle"]: r for r in comm if r["kind"] == "bundle"}
    agents = summary["agents"]
    led = {i: os.path.join(root, "ledgers", "cells", a["cell"], f"seed{a['seed']:03d}.jsonl.gz") for i, a in enumerate(agents)}
    rec = cnt["exception_receipts"]
    want_rows = {i: {r["t"] for r in rec if r["sender"] == i} for i in led}
    want_states = {i: {r["t"] for r in rec if r["recipient"] == i and r["incorporated"]} for i in led}
    rows, states = {}, {}
    for i, p in led.items():
        rows[i], states[i] = walk(p, want_rows[i], want_states[i])
    out = []
    for r in rec:
        b = bundles[r["bundle"]]
        sr = rows[r["sender"]][r["t"]]
        typ, cue = sr["shop_type"], sr["shop_cue"]
        exc_a, nor_a = door_pred(typ, "e"), door_pred(typ, "n")
        pred = b.get("pred")
        if pred is None:
            k1 = "答え無し"
        elif b.get("pred_excluded"):
            k1 = "束から外された"
        elif not sr["held_out_is_door"]:
            k1 = "ドアでない関係の答え"
        else:
            k1 = "例外の答え" if pred[1] == exc_a else ("通常の答え（神話）" if pred[1] == nor_a else "その他")
        doors = [x for x in b["relations"] if x[1] in (X, Y)]
        k1b = ("ドアの関係が無い" if not doors else
               "+".join(("例外の答え" if x[1] == exc_a else "通常の答え（神話）") + ("（話し手の答え）" if sr["held_out_is_door"] else "（見えた関係）")
                        for x in doors))
        sigs = sorted({x[1] for x in b["relations"] if x[1] in ("sig_e", "sig_n")})
        k3, da = "取り込まれていない", None
        if r["incorporated"]:
            da = door_answers(states[r["recipient"]][r["t"]], r["R"], r["R_born"])
            if da is None:
                k3 = "定義が無い"
            else:
                names = {n for s in da for n in s["名"]}
                has_e, has_n = exc_a in names, nor_a in names
                k3 = "両方" if has_e and has_n else ("例外の答えだけ" if has_e else ("通常の答えだけ" if has_n else "ドアの席が無い（又は U だけ）"))
        out.append({**r, "店": typ, "日": cue, "伏せたのがドア": sr["held_out_is_door"], "例外の答え": exc_a, "通常の答え": nor_a,
                    "話し手の答え": pred, "1 話し手の答え": k1, "1b 束の中のドアの関係": k1b, "2 束のシールの述語": sigs,
                    "3 取り込んだ定義のドアの答え": k3, "取り込んだ定義のドアの席": da})
    json.dump({"group_seed": g, "件数": len(out), "束": out}, open(dest, "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=str)
    print(os.path.basename(root.rstrip("/")), len(out), flush=True)


if __name__ == "__main__":
    main()

"""v3.8 の検査 T01・T03〜T13（付録 5 節）を、実際の走行の記録で確かめる結合検査。模型は動かさない（台帳と side を読むだけ）。
走行は tools/v3_run.py --own-evidence --checks（本番の旗）。side の kind＝"v38"（tools/v38.py）と台帳を突き合わせる。
各検査は「当てはまる数」と「破れの数」を出す（破れ 0 で合格。当てはまる数が 0 の検査は「確かめられず」）。
使い方  python3 t_checks.py <走行根（ledgers/ と side/ がある）> [出力 json]"""
import collections, glob, gzip, json, os, sys

root = sys.argv[1]
N = collections.Counter(); BAD = collections.Counter(); EX = collections.defaultdict(list)


def bad(k, ex):
    BAD[k] += 1
    if len(EX[k]) < 3:
        EX[k].append(ex)


def key(p, a):
    return (p, tuple(a))


for led in sorted(glob.glob(os.path.join(root, "ledgers/cells/*/seed*.jsonl.gz"))):
    cell = os.path.basename(os.path.dirname(led)); sd = os.path.basename(led).replace(".jsonl.gz", "")
    side = os.path.join(root, "side", cell, sd + ".jsonl")
    L = {}
    with gzip.open(led, "rt", encoding="utf-8") as f:
        next(f)
        for line in f:
            r = json.loads(line); L[r["prediction_order"]] = r
    V = {}
    for line in open(side, encoding="utf-8"):
        if '"v38"' in line:
            d = json.loads(line)
            if d.get("kind") == "v38":
                V[d["trial"]] = d
    for t, r in L.items():
        d = V.get(t)
        cs = r.get("charge_source") or {}
        fired = bool(r.get("f_fired")); hit = r.get("hit") == 1
        N["T04_②の罰が無い（試行）"] += 1
        if cs.get("②"):
            bad("T04_②の罰が無い（試行）", (cell, sd, t))
        if fired:
            N["T09_開示が記録に届く（開示のある試行）"] += 1
            if d is None or d.get("受け取った開示") is None:
                bad("T09_開示が記録に届く（開示のある試行）", (cell, sd, t))
            elif key(*d["受け取った開示"]) != key(r["held_out_content"]["predicate"], r["held_out_content"]["arguments"]):
                bad("T09_開示が記録に届く（開示のある試行）", (cell, sd, t, "中身が違う"))
        if not fired:
            N["T02_開示なしの試行で伏せ辺を読まない"] += 1
            if d is not None and d.get("受け取った開示") is not None:
                bad("T02_開示なしの試行で伏せ辺を読まない", (cell, sd, t))
        if cs.get("①") or cs.get("①_穴埋め"):
            N["T09_①は外れ＋開示の試行だけ"] += 1
            if hit or not fired:
                bad("T09_①は外れ＋開示の試行だけ", (cell, sd, t, hit, fired))
        if d is None:
            continue
        rec = d.get("受け取った開示"); rk = key(*rec) if rec else None
        pred = d.get("予測"); src = d.get("出どころ"); seat = d.get("席の観察")
        rows = d.get("行") or []
        for x in rows:
            pos = x.get("pos"); rel = key(x["pred"], pos) if pos is not None else None
            orig, new = x["元"], x["新"]
            if rk is None and orig in ("③", "判定不能"):
                N["T03_T10_開示なしの未確認は中立"] += 1
                if new != orig or x.get("確認+", 0) or x.get("評価+", 0) or x.get("使用+", 1) != 1:
                    bad("T03_T10_開示なしの未確認は中立", (cell, sd, t, x))
            if rk is None:
                N["T13_開示なしでは反証しない"] += 1
                if new == "反証":
                    bad("T13_開示なしでは反証しない", (cell, sd, t, x))
            if rk is not None and orig != "充足":
                if new == "充足":
                    N["T01_T04_開示での確認は完全一致"] += 1
                    if rel != rk and not (pred and key(pred[1], pred[2]) == rk):
                        bad("T01_T04_開示での確認は完全一致", (cell, sd, t, x))
                    if x.get("確認+") != 1 or x.get("評価+") != 1:
                        bad("T01_T04_開示での確認は完全一致", (cell, sd, t, "回数", x))
                if pos is not None and x["pred"] == rk[0] and tuple(pos) != rk[1]:
                    N["T05_引数違いは確認しない"] += 1
                    if new == "充足":
                        bad("T05_引数違いは確認しない", (cell, sd, t, x))
                if pos is not None and rel != rk and new != "充足":
                    N["T13_開示後の不成立は反証"] += 1
                    if new != "反証" or x.get("評価+") != 1 or x.get("確認+") != 0:
                        bad("T13_開示後の不成立は反証", (cell, sd, t, x))
                if pos is None:
                    N["T12_位置が決まらない行は反証しない"] += 1
                    if new == "反証":
                        bad("T12_位置が決まらない行は反証しない", (cell, sd, t, x))
                    if new == "充足":
                        N["T12_位置が決まらない行を予測の引数で確認"] += 1
        if rk is not None and hit and src == "投影":
            N["T01_投影の当たり＋開示"] += 1
            ok = any(x["新"] == "充足" and x["元"] != "充足" for x in rows) or any(
                x["元"] == "充足" and x.get("pos") and key(x["pred"], x["pos"]) == rk for x in rows)
            if not ok:
                bad("T01_投影の当たり＋開示", (cell, sd, t))
            for x in rows:
                if x.get("pos") is not None and key(x["pred"], x["pos"]) == rk and x["新"] != "充足":
                    bad("T01_投影の当たり＋開示", (cell, sd, t, x))
        if rk is not None and hit and src == "穴埋め":
            N["T06_穴埋めの当たり＋開示"] += 1
            if not seat:
                bad("T06_穴埋めの当たり＋開示", (cell, sd, t, "席の観察なし"))
            else:
                b, a = seat["前"], seat["後"]; p = seat["述語"]
                if isinstance(b, dict) and isinstance(a, dict):
                    if a.get(p, 0) != b.get(p, 0) + 1 or any(a.get(q, 0) != b.get(q, 0) for q in set(a) | set(b) if q != p):
                        bad("T06_穴埋めの当たり＋開示", (cell, sd, t, "回数", b, a))
                N["T06_生きている行の席" if seat.get("生きている行") else "T06_墓石の席"] += 1
                for x in rows:
                    if x["slot"] == seat["slot"] and x["reg"] == seat["reg"] and x["pred"] != p:
                        N["T06_元の行が別の述語"] += 1
                        if x["新"] == "充足" and x["元"] != "充足":
                            bad("T06_元の行が別の述語", (cell, sd, t, x))
        if seat and not (rk is not None and hit and src == "穴埋め"):
            bad("T06_穴埋めの当たり＋開示", (cell, sd, t, "当たり＋開示の穴埋めでないのに席の観察"))
        if pred is None and rk is not None:
            N["T08_棄権＋開示"] += 1
            if seat:
                bad("T08_棄権＋開示", (cell, sd, t, "席の観察"))
out = {"当てはまる数": dict(N), "破れ": dict(BAD), "破れの例": dict(EX)}
print(json.dumps({k: {"当てはまる": N[k], "破れ": BAD.get(k, 0)} for k in sorted(N)}, ensure_ascii=False, indent=1))
if len(sys.argv) > 2:
    json.dump(out, open(sys.argv[2], "w"), ensure_ascii=False, indent=1)

"""SME 版の独立点検の 6（照合の中身の抜き取り）と 8（開示の記録）。Codex の sme_replay_audit.py は使わず、記録を自分で読む。
使い方：check6.py <走行の置き場所>  → 標準出力。
6：side/<セル>/seed001.sme.jsonl.gz の kind＝sme_result・caller＝v39:map_v39（定義と場面の照合。選びに使う）から、
  試行が違う 3 件（最初・真ん中・最後の方）を取り、採用された対応（new_relation_mapping・new_entity_mapping）について確かめる：
  (a) 一対一：関係どうし・物どうしの写しで、写し先が重ならない。左右の種類（物→物、関係／U→関係／未知）が合う。
  (b) 引数の順：写した関係の組で、左の k 番目の引数の写し先が、右の k 番目の引数と同じ（左の引数が写っている位置だけ）。
      右が未知の要素（伏せた位置、args＝None）のときは、引数を作っていないこと。
  (c) U の席の名前を読まない：左の U の節は names が空。U の節の写しの種類が "name" でない。
  (d) 伏せた位置を世界から補わない：その試行の伏せた関係（台帳の held_out_content の ID）が右の節にあるなら、種類は unknown・names は空・args は None。
      右の関係の節の ID は、その試行の見えている関係（台帳の observable_mask_edges）か未知の要素だけ。
  試行の見分け：右の節の関係の ID の集まりが、台帳のどの試行の observable_mask_edges と同じかで決める（関係の ID は試行ごとに違う）。
  同じ確かめを、その 3 試行の全部の map_v39 の照合にも当てる（数を書く）。
8：台帳の全部の試行の行に f_realized と f_fired があり、f_fired が真の試行は開示（feedback）が記録されているか。"""
import glob
import gzip
import json
import sys
from collections import Counter

root = sys.argv[1]
led = glob.glob(f"{root}/ledgers/cells/*/seed001.jsonl.gz")[0]
rows = [json.loads(l) for i, l in enumerate(gzip.open(led, "rt", encoding="utf-8")) if i > 0]
vis2t = {}
for t, r in enumerate(rows):
    vis2t[frozenset(r["observable_mask_edges"])] = t

# 8
c8 = Counter()
for r in rows:
    c8["試行"] += 1
    c8["f_realized あり"] += r.get("f_realized") is not None
    c8["f_fired あり"] += "f_fired" in r
    c8["開示あり"] += bool(r.get("f_fired"))
    c8["開示あり・feedback_content あり"] += bool(r.get("f_fired")) and r.get("feedback_content") is not None
    c8["開示なし・feedback_content なし"] += (not r.get("f_fired")) and r.get("feedback_content") is None
print("点検 8：", dict(c8), "f_realized の値", Counter(r.get("f_realized") for r in rows))

side = glob.glob(f"{root}/side/*/seed001.sme.jsonl*")[0]
opn = gzip.open if side.endswith(".gz") else open
by_t = {}
for line in opn(side, "rt", encoding="utf-8"):
    r = json.loads(line)
    if r.get("kind") != "sme_result" or r.get("caller") != "v39:map_v39":
        continue
    rel = frozenset(n["key"] for n in r["right_nodes"] if n["kind"] == "relation")
    t = vis2t.get(rel)
    by_t.setdefault(t, []).append(r)
ts = sorted(t for t in by_t if t is not None)
print("map_v39 の照合：", sum(len(v) for v in by_t.values()), "件、試行が分かった", sum(len(by_t[t]) for t in ts), "件、分からない", len(by_t.get(None, [])), "件、試行の数", len(ts))
pick = [ts[len(ts) // 10], ts[len(ts) // 2], ts[-5]]


def audit(r, t, verbose):
    L = {n["key"]: n for n in r["left_nodes"]}
    R = {n["key"]: n for n in r["right_nodes"]}
    rm, em = r["new_relation_mapping"], r["new_entity_mapping"]
    kinds = {(a, b): k for a, b, k in r["kinds"]}
    v = Counter()
    # (a)
    v["関係の写しの重なり"] += len(rm) - len(set(rm.values()))
    v["物の写しの重なり"] += len(em) - len(set(em.values()))
    v["物と関係の写し先の重なり"] += len(set(rm.values()) & set(em.values()))
    for a, b in em.items():
        v["物の写しの種類違い"] += not (L[a]["kind"] == "entity" and R[b]["kind"] == "entity")
    for a, b in rm.items():
        v["関係の写しの種類違い"] += not (L[a]["kind"] in ("relation", "unknown") and R[b]["kind"] in ("relation", "unknown"))
    # (b)
    allmap = {**em, **rm}
    for a, b in rm.items():
        la, rb = L[a], R[b]
        if rb["kind"] == "unknown":
            v["未知の要素に引数がある"] += rb["args"] is not None
            continue
        if la["args"] is None:
            continue
        v["引数の数の違い"] += len(la["args"]) != len(rb["args"])
        for k, x in enumerate(la["args"]):
            if x in allmap and k < len(rb["args"]):
                v["確かめた引数の位置"] += 1
                v["引数の順の違反"] += allmap[x] != rb["args"][k]
    # (c)
    for a, n in L.items():
        if n.get("state") == "U":
            v["U の節"] += 1
            v["U の節に名前がある"] += bool(n["names"])
            if a in rm:
                v["U の節の写しが名前の一致"] += kinds.get((a, rm[a])) == "name"
    # (d)
    held = rows[t]["held_out_content"]["relation_id"]
    visible = set(rows[t]["observable_mask_edges"])
    if held in R:
        n = R[held]
        v["伏せた関係の節"] += 1
        v["伏せた関係の節が補われている"] += not (n["kind"] == "unknown" and not n["names"] and n["args"] is None)
    v["見えていない関係の節（未知以外）"] += sum(1 for k, n in R.items() if n["kind"] == "relation" and k not in visible)
    if verbose:
        print(f"\n試行 {t}（左の節 {len(L)}、右の節 {len(R)}、関係の写し {len(rm)}、物の写し {len(em)}、伏せた関係 {held}）")
        for a, b in sorted(rm.items()):
            la, rb = L[a], R[b]
            print(f"  {a}[{la['kind']}・{la.get('state')}・{','.join(la['names']) or '名前なし'}・{la['args']}] → {b}[{rb['kind']}・{','.join(rb['names']) or '名前なし'}・{rb['args']}]  種類 {kinds.get((a, b))}")
    return v


tot = Counter()
for t in pick:
    rs = by_t[t]
    print(f"\n== 試行 {t}：map_v39 の照合 {len(rs)} 件")
    show = max(range(len(rs)), key=lambda i: len(rs[i]["new_relation_mapping"]))   # 写しのいちばん多い照合を印字する
    for i, r in enumerate(rs):
        tot.update(audit(r, t, i == show))
print("\n点検 6 の合計（3 試行の全部の map_v39 の照合）：", dict(tot))
bad = {k: v for k, v in tot.items() if any(w in k for w in ("重なり", "種類違い", "違反", "違い", "名前がある", "名前の一致", "補われている", "未知以外", "引数がある")) and v}
print("違反：", bad or "なし")

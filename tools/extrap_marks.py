"""外挿の印（2026-09-30 夕方の委任書「答えごとに『外挿の印』を付ける解析の道具」、アストラさん採用の規則）。★ 判断しない。模型は変えない。
読むもの：tools/extrap_reader.py が返す試行（予測の直前の状態・世界・開示・side・--dump-routing の記録・答えの記録）。版は SW でなく、読む走行の flag.json に従う。
すべて「その試行の予測の直前までの履歴」で付ける（今の開示や、そのあとの取り込みでは付け直さない）。

■ 状況（伏せた位置を基準に。今の正解は使わない）
  本人の見た場面 V_s ＝ 提示の関係 ＋（開示があれば）開示の関係。
  ある位置 p の状況は、p の中身（述語と引数）を隠した形で、V_s の中の p の親から作る。
  ・粗い：親ごとに（親の高さ, 親の引数の数, p が何番目の引数か, 親の子の並びの形）。子の並びの形は、子ごとに
      p 自身なら「伏」、見えている関係なら（関係, 引数の数, 引数の物・関係の出方の番号の並び）、物なら（物, 出方の番号）。
      物・関係の番号は、その親の子たちの中での初めての出方の順の番号（名前・ID は捨てる）。親の高さは V_s の中の高さ（p は高さ 0 として数える）。
  ・細かい：粗いに、親の述語と、見えている兄弟の述語（子の並びの順）を足す。
  ・親が二つ以上：親ごとの形を文字列にして並べ替えた組を状況にする（どれか一つを選ばない。決まった一つの規則）。
  ・判定不能：V_s に p を引数に持つ親が無い（理由「親が無い」）、又は p の兄弟の関係 ID が親の引数にあるのに V_s に無い（理由「兄弟が見えない」）。
  ・p の引数は使わない（本人には伏せた関係の引数は見えない。過去の場面の位置も同じく隠して照合する）。
■ エージェントの経験（粗い・細かいの両方）：過去の試行 s＜t の V_s の各位置（見えていた関係・開示された関係、開示の無い伏せた位置も）の状況と中身
  ・状況を見た：同じ状況の位置が過去にあった。
  ・確かめる機会があった：その位置の中身が見えていた（見えていた関係、又は伏せられて開示された）。中身の名を「その状況で経験した答え」とする。
  ・印：確かめる機会がまだなかった（状況が初めて／状況は見たが中身は未確認）・あった（中身も確認済み）・判定不能。
■ 覚えているか（研究者の側の診断）
  ・逐語：予測の直前の逐語の記憶（prototype の残っている場面）に、同じ状況で中身を含む位置がある。
  ・定義の役割：記憶の定義の席のうち、役割（親の行の生まれたときの述語と、その親の中の位置）が伏せた位置の親（述語と位置）と同じ席の
      固定の名（F）か候補の履歴の名に、その状況で経験した答えがある。
  ・答えを作れる：答えの記録の候補の答え（cand_answers）に、正解（hit＝1）を出す候補がある（答えた試行だけ。黙った試行は記録なし）。
  ・実際に使える：実際の答えが正解。
■ 定義の経験（選ばれた定義と、答えの出どころの席。定義の同一性は名前＠生まれた試行）
  ・取り込んだ：s＜t に誕生・同化でその定義に登録した場面に、同じ状況の位置があった。
  ・予測を出した／採点を受けた：s＜t にその定義が選ばれて答え（開示を受け）、s の伏せた位置の状況が同じ。
  ・★ 証拠が届いた：s＜t に、答えの出どころの席に、同じ状況の位置についての観察（m1・D-10）か採点が実際に届いた。
      観察＝--dump-routing の m1 の記録で、その席に名を足し、その出どころの関係（親の同じ位置の子、又は高階の席の位置の関係）の状況が同じ。
         又は side の kind＝"v38" の「席の観察」（D-10。開示された関係）の状況が同じ。
      採点＝--dump-routing の score の記録で、その席を採点し、開示された関係の状況が同じ（成績が変わった）。
  ・名が保存されている：予測の直前、その席の履歴（F なら固定の名も）に、その状況で経験した答えの名がある。
■ 成績
  ・課題：当たり／外れ／棄権（台帳の coverage・hit）。
  ・世界：答えた関係と同じ述語・同じ引数の組の関係が、作り直した完全な場面（G_star）にあれば真、無ければ偽（abm/world.py は場面の関係をすべて書き出し、
      逆向き・導かれる関係を作らない：control/2026-09-30_1549_外挿の印_記録の旗を作った_マック.md の 4）。答えなしは空。
  ・答えの出どころ：答えの記録の source。
出力：一走行ごとに、全課題の行（CSV）。腕ごとの表は tools/extrap_tables.py。
使い方（コードの作業場所を sys.path に置いて）：python3.12 tools/extrap_marks.py <腕の走行根> <セル> <種> <出力の .csv>
"""
from __future__ import annotations

import csv
import json
import sys
from collections import defaultdict

UNDET = "判定不能"


def _heights(rels_by_id):
    memo = {}

    def h(rid, seen):
        if rid in memo:
            return memo[rid]
        r = rels_by_id.get(rid)
        if r is None or rid in seen:
            return 0
        kids = [a for a in r["arguments"] if a in rels_by_id and a != rid]
        v = 0 if not kids else 1 + max(h(k, seen | {rid}) for k in kids)
        memo[rid] = v
        return v

    return {rid: h(rid, frozenset()) for rid in rels_by_id}


def situation(p_id, view, heights=None):
    """位置 p_id（中身は使わない）の状況：(粗い, 細かい, 理由)。view は {関係 ID: {predicate, arguments}}（p が中にあっても使わない）。"""
    others = {k: v for k, v in view.items() if k != p_id}
    parents = [(pid, r) for pid, r in others.items() if p_id in r["arguments"]]
    if not parents:
        return None, None, "親が無い"
    hts = heights if heights is not None else _heights(others)
    coarse_parts, fine_parts = [], []
    for pid, P in parents:
        labels = {}
        kids_c, kids_f = [], []
        for a in P["arguments"]:
            if a == p_id:
                kids_c.append("伏")
                kids_f.append("伏")
            elif a in others:
                c = others[a]
                pat = []
                for x in c["arguments"]:
                    labels.setdefault(x, len(labels))
                    pat.append(("R" if x in others else "E") + str(labels[x]))
                kids_c.append(("関係", len(c["arguments"]), tuple(pat)))
                kids_f.append(("関係", len(c["arguments"]), tuple(pat), c["predicate"]))
            elif a in view:          # ありえない（p 以外で view にあれば others にある）
                kids_c.append("?")
                kids_f.append("?")
            else:
                # 物か、見えない関係か。物は親の引数に物として出る（本人の場面の物）。見えない関係は判定不能にする
                if a.startswith("__ent__"):
                    pass
                labels.setdefault(a, len(labels))
                kids_c.append(("物か見えない", labels[a]))
                kids_f.append(("物か見えない", labels[a]))
        k = P["arguments"].index(p_id)
        coarse_parts.append(json.dumps([hts.get(pid, 0), len(P["arguments"]), k, kids_c], ensure_ascii=False))
        fine_parts.append(json.dumps([hts.get(pid, 0), len(P["arguments"]), k, kids_f, P["predicate"]], ensure_ascii=False))
    return tuple(sorted(coarse_parts)), tuple(sorted(fine_parts)), None


def view_of(world_trial, disclosed):
    rels = {r.relation_id: {"predicate": r.predicate, "arguments": list(r.arguments)} for r in world_trial.target_graph_partial.relations}
    if disclosed:
        h = world_trial.held_out_edge
        rels[h.relation_id] = {"predicate": h.predicate, "arguments": list(h.arguments)}
    return rels


def entity_ids(world_trial):
    return {e.entity_id for e in world_trial.G_star.entities}


def sit_checked(p_id, view, ents, relation_ids_in_scene):
    """兄弟の関係 ID が親の引数にあるのに見えない場合を判定不能にする版の situation。"""
    co, fi, why = situation(p_id, view)
    if why:
        return None, None, why
    for pid, r in view.items():
        if pid != p_id and p_id in r["arguments"]:
            for a in r["arguments"]:
                if a != p_id and a not in view and a not in ents:
                    return None, None, "兄弟が見えない"
    return co, fi, None


def seat_roles(defn, born_pred):
    """定義の席ごとの役割：{slot: [(親の生まれたときの述語, 位置), ...]}。born_pred は {slot: 生まれたときの述語}。"""
    rows = defn["constituents"]
    rid_to_slot = {r["relation"]["relation_id"]: r["slot_index"] for r in rows}
    roles = defaultdict(list)
    for r in rows:
        for k, a in enumerate(r["relation"]["arguments"]):
            if a in rid_to_slot:
                roles[rid_to_slot[a]].append((born_pred.get(r["slot_index"], r["relation"]["predicate"]), k))
    return roles


def main(arm_root, cell, seed, out_csv):
    from extrap_reader import iter_run
    trials = list(iter_run(arm_root, cell, seed))
    # 各試行の本人の場面と、その中の位置の状況（粗い・細かい）と中身
    per = []
    for tr in trials:
        wt = tr["world"]
        ents = entity_ids(wt)
        scene_ids = {r.relation_id for r in wt.G_star.relations}
        V = view_of(wt, tr["disclosed"])
        pos = {}
        hid = wt.held_out_edge.relation_id
        for pid in set(V) | {hid}:
            co, fi, why = sit_checked(pid, V if pid in V else V, ents, scene_ids)
            content = V[pid]["predicate"] if pid in V else None
            pos[pid] = (co, fi, why, content)
        per.append({"V": V, "pos": pos, "hid": hid, "ents": ents})
    born_pred = {}          # (R, 生まれた試行, slot) -> 生まれたときの述語
    seen = {"粗": defaultdict(set), "細": defaultdict(set)}        # 状況 -> {中身 or None}
    reg_scenes = defaultdict(list)       # (R, born) -> [s]
    used = defaultdict(list)             # (R, born) -> [(s, disclosed)]
    arrived = defaultdict(lambda: {"粗": set(), "細": set()})   # (R, born, slot) -> 状況の集合（観察・採点が届いた）
    arrived_kind = defaultdict(lambda: {"粗": set(), "細": set()})
    rows_out = []
    for i, tr in enumerate(trials):
        t = tr["t"]
        info = per[i]
        pre = tr["pre"] or {"definitions": {}, "slot_history": {}, "prototype": {"traces": []}}
        # 生まれたときの述語を控える（予測の直前の状態で、初めて見た行の述語。消去の前）
        for R, d in pre["definitions"].items():
            for r in d["constituents"]:
                key = (R, d["registered_at"], r["slot_index"])
                if key not in born_pred and r["relation"]["predicate"] != "⟨消去⟩":
                    born_pred[key] = r["relation"]["predicate"]
        co, fi, why, _ = info["pos"][info["hid"]]
        row = tr["row"]
        ans = tr["answer"]
        rec = {"trial": t, "seed": seed, "answered": int(row.get("coverage") == 1), "hit": row.get("hit"),
               "task": "棄権" if row.get("coverage") != 1 else ("当たり" if row.get("hit") == 1 else "外れ"),
               "disclosed": int(tr["disclosed"]), "situation_undet_reason": why or ""}
        # 世界の真偽
        if row.get("coverage") == 1 and row.get("predicted_edge"):
            pe = row["predicted_edge"]
            truth = any(r.predicate == pe["predicate"] and list(r.arguments) == list(pe["arguments"]) for r in tr["world"].G_star.relations)
            rec["world"] = "真" if truth else "偽"
        else:
            rec["world"] = ""
        for g, key in (("粗", co), ("細", fi)):
            if key is None:
                rec[f"{g}_経験"] = UNDET
                rec[f"{g}_印"] = UNDET
                continue
            s = seen[g].get(key)
            if not s:
                exp = "状況が初めて"
            elif not any(x is not None for x in s):
                exp = "状況は見たが中身は未確認"
            else:
                exp = "中身も確認済み"
            rec[f"{g}_経験"] = exp
            rec[f"{g}_印"] = "確かめる機会がまだなかった" if exp != "中身も確認済み" else "確かめる機会があった"
            contents = {x for x in (s or ()) if x is not None}
            # 逐語
            vb = 0
            for trc in pre["prototype"]["traces"]:
                Vv = {r["relation_id"]: {"predicate": r["predicate"], "arguments": r["arguments"]} for r in trc["scene"]["relations"]}
                for pid in Vv:
                    c2, f2, w2 = situation(pid, Vv)
                    if w2 is None and (c2 if g == "粗" else f2) == key:
                        vb = 1
                        break
                if vb:
                    break
            rec[f"{g}_逐語"] = vb
            # 定義の役割：伏せた位置の親（述語・位置）
            prole = {(r["predicate"], r["arguments"].index(info["hid"])) for pid, r in info["V"].items() if info["hid"] in r["arguments"]}
            dr = 0
            for R, d in pre["definitions"].items():
                bp = {r["slot_index"]: born_pred.get((R, d["registered_at"], r["slot_index"])) for r in d["constituents"]}
                roles = seat_roles(d, {k: v for k, v in bp.items() if v})
                for r in d["constituents"]:
                    if not prole & set(roles.get(r["slot_index"], [])):
                        continue
                    names = set(json.loads(json.dumps(pre["slot_history"].get(str((R, r["slot_index"])), {}))) or {})
                    if r.get("alive"):
                        names.add(r["relation"]["predicate"])
                    if names & contents:
                        dr = 1
                        break
                if dr:
                    break
            rec[f"{g}_定義の役割"] = dr
        # 答えを作れる・実際に使える
        if ans is not None:
            ca = json.loads(ans.get("cand_answers") or "[]")
            rec["答えを作れる"] = int(any(c.get("hit") == 1 for c in ca))
            rec["実際に使える"] = int(row.get("hit") == 1)
            rec["source"] = ans.get("source")
            R = ans.get("R")
            born = int(ans.get("R_born")) if ans.get("R_born") not in (None, "") else None
            slot = int(ans["slot"]) if ans.get("slot") not in (None, "") else None
            rec["def_id"] = ans.get("def_id")
            for g, key in (("粗", co), ("細", fi)):
                if key is None:
                    for c in ("取り込んだ", "予測を出した", "採点を受けた", "証拠が届いた", "名が保存されている"):
                        rec[f"{g}_{c}"] = ""
                    continue
                rec[f"{g}_取り込んだ"] = int(any(per[j]["pos"].get(p) and (per[j]["pos"][p][0 if g == "粗" else 1] == key)
                                             for j in reg_scenes[(R, born)] for p in per[j]["pos"]))
                pu = [(j, dsc) for j, dsc in used[(R, born)] if per[j]["pos"][per[j]["hid"]][0 if g == "粗" else 1] == key]
                rec[f"{g}_予測を出した"] = int(bool(pu))
                rec[f"{g}_採点を受けた"] = int(any(dsc for _, dsc in pu))
                rec[f"{g}_証拠が届いた"] = int(slot is not None and key in arrived[(R, born, slot)][g])
                rec[f"{g}_証拠が届いた_採点"] = int(slot is not None and key in arrived_kind[(R, born, slot)][g])
                s = seen[g].get(key) or set()
                contents = {x for x in s if x is not None}
                names = set()
                d = pre["definitions"].get(R)
                if d is not None and slot is not None:
                    names = set((pre["slot_history"].get(str((R, slot))) or {}).keys())
                    rr = next((r for r in d["constituents"] if r["slot_index"] == slot), None)
                    if rr is not None and rr.get("alive"):
                        names.add(rr["relation"]["predicate"])
                rec[f"{g}_名が保存されている"] = int(bool(names & contents))
        rows_out.append(rec)
        # ---- この試行の出来事を、次の試行からの履歴に足す（予測の直前までの履歴だけで付けるため、足すのは付けたあと）
        for pid, (c2, f2, w2, content) in info["pos"].items():
            if w2 is None:
                seen["粗"][c2].add(content)
                seen["細"][f2].add(content)
        post = tr["post"]
        for kind in ("birth", "assim"):
            for d in tr["side"].get(kind, []):
                dd = post["definitions"].get(d["R"])
                if dd is not None:
                    reg_scenes[(d["R"], dd["registered_at"])].append(i)
        if row.get("R_used") and row.get("coverage") == 1:
            dd = pre["definitions"].get(row["R_used"])
            if dd is not None:
                used[(row["R_used"], dd["registered_at"])].append((i, tr["disclosed"]))
        for m in tr["routing"].get("m1", []):
            dd = post["definitions"].get(m["R"])
            if dd is None:
                continue
            for s in m["seats"]:
                if not s.get("added"):
                    continue
                srcs = [pp["child"][0] for pp in s.get("parents", []) if pp.get("child") and pp["child"][1] in s["added"]]
                srcs += [x[0] for x in s.get("position_relations", []) if x[1] in s["added"]]
                for rid in srcs:
                    pz = info["pos"].get(rid)
                    if pz and pz[2] is None:
                        arrived[(m["R"], dd["registered_at"], s["slot"])]["粗"].add(pz[0])
                        arrived[(m["R"], dd["registered_at"], s["slot"])]["細"].add(pz[1])
        for sc in tr["routing"].get("score", []):
            dd = pre["definitions"].get(sc["R"])
            if dd is None:
                continue
            pz = info["pos"].get(sc["received"][0])
            if not pz or pz[2] is not None:
                continue
            for it in sc["items"]:
                if it.get("scored"):
                    for g, k in (("粗", pz[0]), ("細", pz[1])):
                        arrived[(sc["R"], dd["registered_at"], it["slot"])][g].add(k)
                        arrived_kind[(sc["R"], dd["registered_at"], it["slot"])][g].add(k)
        for v in tr["side"].get("v38", []):
            so = v.get("席の観察")
            if so:
                dd = pre["definitions"].get(so["R"])
                pz = info["pos"].get(info["hid"])
                if dd is not None and pz and pz[2] is None:
                    arrived[(so["R"], dd["registered_at"], so["slot"])]["粗"].add(pz[0])
                    arrived[(so["R"], dd["registered_at"], so["slot"])]["細"].add(pz[1])
    keys = []
    for r in rows_out:
        for k in r:
            if k not in keys:
                keys.append(k)
    with open(out_csv, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        w.writerows(rows_out)
    return len(rows_out)


if __name__ == "__main__":
    sys.path[:0] = [".", "tools"]
    print(main(sys.argv[1], sys.argv[2], int(sys.argv[3]), sys.argv[4]))

"""v3.11c（集団化・事例伝達）の走行の数え（仕様 7 節）と、受入検査 ⑫（数の突き合わせ）。★ 判断しない。模型は動かさない（台帳・side・通信の記録を読むだけ）。
使い方  python3.12 tools/v311c_report.py <走行根>[,<走行根>…] [--names 腕の名前,…] [--md 出力.md] [--json 出力.json]
  走行根は tools/v3_run.py --v311c の出力（ledgers/・side/・comm/run*.jsonl）。一つの走行根に、走行（集団）がいくつあってもよい。
数えるもの（集団ごと・腕ごとの和。ばらつきの単位は集団の走行）
  1 世界の成績：全世界課題（個体 × 試行）を分母に 正解・誤答・棄権、発話時の正解率。誤答の出どころ：F（投影・固定名の穴埋め）／H（席の履歴）／U（全体の既定値）。
  2 伝わる過程：発話の機会（実際に答えた試行）→ 束（参照先を整えて空でない）→ 送信 → 取り込み（同化・誕生）／不成立
     → 取り込んだ定義が次の試行に残る／走行の終わりに残る → その定義がそのあと世界で使われる（R_used）／また語られる（その定義から送った束）。
  3 話の長さ：束の関係の本数、名札を含む記述の長さ（ビット。tools/v311c.py bundle_bits）。束に加えた参照先・外した関係の本数、予測そのものが外れた数。
     世界の場面と送った束の違い（名前の付け直しを除く）：場面の関係の数・束に入った場面の関係の数・場面に無い束の関係（予測）の数。
  4 名札：新しい名札の数、報告からの誕生・名札付きの同化の数、受信 B で同じ名札の候補があった数、集団から消えた名札の数。
  5 回答の一致（100 試行ごと、20 件）：双方正解・同じ誤答・双方棄権・その他。
  ⑫ 突き合わせ：個体ごとに 正解＋誤答＋棄権＝試行数、誤答の出どころの和＝誤答、送信＝配達＝受け取りの記録の数、
     一致の四分類の和＝個体の組の数 × 20、束のある試行は台帳で実際に答えた試行。
"""
from __future__ import annotations

import collections
import glob
import gzip
import json
import os
import sys


def ledger_rows(p):
    with gzip.open(p, "rt", encoding="utf-8") as f:
        next(f)
        for line in f:
            r = json.loads(line)
            if r.get("record_type", "trial") == "trial":
                yield r


def side_v39(p):
    out = {}
    for line in open(p, encoding="utf-8"):
        if '"kind": "v39"' in line:
            d = json.loads(line)
            if d.get("kind") == "v39":
                out[d["trial"]] = d
    return out


def one_population(root, comm_path):
    comm = [json.loads(l) for l in open(comm_path, encoding="utf-8")]
    summ = next((c for c in comm if c["kind"] == "summary"), {})
    agents = summ.get("agents") or []
    seeds = [a.get("seed") for a in agents if isinstance(a, dict)]
    cell = next((a.get("cell") for a in agents if isinstance(a, dict)), None)
    C = collections.Counter()
    chk = collections.Counter()
    per_agent = []
    births = {}          # 個体 → 名前 → [生まれた試行]
    removed = {}         # 個体 → 名前 → [消えた試行]
    used = {}            # 個体 → [(試行, R_used)]
    alive_end = {}
    coverage = {}
    for i, sd in enumerate(seeds):
        led = os.path.join(root, "ledgers", "cells", cell, f"seed{sd:03d}.jsonl.gz")
        side = os.path.join(root, "side", cell, f"seed{sd:03d}.jsonl")
        sv = side_v39(side) if os.path.exists(side) else {}
        A = collections.Counter()
        b_i = collections.defaultdict(list)
        rm_i = collections.defaultdict(list)
        u_i = []
        cov = {}
        for r in ledger_rows(led):
            t = r["prediction_order"]
            A["課題"] += 1
            cov[t] = r.get("coverage") == 1
            for e in r.get("reg_del_events") or []:
                if e.get("kind") == "registration" and not e.get("was_extension"):
                    b_i[e["R"]].append(e["trial"])
                if e.get("kind") == "definition_removed":
                    rm_i[e["R"]].append(e["trial"])
            if r.get("R_used") is not None:
                u_i.append((t, r["R_used"]))
            if r.get("coverage") == 1:
                if r.get("hit") == 1:
                    A["正解"] += 1
                else:
                    A["誤答"] += 1
                    rid = ((r.get("predicted_edge") or {}).get("relation_id") or "")
                    if rid.startswith("sme_projection__"):
                        A["誤答_F"] += 1
                    elif rid.startswith("filling__"):
                        fs = dict((x[0], x[1]) for x in (sv.get(t, {}).get("fill") or []))
                        st = fs.get(rid)
                        A["誤答_" + (st if st in ("F", "H", "U") else "?")] += 1
                    else:
                        A["誤答_?"] += 1
            else:
                A["棄権"] += 1
        chk["個体の課題の和"] += (A["正解"] + A["誤答"] + A["棄権"] == A["課題"])
        chk["誤答の出どころの和"] += (A["誤答_F"] + A["誤答_H"] + A["誤答_U"] + A["誤答_?"] == A["誤答"])
        C.update({k: v for k, v in A.items()})
        per_agent.append(dict(A))
        births[i] = b_i
        removed[i] = rm_i
        used[i] = u_i
        coverage[i] = cov
        # 走行の終わりに生きている定義（side の最後の v39 の記録の後の final 行）
        fin = None
        if os.path.exists(side):
            for line in open(side, encoding="utf-8"):
                if '"kind": "final"' in line:
                    fin = json.loads(line)
        alive_end[i] = set((fin or {}).get("constituents_end", {}).keys())

    def alive_next(i, R, born, t):
        """取り込んだ定義が次の試行の終わりに生きているか：その試行より後に、この定義（同じ同一性）が消えた記録が無いか、R_used に出ているか。
        台帳の定義の消失（definition_removed）を読む。"""
        gone = removed[i].get(R, [])
        return not any(t < g <= t + 1 for g in gone)

    def ident(i, R, t):
        """試行 t の時点の定義 R の同一性（生まれた試行）。"""
        bs = [b for b in births[i].get(R, []) if b <= t]
        return max(bs) if bs else None

    bundles = [c for c in comm if c["kind"] == "bundle"]
    recvs = [c for c in comm if c["kind"] == "recv"]
    # ★ 受け取りで生まれた定義は台帳の登録の記録に載らない（台帳は世界の場面の登録だけ）。通信の記録から足す
    for r in recvs:
        if r.get("result") == "誕生" and r.get("R") is not None:
            births[r["agent"]][r["R"]].append(r["R_born"])
    for i in births:
        for R in births[i]:
            births[i][R].sort()
    probes = [c for c in comm if c["kind"] == "probe"]
    C["発話の機会"] = sum(1 for i in coverage for t, v in coverage[i].items() if v)
    C["束"] = sum(1 for b in bundles if not b.get("empty"))
    C["束が空（参照先を整えると何も残らない）"] = sum(1 for b in bundles if b.get("empty"))
    C["送信"] = sum(1 for b in bundles if b.get("send"))
    C["受け取り"] = len(recvs)
    for r in recvs:
        C["受け取り_" + str(r.get("result"))] += 1
        C["受信B_同じ名札の候補あり"] += (r.get("same_tag_candidates") or 0) > 0
        C["受信B_使った"] += bool(r.get("used_B"))
        C["土台が報告の束"] += bool(r.get("base_is_report"))
    # 伝わる過程のその先：取り込んだ定義が残る・世界で使う・また語る
    sent_by = collections.defaultdict(list)
    for b in bundles:
        if b.get("send"):
            sent_by[b["agent"]].append((b["t"], b.get("R"), b.get("R_born")))
    for r in recvs:
        if r.get("result") not in ("同化", "誕生"):
            continue
        i, R, born, t = r["agent"], r.get("R"), r.get("R_born"), r["t"]
        C["取り込んだ定義が次の試行に残る"] += int(ident(i, R, t + 1) == born and alive_next(i, R, born, t))
        C["取り込んだ定義が走行の終わりに残る"] += (R in alive_end[i] and ident(i, R, 10 ** 9) == born)
        C["そのあと世界で使われた"] += any(tt > t and RR == R and ident(i, RR, tt) == born for tt, RR in used[i])
        C["そのあとまた語られた"] += any(tt > t and RR == R and bb == born for tt, RR, bb in sent_by[i])
    # 話の長さ・場面との違い・参照先
    nb = [b for b in bundles if not b.get("empty")]
    if nb:
        C["束の関係の本数（和）"] = sum(b.get("n_rel", 0) for b in nb)
        C["束の記述の長さ（ビット、和）"] = sum(b.get("bits", 0) for b in nb)
        C["参照先を加えた本数（和）"] = sum(b.get("added", 0) for b in nb)
        C["初期束から外した本数（和）"] = sum(b.get("excluded", 0) for b in bundles)
        C["予測そのものが外れた"] = sum(1 for b in bundles if b.get("pred_excluded"))
        C["場面の関係の数（和）"] = sum(b.get("scene_n", 0) for b in nb)
        C["束に入った場面の関係（和）"] = sum(b.get("bundle_from_scene", 0) for b in nb)
        C["場面に無い束の関係（予測、和）"] = sum(b.get("bundle_not_in_scene", 0) for b in nb)
    C["集団から消えた名札"] = sum(len(c.get("tags", [])) for c in comm if c["kind"] == "tag_lost")
    for a in agents:
        v = (a or {}).get("v311c") or {} if isinstance(a, dict) else {}
        for k in ("new_tags", "birth_world", "birth_report", "assim_report", "recv_relearn", "recv_score_changed", "recv_merit_changed",
                  "dC_mismatch", "recv_reinit_restored"):
            C["STATS_" + k] += v.get(k, 0) or 0
    # 回答の一致
    P = collections.Counter()
    n = len(seeds)
    for p in probes:
        for k in ("双方正解", "同じ誤答", "双方棄権", "その他"):
            P[k] += p[k]
        chk["一致の四分類の和"] += (p["双方正解"] + p["同じ誤答"] + p["双方棄権"] + p["その他"] == n * (n - 1) // 2 * len(p["answers"][0]))
    # ⑫ 突き合わせ
    chk["送信＝配達"] = int(summ.get("sent") == summ.get("delivered"))
    chk["配達＝受け取りの記録"] = int(summ.get("delivered") == len(recvs))
    chk["束のある試行は実際に答えた試行"] = int(all(coverage[b["agent"]].get(b["t"]) for b in bundles))
    chk["一個体一試行に束は一つまで"] = int(len({(b["agent"], b["t"]) for b in bundles}) == len(bundles))
    chk["受け取りで束を送らない"] = int(all(b["t"] in coverage[b["agent"]] for b in bundles))
    return {"run": os.path.basename(comm_path), "個体": n, "試行": summ.get("trials"), "失敗": len(summ.get("errors") or []),
            "数": dict(C), "回答の一致": dict(P), "回答の一致（試験ごと）": [{k: p[k] for k in ("t", "双方正解", "同じ誤答", "双方棄権", "その他", "correct")}
                                                          for p in probes],
            "個体ごと": per_agent, "突き合わせ": dict(chk), "probes": len(probes)}


def main():
    a = [x for x in sys.argv[1:] if not x.startswith("--")]
    opt = {x.split("=")[0]: x.split("=", 1)[1] for x in sys.argv[1:] if x.startswith("--") and "=" in x}
    roots = a[0].split(",")
    names = opt.get("--names", ",".join(os.path.basename(r.rstrip("/")) for r in roots)).split(",")
    out = {}
    for root, name in zip(roots, names):
        pops = [one_population(root, p) for p in sorted(glob.glob(os.path.join(root, "comm", "run*.jsonl")))]
        tot = collections.Counter()
        for p in pops:
            tot.update(p["数"])
        out[name] = {"集団": pops, "和": dict(tot)}
    if "--json" in opt:
        json.dump(out, open(opt["--json"], "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    lines = []
    for name, v in out.items():
        t = v["和"]
        lines.append(f"### {name}（集団 {len(v['集団'])}）")
        for p in v["集団"]:
            c = p["数"]
            lines.append(f"- {p['run']}：個体 {p['個体']}・試行 {p['試行']}・失敗 {p['失敗']}／課題 {c.get('課題', 0):,}：正解 {c.get('正解', 0):,}・誤答 {c.get('誤答', 0):,}"
                         f"（F {c.get('誤答_F', 0)}・H {c.get('誤答_H', 0)}・U {c.get('誤答_U', 0)}・不明 {c.get('誤答_?', 0)}）・棄権 {c.get('棄権', 0):,}"
                         f"／発話の機会 {c.get('発話の機会', 0)} → 束 {c.get('束', 0)} → 送信 {c.get('送信', 0)} → 受け取り {c.get('受け取り', 0)}"
                         f"（同化 {c.get('受け取り_同化', 0)}・誕生 {c.get('受け取り_誕生', 0)}・不成立 {c.get('受け取り_不成立', 0)}）"
                         f" → 次の試行に残る {c.get('取り込んだ定義が次の試行に残る', 0)}・終わりに残る {c.get('取り込んだ定義が走行の終わりに残る', 0)}"
                         f" → 世界で使う {c.get('そのあと世界で使われた', 0)}・また語る {c.get('そのあとまた語られた', 0)}"
                         f"／突き合わせ {p['突き合わせ']}")
        lines.append("")
    md = "\n".join(lines)
    if "--md" in opt:
        open(opt["--md"], "w", encoding="utf-8").write(md + "\n")
    print(md)


if __name__ == "__main__":
    main()

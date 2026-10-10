"""例外の定義（D_e）の調べ（受け箱の指示 84 の 4・5、理解の場の決定 10/10 16:26・18:39）。記録を読むだけ、探りの数え。

範囲：第 1 波・世界 2・種 1〜20。本は ~/surface/wave1_view/selection.tsv（wave1.py・door_errors.py と同じ選び方）。
  「1a」＝行 1a（種 1〜10）と 1b（種 11〜20）を合わせたもの、「5a」＝5a/5b、「7a」＝7a/7b（door_errors.py と同じ合わせ方）。
読むもの（どれも読むだけ）：
  台帳 ledgers/cells/*/seedNNN.jsonl.gz：試行の行（shop_cue・held_out_is_door・hit・predicted_edge）と state_snapshot。
     state_snapshot の差分を abm.loop._apply（c7921598 の abm/loop.py。4ceadf63・c57467ea・e9ed84a・daf69efd と同じ中身）で積み、
     毎試行の終わりの記憶（定義・席・slot_history）を戻す。CHECK の試行と最後の試行で agent_state_snapshot_hash と照合する
     （d_skeleton.py と同じ戻し方）。
  注意の記録 attention/*/seedNNN.jsonl.gz：候補（R・registered_at・q_numerator/q_denominator・gate_passed・hit・seal）と selected_R。
     door_errors.py の読み方（rows_gz・seal_fields）をそのまま使う。
  side/*/seedNNN.shop.jsonl：kind=shop_seat・which=sig の席の移り変わり（R・reg・slot・trial・from・to・cand）。シールの席の決め方。
  side/*/seedNNN.jsonl：kind=birth/assim（m1 が誕生・同化した試行と定義）、kind=v310be（E の選び：chosen・reg・lam・cands）、
     kind=v39（変換 conv：[種類, R, 席, V, dC, why, 同点の数]・退役 retire）。
  flag.json：v39_price（変換の λ）・e_price・no_forget_exec・match_cstar・match_cstar_e。
定義（meta.json にも書く）：
  シールの席＝shop.jsonl の which=sig の (R, reg, slot)。席の状態＝戻した記憶で alive→F、slot_history に鍵あり→H、ほか→U
     （v39.seat_state・d_skeleton.py と同じ）。F の名前＝その席の relation.predicate。H の履歴＝slot_history の表。
  D_e（その時点）＝シールの席が F で名前が sig_e、又は H で履歴に sig_e が 1 以上ある定義。
  D_e（誕生で）＝誕生の試行（registered_at）の終わりの記憶で、上の D_e に当たる定義（指示の「sig_e の F か、履歴に sig_e を持つ H と
     して生まれた定義」）。誕生と同じ試行で退役した定義は記憶に残らないので NA。
  D_n の F[sig_n]＝シールの席が F で名前が sig_n の定義。
使い方：nice -n 15 python3 exception_defs.py --out DIR [--workers 3] [--only 1a,1]
"""
import argparse
import csv
import gzip
import json
import math
import sys
from collections import Counter, defaultdict
from datetime import datetime
from fractions import Fraction
from hashlib import sha256
from multiprocessing import Pool
from pathlib import Path

SRC = "/mnt/d/sfn_runs/scratch_exception_defs_20261010/src_c792"   # git -C ~/sfn/sfn-compression-abm archive c7921598 abm tools
sys.path.insert(0, SRC)
sys.path.insert(0, str(Path.home() / "surface/door_errors"))
import door_errors as DE  # noqa: E402  rows_gz・one・seal_fields・fmtf（読み方を合わせる）

V = Path.home() / "surface/wave1_view"
WORLD = 2
GROUPS = ("1", "5", "7")
EXPECTED = {"1": (218, 612), "7": (21, 612), "5": (169, 431)}   # door_errors_20261010_1211 の数（選び間違い、例外の日のドアの課題）
CHECK = (0, 300, 500, 1000, 1500)


def hstr(h):
    if h is None:
        return ""
    if not isinstance(h, dict):
        return "表でない:" + json.dumps(h, ensure_ascii=False)
    return ",".join(f"{k}:{v}" for k, v in sorted(h.items())) if h else "{}"


def summarise(st, seal_slots):
    """毎試行の終わりの記憶から、定義ごとのシールの席の状態。鍵は (名前, registered_at)。"""
    sh = st["slot_history"]
    out = {}
    for name, d in st["definitions"].items():
        reg = d["registered_at"]
        rows = {c["slot_index"]: c for c in d["constituents"]}
        seals = []
        for s in sorted(seal_slots.get((name, reg), ())):
            c = rows.get(s)
            if c is None:
                seals.append((s, "席なし", "", None))
                continue
            key = str((name, s))
            state = "F" if c["alive"] else ("H" if key in sh else "U")
            seals.append((s, state, c["relation"]["predicate"] if state == "F" else "", sh.get(key) if state == "H" else None))
        de = any((st_ == "F" and nm == "sig_e") or (st_ == "H" and isinstance(h, dict) and h.get("sig_e", 0) > 0)
                 for _, st_, nm, h in seals)
        out[(name, reg)] = dict(
            seals=seals, de=de,
            Fn=any(st_ == "F" and nm == "sig_n" for _, st_, nm, _h in seals),
            Fe=any(st_ == "F" and nm == "sig_e" for _, st_, nm, _h in seals),
            He=any(st_ == "H" and isinstance(h, dict) and h.get("sig_e", 0) > 0 for _, st_, nm, h in seals),
            assim=d.get("assimilation_count"), n_seats=len(d["constituents"]))
    return out


def seal_txt(info):
    if info is None:
        return dict(state="NA", name="NA", history="NA")
    if not info["seals"]:
        return dict(state="シールの席なし", name="", history="")
    return dict(state="|".join(s[1] for s in info["seals"]), name="|".join(s[2] for s in info["seals"]),
                history="|".join(hstr(s[3]) if s[1] == "H" else "" for s in info["seals"]))


def att_seal_class(raw):
    """注意の記録の候補の seal から分類（F sig_n / F sig_e / H（sig_e あり）/ H（sig_e なし）/ U / なし）。"""
    if not raw:
        return "シールの席なし"
    out = []
    for s in raw:
        st = s.get("state")
        if st == "F":
            out.append(f"F {s.get('name')}")
        elif st == "H":
            out.append("H sig_e あり" if (s.get("history") or {}).get("sig_e", 0) > 0 else "H sig_e なし")
        else:
            out.append(str(st))
    return "|".join(out)


def find_def(info_t, name):
    """名前で定義を引く（その時点で同じ名前は一つ）。"""
    got = [k for k in info_t if k[0] == name]
    return got[0] if len(got) == 1 else None


def one_run(job):
    row, world, seed, run_name, version = job
    g = row[0]
    rd = V / row / f"q{row}_w{world}" / f"seed{seed:03d}"
    base = dict(row=row, world=world, seed=seed, run=run_name, version=version)
    res = dict(base=base, status="", tables=defaultdict(list), checks=[])
    led = DE.one(rd, f"ledgers/cells/*/seed{seed:03d}.jsonl.gz")
    att = DE.one(rd, f"attention/*/seed{seed:03d}.jsonl.gz")
    shp = DE.one(rd, f"side/*/seed{seed:03d}.shop.jsonl")
    sidef = DE.one(rd, f"side/*/seed{seed:03d}.jsonl")
    for nm, p in (("台帳", led), ("注意の記録", att), ("shop.jsonl", shp), ("side jsonl", sidef)):
        if p is None:
            res["status"] = f"NA：{nm}が無い"
            return res
    flag = json.loads((rd / "flag.json").read_text())
    lam_conv = flag.get("v39_price")
    chk = lambda name, ok, detail="": res["checks"].append(dict(**base, check=name, ok=ok, detail=detail))

    # ---- shop.jsonl：シールの席
    seal_slots = defaultdict(set)
    shop_ev = defaultdict(list)
    seal_events = []
    with open(shp, encoding="utf-8") as f:
        for line in f:
            e = json.loads(line)
            if e.get("kind") == "shop_seat" and e.get("which") == "sig":
                seal_slots[(e["R"], e["reg"])].add(e["slot"])
                shop_ev[e["trial"]].append(e)
                seal_events.append(e)
    # ---- side jsonl：誕生・同化・E・変換
    m1rec, e_rec, v39rec = {}, {}, {}
    with open(sidef, encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            k = r.get("kind")
            if k in ("birth", "assim"):
                if r["trial"] in m1rec:
                    res["status"] = f"NA：side の birth/assim が同じ試行に二つ（{r['trial']}）"
                    return res
                m1rec[r["trial"]] = r
            elif k == "v310be":
                e_rec[r["trial"]] = r
            elif k == "v39":
                v39rec[r["trial"]] = r
    conv_by = defaultdict(list)
    retire_at = defaultdict(list)
    for t, r in v39rec.items():
        for c in r.get("conv") or []:
            conv_by[(t, c[1], c[2])].append(c)
        for R in r.get("retire") or []:
            retire_at[R].append(t)
    # E の記録と side の誕生・同化の突き合わせ
    bad = []
    for t, r in m1rec.items():
        er = e_rec.get(t, {})
        if "x" in er:
            continue
        exp_new = r["kind"] == "birth"
        if (er.get("chosen") is None) != exp_new or er.get("reg") != r["R"]:
            bad.append(t)
    chk("side の birth/assim と v310be の chosen・reg", not bad, ";".join(map(str, bad[:20])))

    # ---- 台帳：毎試行の記憶を戻す
    from abm.loop import _apply, _json_bytes
    L, infos = {}, {}
    st = None
    horizon = None
    shop_cur = {}
    shop_mism = []
    no_seal = Counter()
    multi_seal = set()
    hash_res = []
    last_t = None
    last_hash = None
    with gzip.open(led, "rt", encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            if r.get("record_type") == "run_header":
                horizon = int(r["trial_count"])
                continue
            if r.get("record_type", "trial") != "trial":
                continue
            t = r["prediction_order"]
            s = r["state_snapshot"]
            if s["kind"] == "full":
                st = s["value"]
            elif s["kind"] == "delta":
                st = _apply(st, s["changes"])
            else:
                res["status"] = f"NA：state_snapshot の種類 {s['kind']}"
                return res
            pe = r["predicted_edge"]
            L[t] = dict(cue=r.get("shop_cue"), door=bool(r.get("held_out_is_door")), shop_type=r.get("shop_type"),
                        outcome="correct" if r["hit"] else "silent" if pe is None else "wrong",
                        lam_ledger=r.get("lambda"))
            info = summarise(st, seal_slots)
            infos[t] = info
            for k, v in info.items():
                if not v["seals"]:
                    no_seal[k] += 1
                if len(v["seals"]) > 1:
                    multi_seal.add(k)
            for e in shop_ev.get(t, ()):
                shop_cur[(e["R"], e["reg"], e["slot"])] = e["to"]
            live = {k: v for k, v in shop_cur.items() if v != "定義ごと消えた"}
            mine = {(k[0], k[1], s[0]): s[1] for k, v in info.items() for s in v["seals"]}
            if live != mine:
                shop_mism.append(t)
            if t in CHECK:
                hash_res.append((t, sha256(_json_bytes(st)).hexdigest() == r["agent_state_snapshot_hash"]))
            last_t, last_hash = t, r["agent_state_snapshot_hash"]
    hash_res.append((last_t, sha256(_json_bytes(st)).hexdigest() == last_hash))
    chk("台帳の状態の sha256（agent_state_snapshot_hash）", all(ok for _, ok in hash_res),
        ";".join(f"{t}:{ok}" for t, ok in hash_res))
    chk("シールの席の状態：台帳から戻した記憶 対 shop.jsonl（毎試行）", not shop_mism,
        f"合わない試行 {len(shop_mism)}" + (f"（最初 {shop_mism[:10]}）" if shop_mism else ""))
    chk("シールの席が shop.jsonl に無い定義（情報：シールの関係を持たない定義）", "情報", f"{len(no_seal)} 定義：" + ";".join(f"{k[0]}@{k[1]}" for k in list(no_seal)[:20]))
    chk("シールの席が二つ以上の定義", not multi_seal, ";".join(f"{k[0]}@{k[1]}" for k in list(multi_seal)[:20]))
    trials = sorted(L)
    empty = {}
    before = lambda t: infos.get(t - 1, empty)

    # 誕生で D_e か
    birth_info = {}
    for t, r in m1rec.items():
        if r["kind"] != "birth":
            continue
        k = (r["R"], t)
        birth_info[k] = infos.get(t, {}).get(k)   # None＝同じ試行で退役（記憶に残らない）

    def de_birth(k):
        if k not in birth_info:
            # 誕生の記録が無い（試行 0 より前は無いので、名前の付け替えなど）
            i = infos.get(k[1], {}).get(k)
            return "NA：side に誕生の記録が無い" if i is None else i["de"]
        i = birth_info[k]
        return "NA：誕生と同じ試行で退役（記憶に残らない）" if i is None else i["de"]

    # ---- 注意の記録
    cap = {}
    keep = {}
    with gzip.open(att, "rt", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            r = json.loads(line)
            t = r.get("trial")
            if t is None or t in cap:
                res["status"] = f"NA：注意の記録の試行の番号が無いか重なる（{t}）"
                return res
            cands = r.get("candidates") or []
            cap[t] = any(c.get("gate_passed") and c.get("hit") for c in cands)
            x = L.get(t)
            if x is not None and x["door"] and x["cue"] == "e":
                keep[t] = dict(selected=r.get("selected_R"), n_defs_att=r.get("definitions"),
                               cands=[dict(R=c.get("R"), reg=c.get("registered_at"),
                                           q=Fraction(int(c["q_numerator"]), int(c["q_denominator"])),
                                           gate=c.get("gate_passed"), hit=c.get("hit"), seal_raw=c.get("seal"),
                                           seal=DE.seal_fields(c)) for c in cands])
    if sorted(cap) != trials:
        res["status"] = f"NA：突き合わせの誤り（台帳 {len(trials)} 試行、注意の記録 {len(cap)} 試行）"
        return res
    # 注意の記録の seal 対 戻した記憶（その試行の前＝t−1 の終わり）
    a_chk = a_ok = 0
    a_bad = []
    for t, k in keep.items():
        b = before(t)
        for c in k["cands"]:
            i = b.get((c["R"], c["reg"]))
            mine = None if i is None else [(s[0], s[1], s[2] if s[1] == "F" else "", hstr(s[3]) if s[1] == "H" else "") for s in i["seals"]]
            theirs = [(s.get("slot"), s.get("state"), (s.get("name") or "") if s.get("state") == "F" else "",
                       hstr(s.get("history") or {}) if s.get("state") == "H" else "") for s in (c["seal_raw"] or [])]
            a_chk += 1
            if mine == theirs:
                a_ok += 1
            elif len(a_bad) < 10:
                a_bad.append(f"t{t} {c['R']}：記憶 {mine} 注意 {theirs}")
    chk("注意の記録の候補の seal 対 戻した記憶（t−1 の終わり）", a_ok == a_chk, f"照らした {a_chk}、同じ {a_ok}；" + " / ".join(a_bad))
    n_cand_vs_defs = sum(1 for t, k in keep.items() if len(k["cands"]) != len(before(t)))
    chk("注意の記録の候補の数＝記憶の定義の数（t−1 の終わり）", n_cand_vs_defs == 0, f"違う試行 {n_cand_vs_defs}")

    door_e = [t for t in trials if L[t]["door"] and L[t]["cue"] == "e"]
    sel_err = [t for t in door_e if L[t]["outcome"] == "wrong" and cap[t]]
    res["counts"] = (len(sel_err), len(door_e))

    def e_fields(t):
        """E の選び（試行 t の場面）。"""
        m = m1rec.get(t)
        er = e_rec.get(t)
        out = dict(E_kind="なし（side に birth/assim が無い）" if m is None else m["kind"], E_R="" if m is None else m["R"],
                   E_route="" if m is None else m.get("route"))
        if m is None:
            out["E_R_is_De"] = ""
        elif m["kind"] == "birth":
            out["E_R_is_De"] = de_birth((m["R"], t))
        else:
            k = find_def(before(t), m["R"])
            out["E_R_is_De"] = "NA：t−1 の記憶に無い" if k is None else before(t)[k]["de"]
        if er is None:
            out.update(E_record="NA：v310be の行が無い")
        elif "x" in er:
            out.update(E_record=f"NA：v310be の x＝{er.get('x')}（E の選びの記録なし）")
        else:
            out.update(E_record="ok")
        return out

    def e_cands(t):
        er = e_rec.get(t)
        if er is None or "x" in er:
            return None
        return er.get("cands") or []

    # ---- 表 1（7）：例外の日のドアの課題ごとの正答の候補
    if g == "7":
        prev_top = {}
        rows1 = []
        for t in door_e:
            k = keep[t]
            b = before(t)
            ty = L[t]["shop_type"]
            correct = [c for c in k["cands"] if c["gate"] and c["hit"]]
            chosen = next((c for c in k["cands"] if c["R"] == k["selected"]), None)
            top = max(correct, key=lambda c: c["q"]) if correct else None   # 同じ q なら candidates の先
            j = lambda f: ";".join(str(f(c)) for c in correct)
            r1 = dict(**base, trial=t, shop_type=ty, outcome=L[t]["outcome"], capable=cap[t],
                      selection_error=(L[t]["outcome"] == "wrong" and cap[t]),
                      selected_R=k["selected"] if k["selected"] is not None else "NA：selected_R が null",
                      selected_reg="NA" if chosen is None else chosen["reg"],
                      selected_q="NA" if chosen is None else DE.fmtf(chosen["q"]),
                      selected_seal="NA" if chosen is None else att_seal_class(chosen["seal_raw"]),
                      selected_is_De=("NA" if chosen is None or (chosen["R"], chosen["reg"]) not in b else b[(chosen["R"], chosen["reg"])]["de"]),
                      n_candidates=len(k["cands"]), n_correct=len(correct),
                      correct_R=j(lambda c: c["R"]), correct_reg=j(lambda c: c["reg"]), correct_q=j(lambda c: DE.fmtf(c["q"])),
                      correct_seal=j(lambda c: att_seal_class(c["seal_raw"])),
                      correct_seal_history=j(lambda c: c["seal"]["history"]),
                      correct_is_De=j(lambda c: b.get((c["R"], c["reg"]), {}).get("de", "NA")),
                      correct_is_De_birth=j(lambda c: de_birth((c["R"], c["reg"]))),
                      correct_assim_count=j(lambda c: b.get((c["R"], c["reg"]), {}).get("assim", "NA")),
                      top_correct_R="" if top is None else top["R"], top_correct_reg="" if top is None else top["reg"],
                      top_correct_q="" if top is None else DE.fmtf(top["q"]),
                      top_correct_changed_same_type=("" if prev_top.get(ty) is None or top is None else (top["R"], top["reg"]) != prev_top[ty]),
                      n_De_in_memory=sum(v["de"] for v in b.values()),
                      **e_fields(t))
            if top is not None:
                prev_top[ty] = (top["R"], top["reg"])
            rows1.append(r1)
        res["tables"]["t1"] = rows1
        # 種・お店の型ごとのまとめ（型ごとにドアの正解が違うので、正答の候補の入れ替わりは同じ型の中で数える）
        summ = []
        for ty in sorted({r["shop_type"] for r in rows1}):
            rr = [r for r in rows1 if r["shop_type"] == ty]
            errs = [r for r in rr if r["selection_error"]]
            s = dict(**base, shop_type=ty, door_exception_tasks=len(rr), selection_errors=len(errs),
                     error_trials=";".join(str(r["trial"]) for r in errs),
                     errors_trial_lt300=sum(r["trial"] < 300 for r in errs), errors_trial_ge300=sum(r["trial"] >= 300 for r in errs),
                     first_error_trial=errs[0]["trial"] if errs else "", last_error_trial=errs[-1]["trial"] if errs else "",
                     top_correct_changes_all=sum(r["top_correct_changed_same_type"] is True for r in rr),
                     top_correct_change_trials=";".join(str(r["trial"]) for r in rr if r["top_correct_changed_same_type"] is True),
                     top_correct_distinct=len({(r["top_correct_R"], r["top_correct_reg"]) for r in rr if r["top_correct_R"]}),
                     top_correct_sequence=" → ".join(f"{R}@{rg}" for i, (R, rg) in enumerate((r["top_correct_R"], r["top_correct_reg"]) for r in rr if r["top_correct_R"])
                                                     if i == 0 or (R, rg) != [(x["top_correct_R"], x["top_correct_reg"]) for x in rr if x["top_correct_R"]][i - 1]))
            if errs:
                le = errs[-1]["trial"]
                s["top_correct_changes_to_last_error"] = sum(r["top_correct_changed_same_type"] is True for r in rr if r["trial"] <= le)
                after = next((r for r in rr if r["trial"] > le and r["top_correct_R"]), None)
                if after is None:
                    s.update(next_task_trial="NA：最後の選び間違いの後に、同じ型で正答の候補のある課題が無い")
                else:
                    ka = (after["top_correct_R"], after["top_correct_reg"])
                    ta = after["trial"]
                    at_err_corr = sum(any((R, int(rg)) == ka for R, rg in zip(r["correct_R"].split(";"), r["correct_reg"].split(";")) if R)
                                      for r in errs)
                    at_err_top = sum((r["top_correct_R"], r["top_correct_reg"]) == ka for r in errs)
                    assim = [t for t, m in m1rec.items() if m["kind"] == "assim" and m["R"] == ka[0] and ka[1] < t < ta]
                    assim_before_le = [t for t in assim if t <= le]
                    s.update(next_task_trial=ta, R_after=ka[0], R_after_reg=ka[1], R_after_q=after["top_correct_q"],
                             R_after_is_De=after["correct_is_De"].split(";")[after["correct_R"].split(";").index(ka[0])],
                             R_after_is_De_birth=de_birth(ka),
                             R_after_born_after_last_error=ka[1] > le,
                             R_after_born_after_first_error=ka[1] > errs[0]["trial"],
                             R_after_correct_at_error_tasks=at_err_corr, R_after_top_at_error_tasks=at_err_top,
                             R_after_assim_until_next_task=len(assim),
                             R_after_assim_until_next_task_cue_e=sum(L[t]["cue"] == "e" for t in assim),
                             R_after_assim_until_last_error=len(assim_before_le),
                             R_after_assim_until_last_error_cue_e=sum(L[t]["cue"] == "e" for t in assim_before_le),
                             R_after_assim_last_error_to_next_task_cue_e=sum(L[t]["cue"] == "e" for t in assim if t > le))
                    s["pattern"] = ("b：最後の選び間違いより後に生まれた定義" if ka[1] > le else
                                    "a：選び間違いの課題でも正答の候補だった定義" if at_err_corr > 0 else
                                    "c：最後の選び間違いより前に生まれたが、選び間違いの課題では正答の候補でなかった定義")
            else:
                s["pattern"] = "選び間違いなし"
            births_de = sorted(t2 for (R, t2), i in birth_info.items() if i is not None and i["de"] and L[t2]["shop_type"] == ty)
            s["De_births_this_type"] = len(births_de)
            s["De_birth_trials_this_type"] = ";".join(map(str, births_de))
            s["De_births_trial_lt300_this_type"] = sum(t < 300 for t in births_de)
            s["births_same_trial_retired_all_types"] = sum(i is None for i in birth_info.values())
            ex_assim = [t for t, m in m1rec.items() if m["kind"] == "assim" and L[t]["cue"] == "e" and L[t]["shop_type"] == ty]
            s["exception_scenes_assimilated_this_type"] = len(ex_assim)
            s["exception_scenes_assimilated_into_De_this_type"] = sum(
                1 for t in ex_assim if (lambda k: k is not None and before(t)[k]["de"])(find_def(before(t), m1rec[t]["R"])))
            s["exception_scenes_born_this_type"] = sum(1 for t, m in m1rec.items() if m["kind"] == "birth" and L[t]["cue"] == "e" and L[t]["shop_type"] == ty)
            summ.append(s)
        res["tables"]["t1_summary"] = summ

    # ---- E の選び（例外の日の場面）：1・7
    if g in ("1", "7"):
        rows = []
        for t in trials:
            if L[t]["cue"] != "e":
                continue
            ef = e_fields(t)
            cs = e_cands(t)
            r = dict(**base, trial=t, shop_type=L[t]["shop_type"], door_task=L[t]["door"], outcome=L[t]["outcome"], **ef,
                     n_De_in_memory_before=sum(v["de"] for v in before(t).values()))
            if cs is None:
                r.update(K_chosen="NA", K_new="NA", K_best_existing="NA", R_best_existing="NA", n_cands_recorded="NA")
            else:
                er = e_rec[t]
                new = [c for c in cs if c[0] is None]
                old = [c for c in cs if c[0] is not None]
                bo = min(old, key=lambda c: c[4]) if old else None
                r.update(K_chosen=er.get("K"), ties=er.get("ties"),
                         K_new=new[0][4] if new else ("NA：新しい定義は候補から外れた（" + str(er.get("new_excluded")) + "）" if er.get("new_excluded")
                                                     else "NA：記録の 12 件に無い"),
                         K_best_existing=bo[4] if bo else "NA：既存の定義の候補が記録に無い",
                         R_best_existing=bo[0] if bo else "",
                         R_best_existing_is_De=("" if bo is None else (lambda k: "NA" if k is None else before(t)[k]["de"])(find_def(before(t), bo[0]))),
                         n_cands_recorded=len(cs))
            rows.append(r)
        res["tables"]["e_exception_days"] = rows

    # ---- 表 2（1）：例外の定義ごとのシールの席の移り変わり
    if g == "1":
        ever_de = {k for i in infos.values() for k, v in i.items() if v["de"]}
        ev_by_def = defaultdict(list)
        for e in seal_events:
            ev_by_def[(e["R"], e["reg"])].append(e)
        lamE = lambda t: (e_rec.get(t) or {}).get("lam", "NA：その試行の v310be に lam が無い")
        rows_ev = []
        for e in seal_events:
            k = (e["R"], e["reg"])
            t = e["trial"]
            cv = conv_by.get((t, e["R"], e["slot"]), [])
            vfh = [c for c in cv if c[0] == "FH"]
            vhu = [c for c in cv if c[0] == "HU"]
            cand = e.get("cand") or {}
            hb = before(t).get(k)
            ha = infos.get(t, {}).get(k)
            rows_ev.append(dict(**base, R=e["R"], reg=e["reg"], slot=e["slot"], trial=t, cue=L[t]["cue"],
                                **{"from": e["from"], "to": e["to"]},
                                is_De_birth=de_birth(k), is_De_before="" if hb is None else hb["de"], is_De_after="" if ha is None else ha["de"],
                                seal_history_before="" if hb is None else seal_txt(hb)["history"],
                                seal_name_before="" if hb is None else seal_txt(hb)["name"],
                                seal_history_after="" if ha is None else seal_txt(ha)["history"],
                                V_FH=";".join(repr(c[3]) for c in vfh), why_FH=";".join(str(c[5]) for c in vfh),
                                V_HU=";".join(repr(c[3]) for c in vhu), why_HU=";".join(str(c[5]) for c in vhu),
                                dC_FH=";".join(str(c[4]) for c in vfh), dC_HU=";".join(str(c[4]) for c in vhu),
                                lambda_conv=lam_conv, lambda_E=lamE(t), lambda_ledger=L[t]["lam_ledger"] if L[t]["lam_ledger"] is not None else "null",
                                shop_cand_kind=cand.get("kind", ""), shop_cand_V=cand.get("V", ""), shop_cand_num=cand.get("num", ""),
                                shop_cand_den=cand.get("den", ""), shop_cand_RF=cand.get("RF", ""), shop_cand_RH=cand.get("RH", ""),
                                shop_cand_RU=cand.get("RU", ""),
                                retire_in_v39=(e["R"] in (v39rec.get(t) or {}).get("retire", []))))
        res["tables"]["t2_events"] = rows_ev
        rows_def = []
        keys = sorted(ever_de | {k for k, i in birth_info.items() if i is not None and i["de"]}, key=lambda k: (k[1], k[0]))
        for k in keys:
            evs = ev_by_def.get(k, [])
            bi = birth_info.get(k) if k in birth_info else infos.get(k[1], {}).get(k)
            bt = seal_txt(bi)
            de_ts = [t for t in trials if k in infos[t] and infos[t][k]["de"]]
            fh = [e for e in evs if e["from"] == "F" and e["to"] in ("H", "U")]
            hu = [e for e in evs if (e["from"] == "H" and e["to"] == "U") or (e["from"] == "F" and e["to"] == "U")]
            gone = [e for e in evs if e["to"] == "定義ごと消えた"]
            present = [t for t in trials if k in infos[t]]
            last_present = present[-1] if present else None
            retire_t = gone[0]["trial"] if gone else ("" if last_present == trials[-1] else f"NA：shop.jsonl に「定義ごと消えた」が無い（最後に記憶にいた試行 {last_present}）")
            vconv = lambda e, kind: ";".join(repr(c[3]) for c in conv_by.get((e["trial"], e["R"], e["slot"]), []) if c[0] == kind) or "NA：v39 の conv に無い"
            assim = [t for t, m in m1rec.items() if m["kind"] == "assim" and m["R"] == k[0] and t > k[1]
                     and (not gone or t <= gone[0]["trial"])]
            born = [e for e in evs if e["from"] == "生まれた"]
            rows_def.append(dict(**base, R=k[0], reg=k[1], birth_cue=L[k[1]]["cue"], birth_shop_type=L[k[1]]["shop_type"],
                                 birth_seal_state=bt["state"], birth_seal_name=bt["name"], birth_seal_history=bt["history"],
                                 birth_seal_shop=";".join(e["to"] for e in born) or "NA：shop.jsonl に生まれた行が無い",
                                 is_De_birth=de_birth(k),
                                 De_first_trial=de_ts[0] if de_ts else "", De_last_trial=de_ts[-1] if de_ts else "", De_trials=len(de_ts),
                                 seal_path=" → ".join([born[0]["to"] if born else "?"] + [e["to"] for e in evs if e["from"] != "生まれた"]),
                                 FH_trial=";".join(str(e["trial"]) for e in fh), V_at_FH=";".join(vconv(e, "FH") for e in fh),
                                 why_FH=";".join(";".join(str(c[5]) for c in conv_by.get((e["trial"], e["R"], e["slot"]), []) if c[0] == "FH") for e in fh),
                                 seal_history_at_FH=";".join(seal_txt(infos.get(e["trial"], {}).get(k))["history"] for e in fh),
                                 HU_trial=";".join(str(e["trial"]) for e in hu), V_at_HU=";".join(vconv(e, "HU") for e in hu),
                                 why_HU=";".join(";".join(str(c[5]) for c in conv_by.get((e["trial"], e["R"], e["slot"]), []) if c[0] == "HU") for e in hu),
                                 seal_history_before_HU=";".join(seal_txt(before(e["trial"]).get(k))["history"] for e in hu),
                                 lambda_conv=lam_conv,
                                 lambda_E_at_FH=";".join(str((e_rec.get(e["trial"]) or {}).get("lam", "NA")) for e in fh),
                                 lambda_E_at_HU=";".join(str((e_rec.get(e["trial"]) or {}).get("lam", "NA")) for e in hu),
                                 retire_trial=retire_t, retire_in_v39=";".join(str(t) for t in retire_at.get(k[0], []) if t >= k[1]),
                                 alive_at_end=(last_present == trials[-1]),
                                 assim_total=len(assim), assim_cue_e=sum(L[t]["cue"] == "e" for t in assim),
                                 assim_cue_n=sum(L[t]["cue"] == "n" for t in assim),
                                 assim_count_last=(infos[last_present][k]["assim"] if last_present is not None else "NA")))
        res["tables"]["t2_defs"] = rows_def

    # ---- 表 3（1・5）：選び間違いの一件ごと
    if g in ("1", "5"):
        rows3 = []
        for t in sel_err:
            k = keep[t]
            b = before(t)
            correct = [c for c in k["cands"] if c["gate"] and c["hit"]]
            chosen = next((c for c in k["cands"] if c["R"] == k["selected"]), None)
            others = [c for c in k["cands"] if c is not chosen and not (c["gate"] and c["hit"])]
            cls = [att_seal_class(c["seal_raw"]) for c in others]
            ckey = None if chosen is None else (chosen["R"], chosen["reg"])
            corr_keys = {(c["R"], c["reg"]) for c in correct}
            mem_Fn = [kk for kk, v in b.items() if v["Fn"] and kk != ckey]
            mem_Fn_nc = [kk for kk in mem_Fn if kk not in corr_keys]
            rows3.append(dict(
                **base, trial=t, shop_type=L[t]["shop_type"], selected_R=k["selected"] if k["selected"] is not None else "NA：selected_R が null",
                selected_reg="NA" if chosen is None else chosen["reg"],
                selected_seal="NA" if chosen is None else att_seal_class(chosen["seal_raw"]),
                selected_seal_history="NA" if chosen is None else chosen["seal"]["history"],
                selected_q="NA" if chosen is None else DE.fmtf(chosen["q"]),
                selected_gate_passed="NA" if chosen is None else chosen["gate"],
                selected_is_De="NA" if ckey not in b else b[ckey]["de"],
                selected_is_De_birth="NA" if ckey is None else de_birth(ckey),
                n_correct=len(correct), correct_R=";".join(c["R"] for c in correct),
                correct_seal=";".join(att_seal_class(c["seal_raw"]) for c in correct),
                correct_seal_history=";".join(c["seal"]["history"] for c in correct),
                correct_is_De=";".join(str(b.get((c["R"], c["reg"]), {}).get("de", "NA")) for c in correct),
                n_candidates=len(k["cands"]), n_defs_attention=k["n_defs_att"], n_others=len(others),
                others=";".join(f"{c['R']}@{c['reg']}:{x}:{c['seal']['history']}:gate={c['gate']}" for c, x in zip(others, cls)),
                n_others_F_sig_n=sum(x == "F sig_n" for x in cls), n_others_F_sig_e=sum(x == "F sig_e" for x in cls),
                n_others_H_sig_e=sum(x == "H sig_e あり" for x in cls), n_others_H_no_sig_e=sum(x == "H sig_e なし" for x in cls),
                n_others_U=sum(x == "U" for x in cls), n_others_no_seal=sum(x == "シールの席なし" for x in cls),
                n_others_F_sig_n_gate_passed=sum(x == "F sig_n" and c["gate"] for c, x in zip(others, cls)),
                other_F_sig_n_present=any(x == "F sig_n" for x in cls),
                memory_n_defs=len(b), memory_n_F_sig_n_excl_selected=len(mem_Fn),
                memory_n_F_sig_n_excl_selected_and_correct=len(mem_Fn_nc),
                memory_n_De=sum(v["de"] for v in b.values())))
        res["tables"]["t3"] = rows3

    # ---- 表 4（1）：D_e の数の推移・誕生
    if g == "1":
        rows4 = []
        de_birth_keys = {k for k, i in birth_info.items() if i is not None and i["de"]}
        for t in trials:
            i = infos[t]
            m = m1rec.get(t)
            rows4.append(dict(**base, trial=t, cue=L[t]["cue"], door_task=L[t]["door"], n_defs=len(i),
                              n_De=sum(v["de"] for v in i.values()), n_De_F_sig_e=sum(v["Fe"] for v in i.values()),
                              n_De_H_sig_e=sum(v["He"] and not v["Fe"] for v in i.values()),
                              n_De_birth_alive=sum(k in de_birth_keys for k in i), n_F_sig_n=sum(v["Fn"] for v in i.values()),
                              E_kind="" if m is None else m["kind"],
                              birth_is_De=("" if m is None or m["kind"] != "birth" else de_birth((m["R"], t)))))
        res["tables"]["t4_trials"] = rows4
        rows4b = []
        for t in sorted(m1rec):
            m = m1rec[t]
            if m["kind"] != "birth":
                continue
            k = (m["R"], t)
            b = before(t)
            bi = birth_info.get(k)
            bt = seal_txt(bi)
            ex_de = sorted((kk for kk, v in b.items() if v["de"]), key=lambda kk: (kk[1], kk[0]))
            cs = e_cands(t)
            r = dict(**base, trial=t, R=m["R"], route=m.get("route"), cue=L[t]["cue"], shop_type=L[t]["shop_type"], door_task=L[t]["door"],
                     birth_seal_state=bt["state"] if bi is not None else "NA：誕生と同じ試行で退役（記憶に残らない）",
                     birth_seal_name=bt["name"] if bi is not None else "NA", birth_seal_history=bt["history"] if bi is not None else "NA",
                     is_De_birth=de_birth(k), n_defs_before=len(b), n_De_before=len(ex_de),
                     De_before=";".join(f"{kk[0]}@{kk[1]}" for kk in ex_de))
            if cs is None:
                er = e_rec.get(t)
                why = "NA：v310be の行が無い" if er is None else f"NA：v310be の x＝{er.get('x')}（E の選びの記録なし）"
                r.update(E_record=why, K_new=why, K_best_existing=why, De_before_E_scores=why)
            else:
                er = e_rec[t]
                new = [c for c in cs if c[0] is None]
                old = [c for c in cs if c[0] is not None]
                bo = min(old, key=lambda c: c[4]) if old else None
                full = len(cs) >= 12
                def score_of(kk):
                    hit = [c for c in old if c[0] == kk[0]]
                    if hit:
                        c = hit[0]
                        return f"{kk[0]}@{kk[1]}:K={c[4]}:A={c[1]}:r={c[2]}:dC={c[3]}:K-K_new={'NA' if not new else round(c[4] - new[0][4], 6)}"
                    return (f"{kk[0]}@{kk[1]}:NA（記録は K の小さい順に 12 件までで、打ち切りか取り込み不可かは分からない。記録の最大の K＝{max(c[4] for c in cs)}）" if full else
                            f"{kk[0]}@{kk[1]}:NA（E の候補の記録に無い。記録が 12 件未満なので、hypo_m1 が None＝取り込み不可）")
                r.update(E_record="ok", ties=er.get("ties"), lam_E=er.get("lam"), n_cands_recorded=len(cs),
                         K_new=new[0][4] if new else "NA：新しい定義の行が無い", A_new=new[0][1] if new else "NA",
                         r_new=new[0][2] if new else "NA", dC_new=new[0][3] if new else "NA",
                         R_best_existing=bo[0] if bo else "NA：既存の定義の候補が記録に無い",
                         R_best_existing_is_De=("" if bo is None else (lambda kk: "NA" if kk is None else b[kk]["de"])(find_def(b, bo[0]))),
                         K_best_existing=bo[4] if bo else "NA", A_best_existing=bo[1] if bo else "NA",
                         r_best_existing=bo[2] if bo else "NA", dC_best_existing=bo[3] if bo else "NA",
                         K_best_existing_minus_K_new=(round(bo[4] - new[0][4], 6) if bo and new else "NA"),
                         De_before_E_scores=";".join(score_of(kk) for kk in ex_de))
            rows4b.append(r)
        res["tables"]["t4_births"] = rows4b
    res["status"] = "ok"
    return res


TABLES = {
    "t1": ("t1_7a_door_exception_tasks.csv", "7a/7b：例外の日のドアの課題ごとの正答の候補（R・q）と、その試行の E の選び"),
    "t1_summary": ("t1_7a_seed_summary.csv", "7a/7b：種・お店の型ごとのまとめ（選び間違いの試行・正答の候補の入れ替わり・同化・D_e の誕生）"),
    "e_exception_days": ("e_choice_exception_days.csv", "1a/1b・7a/7b：例外の日の場面ごとの E の選び（同化先・誕生、K）"),
    "t2_defs": ("t2_1a_exception_defs.csv", "1a/1b：D_e（誕生で、又はその時点で）ごとのシールの席の移り変わり・V・λ・退役"),
    "t2_events": ("t2_1a_seal_events.csv", "1a/1b：全定義のシールの席の移り変わり（shop.jsonl）一行ずつ、V（v39 の conv）・λ"),
    "t3": ("t3_1a_5a_wrong_picks.csv", "1a/1b・5a/5b：例外の日のドアの課題の選び間違いの一件ごと、選んだ定義とほかの候補のシール"),
    "t4_trials": ("t4_1a_De_per_trial.csv", "1a/1b：試行ごとの D_e の数"),
    "t4_births": ("t4_1a_births.csv", "1a/1b：誕生ごと（D_e かどうか・その時の既存の D_e・E の候補の点）"),
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--only", help="試しに一本だけ（例 1a,1）")
    a = ap.parse_args()
    out = Path(a.out)
    sel = list(csv.DictReader(open(V / "selection.tsv"), delimiter="\t"))
    jobs, absent = [], []
    for s in sel:
        if s["row"][0] not in GROUPS or int(s["world"]) != WORLD:
            continue
        if not s["run"]:
            absent.append(f"{s['row']} 種 {s['seed']}：未完（持ち帰っていない）")
            continue
        jobs.append((s["row"], int(s["world"]), int(s["seed"]), s["run"], s["version"]))
    if a.only:
        r, sd = a.only.split(",")
        jobs = [j for j in jobs if j[0] == r and j[2] == int(sd)]
    with Pool(a.workers) as pool:
        results = pool.map(one_run, jobs, chunksize=1)
    results.sort(key=lambda r: ("175".index(r["base"]["row"][0]), r["base"]["row"], r["base"]["seed"]))
    for key, (fname, _) in TABLES.items():
        rows = [x for r in results for x in r["tables"].get(key, [])]
        if not rows:
            continue
        fields = []
        for x in rows:
            for k in x:
                if k not in fields:
                    fields.append(k)
        p = out / fname
        with open(p, "x", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fields, restval="")
            w.writeheader()
            w.writerows(rows)
    checks = [c for r in results for c in r["checks"]]
    with open(out / "checks.csv", "x", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["row", "world", "seed", "run", "version", "check", "ok", "detail"])
        w.writeheader()
        w.writerows(checks)
    tot = {g: [0, 0, 0] for g in GROUPS}
    for r in results:
        if r["status"] == "ok":
            g = r["base"]["row"][0]
            tot[g][0] += r["counts"][0]
            tot[g][1] += r["counts"][1]
            tot[g][2] += 1
    na_runs = [f"{r['base']['row']} 種 {r['base']['seed']}（{r['base']['run']}）：{r['status']}" for r in results if r["status"] != "ok"]
    meta = dict(
        made_at=datetime.now().isoformat(timespec="seconds"),
        rule="受け箱の指示 84 の 4・5（理解の場の決定 10/10 16:26・18:39、記録を読むだけ、探りの数え）",
        script="exception_defs.py（nice -n 15 python3 exception_defs.py --out . --workers 3）",
        world=WORLD, rows="1a/1b・5a/5b・7a/7b（door_errors.py と同じく a と b を合わせ、種 1〜20）。指示の「1a」「5a」「7a」はこの合わせ方で読んだ",
        selection="~/surface/wave1_view/selection.tsv（sha256 feb81a47775b85b6f9a8954807550d4e601998921d21c293ba240657cc71f6da）",
        runs_absent=absent, runs_na=na_runs or "なし",
        totals_vs_door_errors={f"{g}a/{g}b": dict(selection_error=tot[g][0], door_exception_tasks=tot[g][1], runs=tot[g][2],
                                                  door_errors_20261010_1211=EXPECTED[g], same=tuple(tot[g][:2]) == EXPECTED[g])
                               for g in GROUPS},
        tables={v[0]: v[1] for v in TABLES.values()},
        definitions={
            "課題・例外の日・ドアの課題・誤答・capable・選び間違い・選んだ定義・正答の候補・q":
                "door_errors.py（~/surface/door_errors/meta.json）と同じ。q＝q_numerator/q_denominator",
            "シールの席": "side/*/seedNNN.shop.jsonl の kind=shop_seat・which=sig に出る (R, reg, slot)",
            "席の状態 F/H/U": "台帳の state_snapshot を積んで戻した記憶で、alive なら F、slot_history に (R, slot) の鍵があれば H（空の表 {} も H）、ほかは U（tools/v39.seat_state・d_skeleton.py と同じ）",
            "F の名前（sig_n・sig_e）": "F の席の relation.predicate。F→H で predicate は ⟨消去⟩ になるので、H の名前は履歴の表だけで見る",
            "D_e（その時点）": "シールの席が F で名前 sig_e、又は H で履歴の表に sig_e が 1 以上。記録に D_e という欄は無い。この定義で数えた",
            "D_e（誕生で）": "誕生の試行（registered_at＝side の kind=birth の trial）の終わりの記憶で D_e（その時点）に当たる定義。誕生と同じ試行で退役した定義は NA",
            "D_n の F[sig_n]": "シールの席が F で名前 sig_n の定義",
            "その試行の前の記憶": "試行 t の予測・E の選びの時の記憶＝試行 t−1 の終わりの記憶（注意の記録の seal と照合、checks.csv）",
            "誕生・同化": "side/*/seedNNN.jsonl の kind=birth（誕生）・kind=assim（同化、m1 が既存の定義を登録し直した）。試行 t の場面を登録した",
            "E の選び": "side の kind=v310be（tools/v310be.py choose_and_register）。chosen が null＝新しい定義（誕生）、reg＝登録した定義。cands＝[R(null＝新), A, r, ΔC, K, 内訳] を K の小さい順に 12 件まで。K＝A＋r＋λ_E·ΔC、最小の K を選ぶ",
            "C* の点（取り込み先の点）": "記録に「C* の点」という欄は無い。1 の行は match_cstar_e が真で、E の r（書換ビット）は C* の照合の下で計られる（tools/cstar_runtime.py の rewrite の包み）。そこで取り込み先の候補の K・A・r・ΔC を並べた",
            "V": "シールの席の変換（F→H・H→U）の時の V は side の kind=v39 の conv（[種類, R, 席, V, ΔC, why, 同点の数]、tools/v39.run_conversions）。shop.jsonl の cand.V は、その試行で最後に計った候補の値（変換の後に計り直した値で上書きされることがある）なので別の欄（shop_cand_*）に置いた",
            "λ": "記録に試行ごとの変換の λ の欄は無い。変換の λ＝flag.json の v39_price（走行の定数、V＜λ で変換、tools/v39.py の LAM＝CFG['price']）。E の λ＝side の v310be の lam（flag.json の e_price と同じ値）。台帳の lambda 欄は null（lambda_ledger 欄）",
            "退役": "shop.jsonl の to＝「定義ごと消えた」の試行（v39 の retire とも照らした：retire_in_v39 欄）",
            "t1 の top_correct": "正答の候補のうち q が最大の候補（同じ q なら candidates の先）。top_correct_changed_same_type＝同じお店の型（台帳の shop_type、甲・乙でドアの正解が違う）の一つ前の例外の日のドアの課題の top_correct と (R, reg) が違う",
            "t1_summary の pattern": "機械的な分け：R_after（同じ型で、最後の選び間違いの後の最初の課題の top_correct）が、b＝最後の選び間違いより後に生まれた／a＝選び間違いの課題でも正答の候補だった／c＝前に生まれたが選び間違いの課題では正答の候補でなかった。良し悪しの判断ではない",
            "t3 の others": "注意の記録の候補のうち、選んだ定義でも正答の候補（gate_passed かつ hit）でもないもの。書式 R@reg:分類:履歴:gate=gate_passed",
        },
        fields={
            "row,world,seed,run,version": "selection.tsv",
            "trial,cue,door_task,outcome,capable,selection_error": "台帳の prediction_order・shop_cue・held_out_is_door・hit・predicted_edge と注意の記録（capable）",
            "selected_*,correct_*,n_candidates,n_correct,*_q,*_seal,*_seal_history,n_defs_attention": "注意の記録 attention/*/seedNNN.jsonl.gz（seal は F 名前／H sig_e あり・なし／U に分類）",
            "*_is_De,*_assim_count,n_De_*,memory_*,n_defs*,n_F_sig_n,seal_history_*,seal_name_*,birth_seal_*": "台帳の state_snapshot から戻した記憶（試行の前＝t−1 の終わり、誕生＝誕生の試行の終わり）",
            "*_is_De_birth": "上の D_e（誕生で）",
            "E_kind,E_R,E_route": "side の kind=birth/assim",
            "E_record,K_*,A_*,r_*,dC_*,ties,lam_E,n_cands_recorded,R_best_existing*,De_before_E_scores": "side の kind=v310be",
            "from,to,slot,birth_seal_shop,retire_trial,seal_path": "shop.jsonl（which=sig）",
            "V_FH,V_HU,why_FH,why_HU,dC_FH,dC_HU,V_at_FH,V_at_HU,retire_in_v39": "side の kind=v39 の conv・retire",
            "shop_cand_*": "shop.jsonl の cand（その試行で最後に計った変換の候補の値）",
            "lambda_conv": "flag.json の v39_price", "lambda_E,lambda_E_at_*": "side の v310be の lam", "lambda_ledger": "台帳の lambda 欄",
            "assim_*,R_after_assim_*,exception_scenes_*": "side の kind=assim/birth と台帳の shop_cue",
        },
        source_code="~/sfn/sfn-compression-abm の c7921598 の tools/v39.py・tools/v310be.py・tools/shopworld.py・tools/cstar_runtime.py・tools/v3_run.py・abm/loop.py を読んで合わせた。abm/loop.py・tools/shopworld.py は 4 版で同じ中身、tools/v39.py・tools/v310be.py は c7921598＝4ceadf63、c57467ea＝e9ed84a（記録の形は同じとして読んだ）",
        reused="~/surface/door_errors/door_errors.py（sha256 642edea6447698057a9f16de1113e961bd922ba116126f33f0cf99e393a4ac3b）の rows_gz・one・seal_fields・fmtf を import。記憶の戻し方は d_skeleton_20261010_1622/d_skeleton.py と同じ（abm.loop._apply、ソースは /mnt/d/sfn_runs/scratch_exception_defs_20261010/src_c792 に c7921598 から git archive）",
        not_read="side の sme.jsonl.gz・sme.states.jsonl.gz・routing.jsonl・answers.csv・ambig.csv、stage2、evictions は読んでいない",
    )
    (out / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(meta["totals_vs_door_errors"], ensure_ascii=False))
    print("NA の本：", na_runs)
    print("checks で ok でないもの：", sum(1 for c in checks if c["ok"] is False))


if __name__ == "__main__":
    sys.exit(main())

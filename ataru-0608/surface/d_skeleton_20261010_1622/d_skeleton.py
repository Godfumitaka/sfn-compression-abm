"""受け箱の指示 80 C（探り、新しい走行なし、既存の記録を読むだけ）。

お店の D（#10 τ0.4・#11 τ0.15）と D＋注意（#12 τ0.4・#13 τ0.15）、世界 1・2、種 1〜3 の 24 本について
 (i)  注意の重み a（上位の鍵と値、シールの位置の鍵の a）を試行 500・1000・1500・1739（最後）で
 (ii) 記憶の中の定義ごとの席の状態（F/H/U）、シールが F でほかの席の大半が U の「骨だけ」の定義
を数える。

読むもの（どれも読むだけ）：
  D:  /mnt/d/sfn_runs/cloud/<run>/output/ledgers/cells/<cell>/seedNNN.jsonl.gz   台帳（state_snapshot の差分を
      abm.loop._apply で積み、agent_state_snapshot_hash と sha256 で照合して全状態を戻す）
  D:  /mnt/d/sfn_runs/cloud/<run>/output/attention/<cell>/seedNNN.jsonl.gz       注意の記録（tools/attnsme.py）
  D:  /mnt/d/sfn_runs/cloud/<run>/output/side/<cell>/seedNNN.shop.jsonl          シールと link の席の移り変わり（照合用）
  小: ~/v33prod/results/ataru-0608/cloud_runs/<run>/seedNNN.useforget.jsonl.gz    D の記録（10 試行ごとの snap、照合用）
  小: ~/v33prod/results/ataru-0608/cloud_runs/<run>/seedNNN.retention.jsonl.gz    D の q・注意の記録（tools/useforget_cstar.py）
版の源：git -C ~/sfn/sfn-compression-abm archive daf69efd | tar -x -C <SRC>（--src で渡す）。

使い方：nice -n 15 python3 d_skeleton.py --src <SRC> --out <この folder>
"""
from __future__ import annotations

import argparse
import csv
import glob
import gzip
import json
import os
import sys
from collections import Counter
from hashlib import sha256

ROWS = {"10": ("D", "0.4"), "11": ("D", "0.15"), "12": ("D+注意", "0.4"), "13": ("D+注意", "0.15")}
WORLDS = (1, 2)
SEEDS = (1, 2, 3)
CHECK = (500, 1000, 1500, 1739)
TOPK = 5
DROOT = "/mnt/d/sfn_runs/cloud"
SROOT = os.path.expanduser("~/v33prod/results/ataru-0608/cloud_runs")
# 試行の場面でのシールの位置の k2 の鍵（tools/attnposition_keys.position_index の形：
# シールは一引数・物、親は link（二引数・関係・関係）の 0 番目、link は親なし）。注意の記録の details で毎回照合する。
SEAL_KEY = json.dumps([[[[[2, ["relation", "relation"]], 0]]], [1, ["entity"]]], separators=(",", ":"))


def one(pattern):
    got = glob.glob(pattern)
    if len(got) != 1:
        raise FileNotFoundError(pattern)
    return got[0]


def role_ids(seed, trials):
    from abm.world import opaque_id
    out = {}
    for t in range(trials):
        out[t] = {opaque_id(seed, t, "relation:shop:sig"): "sig", opaque_id(seed, t, "relation:shop:link"): "link",
                  opaque_id(seed, t, "relation:tree:root"): "root", opaque_id(seed, t, "relation:tree:0.0.0"): "door"}
    return out


def scan_trial(t, st, sig_all, cue_at, type_at, episodes, per_trial):
    """毎試行の状態（台帳の差分を積んだもの）で、シール F・ほかの席の U が半分を超える定義を探す。"""
    sh = st["slot_history"]
    now = {}
    for name, d in st["definitions"].items():
        seal = [c for c in d["constituents"] if c["relation"]["relation_id"] in sig_all]
        if not seal or not seal[0]["alive"]:
            continue
        others = [c for c in d["constituents"] if c is not seal[0]]
        oU = sum((not c["alive"]) and str((name, c["slot_index"])) not in sh for c in others)
        oF = sum(c["alive"] for c in others)
        if others and oU / len(others) > 0.5:
            now[(name, d["registered_at"])] = (seal[0]["relation"]["predicate"], len(others), oU, oF, len(d["constituents"]))
    per_trial["trials_with_skeleton_gt50"] += bool(now)
    per_trial["trials_with_skeleton_allU"] += any(v[2] == v[1] for v in now.values())
    per_trial["skeleton_def_trials"] += len(now)
    op = episodes["open"]
    for key in list(op):
        if key not in now:
            e = op.pop(key)
            d = st["definitions"].get(key[0])
            if d is None or d["registered_at"] != key[1]:
                e["end_reason"] = "定義ごと消えた（退役）"
            else:
                seal = [c for c in d["constituents"] if c["relation"]["relation_id"] in sig_all]
                if seal and not seal[0]["alive"]:
                    e["end_reason"] = "シールが F でなくなった（" + ("H" if str((key[0], seal[0]["slot_index"])) in sh else "U") + "）"
                else:
                    e["end_reason"] = "ほかの席の U が半分以下に戻った"
            e["first_trial_after"] = t
            episodes["closed"].append(e)
    for key, (name, n_other, oU, oF, n) in now.items():
        if key in op:
            e = op[key]
            e["last_trial"] = t
            e["n_trials"] += 1
            e["max_other_U"] = max(e["max_other_U"], oU)
            if name != e["seal_name"]:
                e["seal_name_changed"] = 1
        else:
            op[key] = dict(R=key[0], registered_at=key[1], birth_shop_cue=cue_at.get(key[1], ""),
                           birth_shop_type=type_at.get(key[1], ""), seal_name=name, seal_name_changed=0,
                           n_seats=n, other_seats=n_other, other_U_at_start=oU, other_F_at_start=oF,
                           start_trial=t, last_trial=t, n_trials=1, max_other_U=oU, end_reason="", first_trial_after="")


def run_one(row, world, seed, writers, checks):
    from abm.loop import _apply, _json_bytes
    arm, tau = ROWS[row]
    run = f"wave2_{row}_w{world}_s{seed}_cdaf"
    out = os.path.join(DROOT, run, "output")
    small = os.path.join(SROOT, run)
    base = dict(run=run, row=row, arm=arm, tau=tau, world=world, seed=seed)
    ledger = one(f"{out}/ledgers/cells/*/seed{seed:03d}.jsonl.gz")
    attention = one(f"{out}/attention/*/seed{seed:03d}.jsonl.gz")
    shop = one(f"{out}/side/*/seed{seed:03d}.shop.jsonl")
    useforget = os.path.join(small, f"seed{seed:03d}.useforget.jsonl.gz")
    retention = os.path.join(small, f"seed{seed:03d}.retention.jsonl.gz")
    flag = json.load(open(os.path.join(out, "flag.json")))
    trials = None
    roles = None
    sig_all = set()
    link_all = set()
    cue_at, type_at = {}, {}
    states = {}
    st = None
    episodes = {"open": {}, "closed": []}
    per_trial = Counter()
    with gzip.open(ledger, "rt", encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            if r.get("record_type") == "run_header":
                trials = int(r["trial_count"])
                if int(r["run_seed"]) != seed or r["code_commit"][:8] != "daf69efd":
                    raise ValueError((run, r["run_seed"], r["code_commit"]))
                roles = role_ids(seed, trials)
                for t in range(trials):
                    for rid, k in roles[t].items():
                        (sig_all if k == "sig" else link_all if k == "link" else set()).add(rid)
                continue
            if r.get("record_type") != "trial":
                continue
            t = r["prediction_order"]
            cue_at[t], type_at[t] = r.get("shop_cue"), r.get("shop_type")
            s = r["state_snapshot"]
            if s["kind"] == "full":
                st = s["value"]
            elif s["kind"] == "delta":
                st = _apply(st, s["changes"])
            else:
                raise ValueError(("snapshot", run, t, s["kind"]))
            scan_trial(t, st, sig_all, cue_at, type_at, episodes, per_trial)
            if t in CHECK:
                ok = sha256(_json_bytes(st)).hexdigest() == r["agent_state_snapshot_hash"]
                checks.append(dict(**base, trial=t, check="ledger_state_hash", ok=ok, detail=""))
                if not ok:
                    raise ValueError(("hash", run, t))
                states[t] = json.loads(json.dumps(st))
    # (ii') 全試行の走査：骨だけの定義の続いた区間
    for key, e in list(episodes["open"].items()):
        e["end_reason"] = "走行の終わりまで続いた"
        episodes["closed"].append(e)
    for e in sorted(episodes["closed"], key=lambda e: (e["start_trial"], e["R"])):
        writers["epi"].writerow(dict(**base, **e))
    writers["any"].writerow(dict(**base, trials=trials, **{k: per_trial[k] for k in ANY_COLS},
                                 episodes=len(episodes["closed"]),
                                 episodes_seal_sig_n=sum(e["seal_name"] == "sig_n" for e in episodes["closed"]),
                                 episodes_seal_sig_e=sum(e["seal_name"] == "sig_e" for e in episodes["closed"]),
                                 episodes_allU_at_some_trial=sum(e["max_other_U"] == e["other_seats"] for e in episodes["closed"])))
    # (ii) 定義ごとの席の状態
    seat_counts = {}
    for t in CHECK:
        s = states[t]
        sh = s["slot_history"]
        summ = Counter(defs=len(s["definitions"]))
        for name, d in sorted(s["definitions"].items()):
            F = H = U = 0
            seal = [c for c in d["constituents"] if c["relation"]["relation_id"] in sig_all]
            link = [c for c in d["constituents"] if c["relation"]["relation_id"] in link_all]
            per = {}
            for c in d["constituents"]:
                key = str((name, c["slot_index"]))
                state = "F" if c["alive"] else ("H" if key in sh else "U")
                per[c["slot_index"]] = state
                F += state == "F"; H += state == "H"; U += state == "U"
            seat_counts[(t, name)] = (F, H, U)
            if len(seal) > 1:
                raise ValueError(("two seals", run, name))
            seal_slot = seal[0]["slot_index"] if seal else None
            seal_state = per[seal_slot] if seal else "シールの席なし"
            seal_name = seal[0]["relation"]["predicate"] if seal and seal_state == "F" else ""
            seal_hist = json.dumps(sh.get(str((name, seal_slot)), {}), ensure_ascii=False, sort_keys=True) if seal and seal_state == "H" else ""
            link_state = ";".join(per[c["slot_index"]] for c in link) if link else "link の席なし"
            others = [v for k, v in per.items() if k != seal_slot]
            oU = sum(v == "U" for v in others)
            frac = oU / len(others) if others else None
            skel = bool(seal and seal_state == "F" and frac is not None and frac > 0.5)
            skel_all = bool(seal and seal_state == "F" and others and oU == len(others))
            reg = d["registered_at"]
            writers["defs"].writerow(dict(**base, trial=t, R=name, registered_at=reg,
                                          birth_shop_cue=cue_at.get(reg, ""), birth_shop_type=type_at.get(reg, ""),
                                          n_seats=len(per), F=F, H=H, U=U, seal_slot="" if seal_slot is None else seal_slot,
                                          seal_state=seal_state, seal_name_if_F=seal_name, seal_history_if_H=seal_hist,
                                          link_state=link_state, other_seats=len(others), other_U=oU,
                                          other_U_frac="" if frac is None else round(frac, 4),
                                          skeleton_gt50=int(skel), skeleton_allU=int(skel_all)))
            summ["F"] += F; summ["H"] += H; summ["U"] += U
            summ["seal_F_sig_n"] += seal_state == "F" and seal_name == "sig_n"
            summ["seal_F_sig_e"] += seal_state == "F" and seal_name == "sig_e"
            summ["seal_H"] += seal_state == "H"
            summ["seal_U"] += seal_state == "U"
            summ["no_seal_seat"] += not seal
            summ["skeleton_gt50"] += skel
            summ["skeleton_gt50_sig_n"] += skel and seal_name == "sig_n"
            summ["skeleton_gt50_sig_e"] += skel and seal_name == "sig_e"
            summ["skeleton_allU"] += skel_all
            summ["skeleton_gt50_born_cue_e"] += skel and cue_at.get(reg) == "e"
        writers["skel"].writerow(dict(**base, trial=t, **{k: summ[k] for k in SKEL_COLS}))
    # 照合 1：useforget の snap（U でない席）と、戻した状態の F・H
    snap_at = {}
    with gzip.open(useforget, "rt", encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            if r["trial"] in CHECK and "snap" in r:
                snap_at[r["trial"]] = r["snap"]
    for t in CHECK:
        if t not in snap_at:
            checks.append(dict(**base, trial=t, check="useforget_snap_FH", ok="記録なし", detail=""))
            continue
        c = Counter()
        sealkind = Counter()
        for name, slot, reg, state, S, kinds in snap_at[t]:
            c[(name, state)] += 1
            if "シール" in kinds:
                sealkind[(name, state)] += 1
        mism = [name for (tt, name), (F, H, U) in seat_counts.items() if tt == t and (c[(name, "F")], c[(name, "H")]) != (F, H)]
        checks.append(dict(**base, trial=t, check="useforget_snap_FH", ok=not mism, detail=";".join(mism)))
    # 照合 2：shop.jsonl のシールの席の最後の to（試行 ≤ t）と、戻した状態のシールの状態
    last = {}
    events_by_t = []
    with open(shop, encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            if r.get("kind") == "shop_seat" and r.get("which") == "sig":
                events_by_t.append(r)
    for t in CHECK:
        last = {}
        for r in events_by_t:
            if r["trial"] <= t:
                last[(r["R"], r["reg"], r["slot"])] = r["to"]
        live = {k: v for k, v in last.items() if v != "定義ごと消えた"}
        s = states[t]
        mine = {}
        for name, d in s["definitions"].items():
            for c in d["constituents"]:
                if c["relation"]["relation_id"] in sig_all:
                    key = str((name, c["slot_index"]))
                    mine[(name, d["registered_at"], c["slot_index"])] = "F" if c["alive"] else ("H" if key in s["slot_history"] else "U")
        checks.append(dict(**base, trial=t, check="shop_jsonl_seal_state", ok=live == mine,
                           detail="" if live == mine else json.dumps([str(set(live.items()) ^ set(mine.items()))], ensure_ascii=False)[:300]))
    # (i) 注意の重み a
    seal_a_series = []
    key_mismatch = 0
    key_reason = Counter()
    updates = Counter()
    a_at = {}
    key_roles = {}
    upd_t = []
    with gzip.open(attention, "rt", encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            t = r["trial"]
            updates[r.get("update_reason")] += 1
            if r.get("updated"):
                upd_t.append(t)
            for c in r.get("candidates", []):
                for d in c.get("details", []):
                    k = roles[t].get(d.get("relation_id"))
                    if d.get("key") is not None:
                        key_roles.setdefault(d["key"], set()).add(k or "other")
                    if k == "sig":
                        if d.get("key") != SEAL_KEY:
                            key_mismatch += 1
                        key_reason[d.get("reason")] += 1
            a = r["a_after"]
            seal_a_series.append((t, a.get(SEAL_KEY)))
            if t in CHECK:
                a_at[t] = (a, r)
    checks.append(dict(**base, trial="", check="attention_seal_key_matches_details", ok=key_mismatch == 0,
                       detail=json.dumps({"mismatch": key_mismatch, "reasons": {str(k): v for k, v in key_reason.items()}}, ensure_ascii=False)))
    vals = [(t, v) for t, v in seal_a_series if v is not None]
    run_max = max(vals, key=lambda x: (x[1], -x[0])) if vals else (None, None)
    for t in CHECK:
        a, r = a_at[t]
        mean = sum(a.values()) / len(a) if a else 0.0
        ranked = sorted(a.items(), key=lambda kv: (-kv[1], kv[0]))
        sa = a.get(SEAL_KEY)
        rank = next((i + 1 for i, (k, _) in enumerate(ranked) if k == SEAL_KEY), None)
        upto = [v for tt, v in vals if tt <= t]
        writers["seal"].writerow(dict(**base, trial=t, n_keys=len(a), a_mean=mean, a_max=ranked[0][1] if ranked else "",
                                      seal_key_present=int(SEAL_KEY in a), seal_a="" if sa is None else sa,
                                      seal_rank="" if rank is None else rank,
                                      seal_weight_w="" if sa is None else (1 + sa) / (1 + mean),
                                      seal_a_max_so_far=max(upto) if upto else "",
                                      seal_a_max_run=run_max[1] if run_max[1] is not None else "",
                                      seal_a_max_run_trial=run_max[0] if run_max[0] is not None else "",
                                      a_updates_so_far=sum(1 for x in upd_t if x <= t)))
        for i, (k, v) in enumerate(ranked[:TOPK]):
            writers["top"].writerow(dict(**base, trial=t, rank=i + 1, key=k, a=v, is_seal_key=int(k == SEAL_KEY),
                                         key_roles_seen="/".join(sorted(key_roles.get(k, {"記録なし"})))))
        if SEAL_KEY in a and (rank or 0) > TOPK:
            writers["top"].writerow(dict(**base, trial=t, rank=rank, key=SEAL_KEY, a=sa, is_seal_key=1,
                                         key_roles_seen="/".join(sorted(key_roles.get(SEAL_KEY, {"記録なし"})))))
    checks.append(dict(**base, trial="", check="attention_update_reasons", ok="", detail=json.dumps(dict(updates), ensure_ascii=False)))
    # (i) の補い：保持 D の記録（useforget_cstar の matching）にあるシールの席の a と重み
    rec = Counter()
    wmax = (None, None, None)
    with gzip.open(retention, "rt", encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            t = r["trial"]
            for m in r.get("matching", []):
                if roles[t].get(m.get("mapped_to")) != "sig":
                    continue
                rec["seal_matching_rows"] += 1
                if m.get("a") is not None:
                    rec["seal_rows_with_a"] += 1
                    if wmax[0] is None or m["weight"] > wmax[0]:
                        wmax = (m["weight"], m["a"], t)
                if m.get("key") is not None and m["key"] != SEAL_KEY:
                    rec["seal_key_differs"] += 1
    writers["ret"].writerow(dict(**base, seal_matching_rows=rec["seal_matching_rows"], seal_rows_with_a=rec["seal_rows_with_a"],
                                 seal_key_differs=rec["seal_key_differs"],
                                 seal_weight_max="" if wmax[0] is None else wmax[0],
                                 seal_a_at_weight_max="" if wmax[1] is None else wmax[1],
                                 trial_at_weight_max="" if wmax[2] is None else wmax[2],
                                 flag_use_forget=flag.get("use_forget"), flag_use_forget_q=flag.get("use_forget_q", False),
                                 flag_use_forget_attn=flag.get("use_forget_attn", False)))
    return run


ANY_COLS = ("trials_with_skeleton_gt50", "trials_with_skeleton_allU", "skeleton_def_trials")
SKEL_COLS = ("defs", "F", "H", "U", "seal_F_sig_n", "seal_F_sig_e", "seal_H", "seal_U", "no_seal_seat",
             "skeleton_gt50", "skeleton_gt50_sig_n", "skeleton_gt50_sig_e", "skeleton_allU", "skeleton_gt50_born_cue_e")
BASE = ["run", "row", "arm", "tau", "world", "seed"]
TABLES = {
    "seal": ("attention_seal_key.csv", BASE + ["trial", "n_keys", "a_mean", "a_max", "seal_key_present", "seal_a", "seal_rank",
                                              "seal_weight_w", "seal_a_max_so_far", "seal_a_max_run", "seal_a_max_run_trial", "a_updates_so_far"]),
    "top": ("attention_top_keys.csv", BASE + ["trial", "rank", "key", "a", "is_seal_key", "key_roles_seen"]),
    "defs": ("seat_states_by_definition.csv", BASE + ["trial", "R", "registered_at", "birth_shop_cue", "birth_shop_type", "n_seats",
                                                      "F", "H", "U", "seal_slot", "seal_state", "seal_name_if_F", "seal_history_if_H",
                                                      "link_state", "other_seats", "other_U", "other_U_frac", "skeleton_gt50", "skeleton_allU"]),
    "skel": ("skeleton_summary.csv", BASE + ["trial", *SKEL_COLS]),
    "ret": ("retention_seal_weight.csv", BASE + ["seal_matching_rows", "seal_rows_with_a", "seal_key_differs", "seal_weight_max",
                                                 "seal_a_at_weight_max", "trial_at_weight_max", "flag_use_forget", "flag_use_forget_q",
                                                 "flag_use_forget_attn"]),
    "epi": ("skeleton_episodes.csv", BASE + ["R", "registered_at", "birth_shop_cue", "birth_shop_type", "seal_name",
                                            "seal_name_changed", "n_seats", "other_seats", "other_U_at_start", "other_F_at_start",
                                            "start_trial", "last_trial", "n_trials", "max_other_U", "end_reason", "first_trial_after"]),
    "any": ("skeleton_all_trials.csv", BASE + ["trials", *ANY_COLS, "episodes", "episodes_seal_sig_n", "episodes_seal_sig_e",
                                               "episodes_allU_at_some_trial"]),
    "checks": ("checks.csv", BASE + ["trial", "check", "ok", "detail"]),
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--only", default=None, help="試しに一本だけ（run 名）")
    args = ap.parse_args()
    sys.path.insert(0, args.src)
    files, writers = {}, {}
    for k, (name, cols) in TABLES.items():
        path = os.path.join(args.out, name)
        if os.path.exists(path):
            raise FileExistsError(path)
        files[k] = open(path, "x", newline="", encoding="utf-8")
        writers[k] = csv.DictWriter(files[k], fieldnames=cols)
        writers[k].writeheader()
    checks = []
    for world in WORLDS:
        for seed in SEEDS:
            for row in ROWS:
                if args.only and args.only != f"wave2_{row}_w{world}_s{seed}_cdaf":
                    continue
                print(run_one(row, world, seed, writers, checks), flush=True)
                for k in files:
                    files[k].flush()
    for c in checks:
        writers["checks"].writerow(c)
    for f in files.values():
        f.close()


if __name__ == "__main__":
    main()

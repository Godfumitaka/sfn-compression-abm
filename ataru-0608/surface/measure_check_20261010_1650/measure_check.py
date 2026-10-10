"""受け箱の指示 80 B：1a・世界 2・種 1〜3 で、「正答できる定義があるか（capable）」の二つの数え方を比べる。読むだけ。
  - 注意の記録：wave1.py の capable_from_attention（attention/<セル>/seedNNN.jsonl.gz の candidates に gate_passed かつ hit の候補がある）。
  - 再生：2a と同じ道具 tools/selcands_sme.py を本番の版（c7921598）で走らせた候補の記録の correct_gate_passed
    （~/surface/replay_measure_check/q1a_w2/seedNNN/。replay.py の status が ok の本、又は下の採用の確かめを全部通った本）。
選び間違い・定義の不在の数は、wave1.py の one_run をそのまま呼ぶ（capable の出どころだけを差し替える）ので、wave1.py と同じ定義：
  選び間違い（selection_error）＝誤答で capable、定義の不在（absent）＝capable でない（全課題）。範囲は 全課題・全日 と ドア課題・例外の日。
採用の確かめ（replay_accept.py と同じ項目）：status、errors が「旗の違い ['config']」だけか無し、flag_diff が config だけか無し、台帳本体の違う行 0、
  side が同じ、候補の記録の行＝台帳本体の行＝manifest の trial_count、設定ファイルの sha256 が本番と同じ、manifest の world_hash・seed_file_sha256 が同じ、
  候補の記録のファイルが一つ。本番の設定の sha256 は、~/surface/replay_config_sha_aws_m7a.txt・_m1.txt に本番の置き場（4cea）が無いので、
  本番の開始の記録（~/cloud/wave1/*_commands.json の config_sha。wave1_start.py が AWS の上で開始の前に sha256 を確かめた値）を使う。
使い方：python3 measure_check.py OUT_DIR
"""
import csv
import glob
import gzip
import hashlib
import json
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

H = Path.home()
sys.path.insert(0, str(H / "surface"))
import wave1  # noqa: E402

ROW, WORLD, ARM, SEEDS = "1a", 2, "q1a_w2", (1, 2, 3)
RDIR = H / "surface/replay_measure_check"
LAUNCH = ("wave1_s1_jsonlog_commands.json", "wave1_w2s2_jsonlog_commands.json", "wave1_s3_20_commands.json")
AWS_LISTS = ("surface/replay_config_sha_aws_m7a.txt", "surface/replay_config_sha_aws_m1.txt")


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def launch_records():
    out = {}
    for f in LAUNCH:
        for c in json.load(open(H / "cloud/wave1" / f)):
            out.setdefault(c["argv"][3], dict(c, launch_file=f))
    return out


def aws_sha():
    a = {}
    for f in AWS_LISTS:
        for l in open(H / f):
            h, p = l.split()[:2]
            a[p] = h
    return a


def accept(seed, launch, aws):
    d = RDIR / ARM / f"seed{seed:03d}"
    rj = json.load(open(d / "replay.json"))
    prod_dir = Path(rj["run_dir"])
    prod = json.load(open(prod_dir / "flag.json"))
    pm = json.loads(open(prod_dir / "manifest.jsonl").readline())
    if rj["status"] == "ok":
        cands = d / "sme.candidates.jsonl.gz"
        rep_cmd = json.load(open(H / "surface/measure_check_cmds_1a_c792.json"))
        rep_cfg = [r["command"][2] for r in rep_cmd if r["seed"] == seed][0]
        rm = None   # ok の本は tmp が消えるので、manifest は replay.py の旗の比べ（config 以外も同じ）で代える
        cg = [str(cands)]
    else:
        tmp = Path(rj["kept_tmp"]) / "out"
        rep = json.load(open(tmp / "flag.json"))
        rep_cfg = rep["config"]
        rm = json.loads(open(tmp / "manifest.jsonl").readline()) if (tmp / "manifest.jsonl").exists() else {}
        cg = sorted(glob.glob(str(tmp / "side/*" / f"seed{seed:03d}.sme.candidates.jsonl.gz")))
    lr = launch.get(json.load(open(prod_dir.resolve().parent / "native_command.json"))[3])
    ps_launch = lr["config_sha"] if lr else None
    ps_aws = aws.get(prod["config"])
    rs = sha(rep_cfg)
    checks = {"status": rj["status"] in ("ok", "failed"),
              "errors_config_only": rj["errors"] in ([], ["旗の違い ['config']"]),
              "flag_diff_config_only": rj.get("flag_diff") in ([], ["config"]),
              "ledger_body_diff_rows_0": rj.get("ledger_body_diff_rows") == 0,
              "side_same": rj.get("side_diff") == {},
              "candidate_rows_all": rj.get("candidate_rows") == rj.get("ledger_body_rows") == pm["trial_count"],
              "config_sha256_same": ps_launch is not None and ps_launch == rs and (ps_aws is None or ps_aws == rs),
              "manifest_world_seed_same": rm is None or (pm["world_hash"], pm["seed_file_sha256"]) == (rm.get("world_hash"), rm.get("seed_file_sha256")),
              "candidates_file_one": len(cg) == 1}
    return dict(adopted=all(checks.values()), checks=checks, replay_status=rj["status"], replay_errors=rj["errors"],
                flag_diff=rj.get("flag_diff"), candidates_path=cg[0] if len(cg) == 1 else None,
                candidates_sha256=sha(cg[0]) if len(cg) == 1 else None,
                production_config=prod["config"], production_config_sha256_launch_record=ps_launch,
                production_config_launch_record=lr["launch_file"] if lr else None,
                production_config_sha256_aws_list=ps_aws, replay_config=rep_cfg, replay_config_sha256=rs,
                production_world_hash=pm["world_hash"], production_seed_file_sha256=pm["seed_file_sha256"],
                replay_world_hash=rm.get("world_hash") if rm else None, replay_seed_file_sha256=rm.get("seed_file_sha256") if rm else None,
                replay_log_tail=Path(rj["kept_tmp"], "log.txt").read_text(errors="replace").splitlines()[-12:] if rj.get("kept_tmp") else None,
                replay_json=rj)


def replay_cap(path):
    cap, cand = {}, {}
    for r in wave1.rows_gz(path):
        if r["trial"] in cap:
            raise SystemExit(f"再生の候補の記録の試行が重なる {r['trial']}")
        cap[r["trial"]] = bool(r["correct_gate_passed"])
        cand[r["trial"]] = dict(chosen_R=r.get("chosen_R"), n_candidates=len(r["candidates"]),
                                gate_hit_R=[c["R"] for c in r["candidates"] if c["gate_passed"] and c["hit"]],
                                hit_R=[c["R"] for c in r["candidates"] if c["hit"]])
    return cap, cand


def partial_rows(path):
    """止まった再生の候補の記録（gzip が途中で切れている）から、読める行だけを読む。"""
    rows = []
    try:
        with gzip.open(path, "rt", encoding="utf-8") as f:
            for line in f:
                rows.append(json.loads(line))
    except (EOFError, json.JSONDecodeError):
        pass
    return rows


def attention_detail(rd, seed):
    a = wave1.one(rd, f"attention/*/seed{seed:03d}.jsonl.gz")
    det = {}
    for r in wave1.rows_gz(a):
        cs = r.get("candidates") or []
        det[r["trial"]] = dict(selected_R=r.get("selected_R"), n_candidates=len(cs),
                               gate_hit_R=[c.get("R") for c in cs if c.get("gate_passed") and c.get("hit")],
                               hit_R=[c.get("R") for c in cs if c.get("hit")])
    return det


def main():
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=False)
    sel = {(s["row"], int(s["world"]), int(s["seed"])): s for s in csv.DictReader(open(wave1.V / "selection.tsv"), delimiter="\t")}
    launch, aws = launch_records(), aws_sha()
    rows, diffs, examples, meta_runs = [], [], [], {}
    for seed in SEEDS:
        s = sel[(ROW, WORLD, seed)]
        rd = wave1.V / ROW / ARM / f"seed{seed:03d}"
        acc = accept(seed, launch, aws)
        # 注意の記録：wave1.py の one_run をそのまま（1a は注意の記録を使う）
        o_att, c_att = wave1.one_run(ROW, WORLD, seed, s["run"], s["version"])
        cap_att, src_att = wave1.capable_from_attention(rd, seed)
        # 再生：one_run の capable の出どころだけを再生の correct_gate_passed に差し替える
        cap_rep, cand_rep = replay_cap(acc["candidates_path"]) if acc["adopted"] else (None, None)
        if cap_rep is not None:
            orig = wave1.capable_from_attention
            wave1.capable_from_attention = lambda _rd, _s: (cap_rep, f"再生 c792（{acc['candidates_path']}）")
            try:
                o_rep, c_rep = wave1.one_run(ROW, WORLD, seed, s["run"], s["version"])
            finally:
                wave1.capable_from_attention = orig
        else:
            o_rep, c_rep = dict(status="NA：再生を採用しない（" + "・".join(k for k, v in acc["checks"].items() if not v) + " が通らない）"), None
            pr = partial_rows(acc["candidates_path"]) if acc["candidates_path"] else []
            acc["partial_candidate_rows_readable"] = len(pr)
            acc["partial_trials"] = [r["trial"] for r in pr]
            acc["partial_capable_differ"] = sum(cap_att[r["trial"]] != bool(r["correct_gate_passed"]) for r in pr)
            acc["partial_capable_attention"] = sum(cap_att[r["trial"]] for r in pr)
            acc["partial_capable_replay"] = sum(bool(r["correct_gate_passed"]) for r in pr)
        for label, o, c in (("attention", o_att, c_att), ("replay", o_rep, c_rep)):
            for scope, day in (("全課題", "全日"), ("ドア課題", "例外")):
                rows.append(dict(row=ROW, world=WORLD, seed=seed, run=s["run"], version=s["version"], measure=label,
                                 status=o["status"], scope=scope, day=day,
                                 tasks=c.get((scope, day, "tasks"), 0) if c else "",
                                 selection_error=c.get((scope, day, "selection_error"), 0) if c else "",
                                 absent=c.get((scope, day, "absent"), 0) if c else "",
                                 wrong=c.get((scope, day, "wrong"), 0) if c else "",
                                 distinction_loss=c.get((scope, day, "distinction_loss"), 0) if c else ""))
        # 試行ごとの違い（台帳の課題の種類ごと）
        per_type = Counter()
        if cap_rep is not None:
            det = attention_detail(rd, seed)
            led = wave1.one(rd, f"ledgers/cells/*/seed{seed:03d}.jsonl.gz")
            for r in wave1.rows_gz(led):
                if r.get("record_type", "trial") != "trial":
                    continue
                t = r["prediction_order"]
                outcome = "correct" if r["hit"] else "silent" if r["predicted_edge"] is None else "wrong"
                ttype = ("ドア" if r.get("held_out_is_door") else "ドアでない") + "・" + wave1.DAY.get(r.get("shop_cue"), "なし")
                per_type[(ttype, "tasks")] += 1
                if cap_att[t] != cap_rep[t]:
                    k = "注意あり・再生なし" if cap_att[t] else "注意なし・再生あり"
                    per_type[(ttype, "capable_differs")] += 1
                    per_type[(ttype, k)] += 1
                    per_type[(ttype, f"capable_differs_{outcome}")] += 1
                    if outcome == "wrong":
                        per_type[(ttype, "selection_error_differs")] += 1
                    per_type[(ttype, "absent_differs")] += 1
                    if sum(1 for e in examples if e["seed"] == seed and e["direction"] == k) < 3:
                        examples.append(dict(seed=seed, trial=t, task_type=ttype, outcome=outcome, direction=k,
                                             capable_attention=cap_att[t], capable_replay=cap_rep[t],
                                             attention=det[t], replay=cand_rep[t]))
            for (ttype, k), v in sorted(per_type.items()):
                diffs.append(dict(seed=seed, task_type=ttype, key=k, count=v))
        meta_runs[f"{ARM}/seed{seed:03d}"] = dict(selection=s, production_dir=str(rd.resolve()), attention_source=src_att,
                                                  attention_file=str(wave1.one(rd, f"attention/*/seed{seed:03d}.jsonl.gz")),
                                                  attention_sha256=sha(wave1.one(rd, f"attention/*/seed{seed:03d}.jsonl.gz")),
                                                  ledger_file=str(wave1.one(rd, f"ledgers/cells/*/seed{seed:03d}.jsonl.gz")),
                                                  status_attention=o_att["status"], status_replay=o_rep["status"],
                                                  acceptance=acc, trials_capable_differ=sum(v for (tt, k), v in per_type.items() if k == "capable_differs"))
    f = ["row", "world", "seed", "run", "version", "measure", "status", "scope", "day", "tasks", "selection_error", "absent",
         "wrong", "distinction_loss"]
    with open(out / "measure_check.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=f)
        w.writeheader()
        w.writerows(rows)
    with open(out / "differences_by_task_type.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["seed", "task_type", "key", "count"])
        w.writeheader()
        w.writerows(diffs)
    (out / "examples.json").write_text(json.dumps(examples, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    meta = dict(made_at=datetime.now().isoformat(timespec="seconds"), instruction="受け箱の指示 80 B",
                definitions="wave1.py の one_run（選び間違い＝誤答で capable、定義の不在＝capable でない）。capable の出どころだけを替えた",
                wave1_py_sha256=sha(H / "surface/wave1.py"), replay_py_sha256=sha(H / "surface/replay.py"),
                replay_config=str(H / "surface/configs_measure_check_1a.json"),
                replay_config_sha256=sha(H / "surface/configs_measure_check_1a.json"),
                replay_commands=str(H / "surface/measure_check_cmds_1a_c792.json"),
                replay_commands_sha256=sha(H / "surface/measure_check_cmds_1a_c792.json"),
                replay_launch=("tmux new-session -d -s replay1a_check \"cd /home/tatsu/surface && SURFACE_TMP=/mnt/d/sfn_runs/surface_tmp_measure_check "
                               "python3.12 -u replay.py --configs /home/tatsu/surface/configs_measure_check_1a.json --maxpar 2 --total 12 2>&1 | "
                               "tee -a /home/tatsu/surface/replay_measure_check/replay.log\""),
                replay_tool="tools/selcands_sme.py", replay_src=str(H / "sfn/audit/_read/jsonlog4cea"),
                replay_src_commit="c79215980a913cc426a63f25048e0dfc6fd1f758",
                replay_finding=("3 本とも、再生の道具 tools/selcands_sme.py（c7921598）の中の確かめ「候補の再解析：試行 N の選ばれた定義の答えが本物と違う」で止まった"
                                "（種 1 は試行 15、種 2 は試行 12、種 3 は試行 22。終了コード 3）。台帳本体の違い 1・side の違いは、途中で止まって長さが足りないことによる。"
                                "このため再生の数え方（correct_gate_passed）は 1740 試行のそろった値が無く、比べは NA。読める候補の行（止まる前の試行）だけは突き合わせた（acceptance の partial_*）。"
                                "見立て（確かめていない）：v3_run.py では cstar_runtime.install（508 行）が smereplay.install（585 行、selcands の predict を被せる）より先、"
                                "注意（attn_sme、592 行）と第二段（601 行）がその後に入るので、selcands が候補ごとに呼ぶ v39.predict は C* の照合の段（phase）と注意の選びの外で走る。"
                                "2a（--match-cstar・--attn-*・--stage2 on が無い）では、この違いが出ない。"),
                aws_sha_lists=list(AWS_LISTS), launch_records=list(LAUNCH), runs=meta_runs,
                outputs=["measure_check.csv", "differences_by_task_type.csv", "examples.json", "meta.json", "measure_check.py"])
    (out / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    for r in rows:
        print(r["seed"], r["measure"], r["scope"], r["day"], r["status"], "tasks", r["tasks"], "選び間違い", r["selection_error"], "不在", r["absent"])


if __name__ == "__main__":
    main()

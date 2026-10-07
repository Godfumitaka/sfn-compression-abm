"""候補の記録が無い完了した本を、その版の tools/selcands_sme.py で保存記憶から再生して、候補の記録を作る（任意。既定では使わない）。

~/sme_analysis/run_replay.py と同じ手順を、configs.json の群ごとの設定で行う：
  - 群に "replay": {"src": 作業場所, "commit": その HEAD, "commands": 命令の JSON の glob, "ignore_flags": [...]} があるときだけ。
    src が commit のきれいな作業場所で、src/tools/selcands_sme.py があること。無ければ再生しない（surface.py は NA のまま）。
  - 命令は commands の JSON（一本ずつの {arm, seed, command} の並び。run_after_audit.py の sme.commands.json と同じ形）から、
    command[3] が本の出力先と一致するものを使う。本番の side に seedNNN.sme.states.jsonl.gz が無い本は再生しない。
  - 再生の出力は ~/surface/tmp/<arm>_seedNNN/ に書き、台帳本体（見出しを除く）・side の answers/jsonl/routing/shop/ambig・旗
    （commit と ignore_flags を除く）が本番と同じで、候補の記録が 0〜(horizon−1) の全試行を順に持つときだけ ok。
    ok なら候補の記録と replay.json だけを <replay_dir>/<arm>/seedNNN/ に残して tmp を消す。
    失敗した本は replay.json に status=failed を残し、自動ではやり直さない（tmp も残す。消すのは人が見てから）。
  - 同時の数：再生は --maxpar（既定 2、4 まで）、本番 tools/v3_run.py との合計は --total（既定 12）まで。
    始める前に MemAvailable ≧ 6GiB、C: の空き ≧ 21GB。nice -n 15 ionice -c3。種 21〜40 は扱わない。
  - 止め方：~/surface/STOP_REPLAY を置くと、新しい再生を始めず、走っている再生が終わったら抜ける。
使い方：
  python3.12 ~/surface/replay.py --dry-run           再生が要る本と、作る命令を出すだけ
  python3.12 ~/surface/replay.py --explain ARM SEED  その本の再生の命令を作って出すだけ（済んだ本でも。確かめ用）
  python3.12 ~/surface/replay.py [--maxpar 2] [--wait]
"""
import argparse
import fcntl
import glob
import gzip
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from surface import BASE, candidate_file, discover, expand, load_json, one  # noqa: E402

TMP = BASE / "tmp"
PY = "python3.12"
SIDE_SAME = ("answers.csv", "jsonl", "routing.jsonl", "shop.jsonl", "ambig.csv")


def ledger_rows(p):
    with gzip.open(p, "rt", encoding="utf-8") as f:
        for line in f:
            yield json.loads(line)


def sha256_file(path, chunk=1 << 20):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            b = f.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def git(src, *a):
    return subprocess.run(["git", "-C", str(src), *a], capture_output=True, text=True).stdout.strip()


def prod_count():
    out = subprocess.run(["ps", "-eo", "args"], capture_output=True, text=True).stdout.splitlines()
    return sum(1 for l in out if len(l.split()) > 1 and l.split()[1] == "tools/v3_run.py")


def replay_count():
    out = subprocess.run(["ps", "-eo", "args"], capture_output=True, text=True).stdout.splitlines()
    return sum(1 for l in out if len(l.split()) > 1 and l.split()[1] == "tools/selcands_sme.py")


def mem_available_gib():
    for line in open("/proc/meminfo"):
        if line.startswith("MemAvailable:"):
            return int(line.split()[1]) / 1024 ** 2
    return 0.0


def c_free_gb():
    st = os.statvfs("/mnt/c")
    return st.f_bavail * st.f_frsize / 1024 ** 3


def group_replay(cfg):
    return {g.get("name", ""): g.get("replay") for g in cfg["groups"] if not g.get("todo")}


def commands_for(rp):
    """commands の glob にある JSON を全部読み、command[3]（出力先）→ 命令 にする。"""
    out = {}
    for p in sorted(glob.glob(str(expand(rp["commands"])))):
        x = load_json(p)
        for r in (x if isinstance(x, list) else x.get("plan", [])):
            out[str(Path(r["command"][3]))] = r["command"]
    return out


def plan_one(run, rp, cmds):
    """一本の再生の準備。(argv の材料, 理由) を返す。準備できなければ (None, 理由)。"""
    if not rp:
        return None, "群に replay の設定が無い"
    src = expand(rp["src"])
    if not (src / "tools/selcands_sme.py").exists():
        return None, f"{src} に tools/selcands_sme.py が無い"
    head = git(src, "rev-parse", "HEAD")
    if head != rp["commit"] or git(src, "status", "--short"):
        return None, f"再生の作業場所 {src} が {rp['commit'][:7]} のきれいな状態でない（HEAD {head[:7]}）"
    states = one((run["run_dir"], f"side/*/seed{run['seed']:03d}.sme.states.jsonl.gz"))
    if states is None:
        return None, "本番の side に sme.states.jsonl.gz が無い"
    cmd = cmds.get(run["run_dir"])
    if cmd is None:
        return None, "命令（command[3] が本の出力先と一致するもの）が見つからない"
    return {"src": src, "states": states, "command": cmd}, "ok"


def argv_for(tmp, states):
    return ["/usr/bin/time", "-v", "-o", str(tmp / "time.txt"), "nice", "-n", "15", "ionice", "-c3",
            PY, "tools/selcands_sme.py", str(tmp / "command.json"), str(tmp / "out"), str(states)]


def start(run, prep):
    name = f"{run['arm']}_seed{run['seed']:03d}"
    tmp = TMP / name
    if tmp.exists():
        shutil.rmtree(tmp)   # 自分の前の途中の写しだけ
    tmp.mkdir(parents=True)
    (tmp / "command.json").write_text(json.dumps(prep["command"], ensure_ascii=False))
    env = dict(os.environ, PYTHONHASHSEED="0", PYTHONDONTWRITEBYTECODE="1")
    for k in ("LC_ALL", "LANG", "LC_CTYPE"):
        env.pop(k, None)
    argv = argv_for(tmp, prep["states"])
    log = open(tmp / "log.txt", "w")
    p = subprocess.Popen(argv, cwd=prep["src"], env=env, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
    return {"run": run, "prep": prep, "proc": p, "tmp": tmp, "argv": argv, "t0": time.monotonic(),
            "started": datetime.now().isoformat(timespec="seconds")}


def parse_time(path):
    r = {}
    if path.exists():
        for line in path.read_text().splitlines():
            line = line.strip()
            if line.startswith("Maximum resident set size"):
                r["peak_rss_mb"] = round(int(line.split(":")[-1]) / 1024, 1)
            elif line.startswith("User time"):
                r["user_seconds"] = float(line.split(":")[-1])
    return r


def check(job, rc, rp):
    run, tmp = job["run"], job["tmp"]
    seed, out, prod = run["seed"], job["tmp"] / "out", Path(run["run_dir"])
    flag = load_json(prod / "flag.json")
    horizon = int(flag.get("horizon", 1740))
    res = {"arm": run["arm"], "seed": seed, "run_dir": run["run_dir"], "run_commit": str(flag.get("commit", ""))[:7],
           "replay_code_commit": rp["commit"][:7], "replay_tool": "tools/selcands_sme.py", "command": job["argv"],
           "started": job["started"], "finished": datetime.now().isoformat(timespec="seconds"),
           "wall_seconds": round(time.monotonic() - job["t0"], 1), "exit": rc, **parse_time(tmp / "time.txt")}
    errs = []
    res["log_tail"] = (tmp / "log.txt").read_text(errors="replace").splitlines()[-40:]
    if rc != 0:
        errs.append(f"終了コード {rc}")
    body_diff, n, first = 0, 0, None
    try:
        ri = ledger_rows(one((out, f"ledgers/cells/*/seed{seed:03d}.jsonl.gz")))
        pi = ledger_rows(one((prod, f"ledgers/cells/*/seed{seed:03d}.jsonl.gz")))
        while True:
            a, b = next(ri, None), next(pi, None)
            if a is None and b is None:
                break
            if a is None or b is None:
                body_diff += 1
                first = first or "長さ"
                break
            if b.get("record_type") == "run_header":
                continue
            n += 1
            if a != b:
                body_diff += 1
                first = first or b.get("prediction_order")
    except Exception as e:  # noqa
        errs.append(f"台帳の比べができない：{e!r}")
    res.update(ledger_body_rows=n, ledger_body_diff_rows=body_diff, ledger_first_diff=first)
    side_diff = {}
    try:
        so, sp = one((out, "side/*/")), one((prod, "side/*/"))
        for suf in SIDE_SAME:
            f = f"seed{seed:03d}.{suf}"
            if (sp / f).exists() or (so / f).exists():
                if not ((sp / f).exists() and (so / f).exists() and sha256_file(sp / f) == sha256_file(so / f)):
                    side_diff[f] = "違う"
    except Exception as e:  # noqa
        errs.append(f"side の比べができない：{e!r}")
    res["side_diff"] = side_diff
    try:
        fo = load_json(out / "flag.json")
        skip = {"commit", *rp.get("ignore_flags", [])}
        res["flag_diff"] = sorted(k for k in set(fo) | set(flag) if k not in skip and fo.get(k) != flag.get(k))
    except Exception as e:  # noqa
        errs.append(f"旗の比べができない：{e!r}")
    cands = None
    try:
        cands = one((out, f"side/*/seed{seed:03d}.sme.candidates.jsonl.gz"))
        trials = [json.loads(l)["trial"] for l in gzip.open(cands, "rt", encoding="utf-8")]
        res["candidate_rows"] = len(trials)
        if trials != list(range(horizon)):
            errs.append(f"候補の記録の試行が 0〜{horizon - 1} の順でない（{len(trials)} 行）")
    except Exception as e:  # noqa
        errs.append(f"候補の記録が読めない：{e!r}")
    if body_diff:
        errs.append(f"台帳本体の違う行 {body_diff}")
    if side_diff:
        errs.append(f"side の違い {side_diff}")
    if res.get("flag_diff"):
        errs.append(f"旗の違い {res['flag_diff']}")
    res["errors"] = errs
    res["status"] = "ok" if not errs else "failed"
    dest = Path(run["replay_dir"]) / run["arm"] / f"seed{seed:03d}"
    dest.mkdir(parents=True, exist_ok=True)
    if res["status"] == "ok":
        shutil.copy2(cands, dest / "sme.candidates.jsonl.gz")
        res["candidates_sha256"] = sha256_file(dest / "sme.candidates.jsonl.gz")
        res["replay_mismatches"] = 0
        shutil.rmtree(tmp)
    else:
        res["replay_mismatches"] = "止まった（log_tail と errors を見る）"
        res["kept_tmp"] = str(tmp)
    (dest / "replay.json").write_text(json.dumps(res, ensure_ascii=False, indent=1) + "\n")
    return res


def pending(cfg, busy):
    reps = group_replay(cfg)
    cmd_cache = {}
    runs, _ = discover(cfg)
    for run in runs:
        if (run["run_dir"]) in busy:
            continue
        cf, why, rj = candidate_file(run)
        if cf is not None or rj is not None:      # 候補がある、又は前に試した（失敗は自動でやり直さない）
            continue
        rp = reps.get(run["group"])
        if rp:
            key = rp["commands"]
            if key not in cmd_cache:
                cmd_cache[key] = commands_for(rp)
        prep, reason = plan_one(run, rp, cmd_cache.get(rp["commands"]) if rp else {})
        yield run, rp, prep, reason


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--configs", default=str(BASE / "configs.json"))
    ap.add_argument("--maxpar", type=int, default=2)
    ap.add_argument("--total", type=int, default=12)
    ap.add_argument("--wait", action="store_true", help="待つ本が無くなっても抜けず、新しく完了した本を待つ")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--explain", nargs=2, metavar=("ARM", "SEED"))
    a = ap.parse_args()
    maxpar = max(1, min(4, a.maxpar))
    cfg = load_json(a.configs)
    if a.explain:
        arm, seed = a.explain[0], int(a.explain[1])
        runs, _ = discover(cfg)
        run = [r for r in runs if r["arm"] == arm and r["seed"] == seed]
        if len(run) != 1:
            sys.exit(f"{arm} 種{seed} が完了した本の中に一つに決まらない")
        run = run[0]
        rp = group_replay(cfg).get(run["group"])
        prep, reason = plan_one(run, rp, commands_for(rp) if rp else {})
        print(json.dumps({"run": run["run_dir"], "reason": reason,
                          "cwd": str(prep["src"]) if prep else None,
                          "argv": argv_for(TMP / f"{arm}_seed{seed:03d}", prep["states"]) if prep else None,
                          "command.json": prep["command"] if prep else None}, ensure_ascii=False, indent=1))
        return
    if a.dry_run:
        n = 0
        for run, rp, prep, reason in pending(cfg, set()):
            n += 1
            print(f"{run['config']} 世界{run['world']} 種{run['seed']}（{run['run_dir']}）：{'再生できる' if prep else '再生しない'}：{reason}")
        print(f"候補の記録が無い本 {n}")
        return
    BASE.mkdir(exist_ok=True)
    lock = open(BASE / "replay.lock", "w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        sys.exit("replay.py はもう動いている")
    if replay_count():
        sys.exit("ほかの tools/selcands_sme.py が動いている。先に確かめる")
    running, told = [], set()
    while True:
        for j in list(running):
            rc = j["proc"].poll()
            if rc is not None:
                running.remove(j)
                r = check(j, rc, j["rp"])
                print(f"{datetime.now():%F %T} 終わり {j['run']['arm']} 種{j['run']['seed']}：{r['status']} "
                      f"{r['wall_seconds']}秒 最大常駐 {r.get('peak_rss_mb')}MB {r['errors']}", flush=True)
        todo = []
        if not (BASE / "STOP_REPLAY").exists():
            for run, rp, prep, reason in pending(cfg, {j["run"]["run_dir"] for j in running}):
                if prep:
                    todo.append((run, rp, prep))
                elif run["run_dir"] not in told:
                    told.add(run["run_dir"])
                    print(f"{datetime.now():%F %T} 再生しない {run['arm']} 種{run['seed']}：{reason}（候補の欄は NA）", flush=True)
        if todo and len(running) < maxpar and prod_count() + replay_count() + 1 <= a.total \
                and mem_available_gib() >= 6 and c_free_gb() >= 21:
            run, rp, prep = todo[0]
            j = start(run, prep)
            j["rp"] = rp
            running.append(j)
            print(f"{datetime.now():%F %T} 始め {run['arm']} 種{run['seed']}（本番 {prod_count()}、再生 {len(running)}、"
                  f"空き {mem_available_gib():.1f}GiB、C: {c_free_gb():.0f}GB）", flush=True)
            time.sleep(5)
            continue
        if not running and not todo and (not a.wait or (BASE / "STOP_REPLAY").exists()):
            break
        time.sleep(60)
        cfg = load_json(a.configs)
    print(f"{datetime.now():%F %T} 再生の待ちは無い", flush=True)


if __name__ == "__main__":
    main()

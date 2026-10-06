"""1・2 の材料：完了した (a) の本ごとに、tools/selcands_sme.py で保存記憶の再生と候補の後づけの調べをする。

- 本番の出力は読むだけ。再生の出力は ~/sme_analysis/tmp/<条件>_seedNNN/ に書き、終わったら確かめてから
  候補の記録（sme.candidates.jsonl.gz）と確かめの記録だけを ~/sme_analysis/replay/<条件>/seedNNN/ に残し、tmp は消す。
- 再生は作業場所 ~/sfn/audit/_read/smeevict（10cd8bd）から、本番の命令（plan/sme.commands.evict.json）の出力先だけを
  置き換えて動かす（selcands_sme.py の決まりどおり --sme-replay <本番の sme.states.jsonl.gz> が足される）。
  再生は試行ごとに、予測前の記憶・提示・設定・乱数、対応・答え・保留状態、学習・忘却後の記憶を保存記録と比べ、違えば止まる。
- 同時の数：本番（tools/v3_run.py で ~/smeprod_a/sme/ のもの）＋この再生 ≦ 12、かつ再生は MAXPAR 本まで。
  始める前に MemAvailable ≧ 6GiB、C: の空き ≧ 21GB を確かめる。nice -n 15 ionice -c3。
- 一度失敗した本は自動ではやり直さない（replay/<条件>/seedNNN/replay.json に status=failed と誤りを残す）。

使い方：python3.12 run_replay.py [--maxpar 4] [--wait]   （--wait：まだ走っている本番の本の完了も待って続ける）
止め方：~/sme_analysis/STOP を置くと新しい再生を始めず、走っている再生が終わったら抜ける（--wait でも）。
"""
import argparse
import fcntl
import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

from common import (A_ROOT, PLAN_EVICT, PLAN_ORIG, REPLAY_COMMIT, REPLAY_DIR, REPLAY_SRC, TMP, WORK,
                    complete_runs, diff_paths, is_complete, ledger_path, ledger_rows, run_commit, run_dir,
                    sha256_file, side_dir, ARMS, SEEDS)

PY = "python3.12"
SIDE_SAME = ("answers.csv", "jsonl", "routing.jsonl", "shop.jsonl", "ambig.csv")


def prod_count():
    out = subprocess.run(["ps", "-eo", "args"], capture_output=True, text=True).stdout.splitlines()
    return sum(1 for l in out if len(l.split()) > 1 and l.split()[1] == "tools/v3_run.py" and "/home/tatsu/smeprod_a/sme/" in l)


def mem_available_gib():
    for line in open("/proc/meminfo"):
        if line.startswith("MemAvailable:"):
            return int(line.split()[1]) / 1024 ** 2
    return 0.0


def c_free_gb():
    st = os.statvfs("/mnt/c")
    return st.f_bavail * st.f_frsize / 1024 ** 3


def command_for(arm, seed):
    plan = json.loads(PLAN_EVICT.read_text())
    rows = [r for r in plan if r["arm"] == arm and r["seed"] == seed]
    assert len(rows) == 1, (arm, seed)
    cmd = list(rows[0]["command"])
    orig = [r for r in json.loads(PLAN_ORIG.read_text()) if r["arm"] == arm and r["seed"] == seed][0]["command"]
    # 元の命令との差が二つの旗だけであることを確かめる
    assert [x for x in cmd if x not in ("--sme-intern-cache", "--sme-evict-trial-cache")] == orig, (arm, seed)
    assert cmd[3] == str(run_dir(arm, seed)), (cmd[3], run_dir(arm, seed))
    return cmd


def start(arm, seed):
    name = f"{arm}_seed{seed:03d}"
    tmp = TMP / name
    if tmp.exists():
        shutil.rmtree(tmp)   # 自分の前の途中の写しだけ
    tmp.mkdir(parents=True)
    cmd = command_for(arm, seed)
    (tmp / "command.json").write_text(json.dumps(cmd, ensure_ascii=False))
    states = side_dir(run_dir(arm, seed)) / f"seed{seed:03d}.sme.states.jsonl.gz"
    env = dict(os.environ, PYTHONHASHSEED="0", PYTHONDONTWRITEBYTECODE="1")
    for k in ("LC_ALL", "LANG", "LC_CTYPE"):
        env.pop(k, None)
    argv = ["/usr/bin/time", "-v", "-o", str(tmp / "time.txt"), "nice", "-n", "15", "ionice", "-c3",
            PY, "tools/selcands_sme.py", str(tmp / "command.json"), str(tmp / "out"), str(states)]
    log = open(tmp / "log.txt", "w")
    p = subprocess.Popen(argv, cwd=REPLAY_SRC, env=env, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
    return {"arm": arm, "seed": seed, "proc": p, "tmp": tmp, "argv": argv, "t0": time.monotonic(),
            "started": datetime.now().isoformat(timespec="seconds"), "states": str(states)}


def parse_time(path):
    r = {}
    if path.exists():
        for line in path.read_text().splitlines():
            line = line.strip()
            if line.startswith("Maximum resident set size"):
                r["peak_rss_mb"] = round(int(line.split(":")[-1]) / 1024, 1)
            elif line.startswith("User time"):
                r["user_seconds"] = float(line.split(":")[-1])
            elif line.startswith("System time"):
                r["system_seconds"] = float(line.split(":")[-1])
    return r


def check(job, rc):
    arm, seed, tmp = job["arm"], job["seed"], job["tmp"]
    out = tmp / "out"
    prod = run_dir(arm, seed)
    res = {"arm": arm, "seed": seed, "run_commit": run_commit(arm, seed)[:7], "replay_code_commit": REPLAY_COMMIT[:7],
           "replay_tool": "tools/selcands_sme.py", "command": job["argv"], "states": job["states"],
           "started": job["started"], "finished": datetime.now().isoformat(timespec="seconds"),
           "wall_seconds": round(time.monotonic() - job["t0"], 1), "exit": rc, **parse_time(tmp / "time.txt")}
    errs = []
    log_tail = (tmp / "log.txt").read_text(errors="replace").splitlines()[-40:]
    res["log_tail"] = log_tail
    manifest = []
    if (out / "manifest.jsonl").exists():
        manifest = [json.loads(x) for x in (out / "manifest.jsonl").read_text().splitlines() if x.strip()]
    res["manifest_error"] = manifest[0].get("error") if manifest else "manifest なし"
    if manifest:
        res["manifest_elapsed_sec"] = manifest[0].get("elapsed_sec")
        res["manifest_peak_rss_mb"] = manifest[0].get("peak_rss_mb")
    sr = manifest[0].get("smereplay") if manifest else None
    res["smereplay"] = sr
    if rc != 0 or res["manifest_error"]:
        errs.append(f"終了コード{rc}、manifest の誤り {res['manifest_error']}")
    if not (sr and sr.get("replayed") and sr.get("predictions") == 1740 and sr.get("updates") == 1740):
        errs.append(f"再生の数が 1740 でない：{sr}")
    # 台帳本体（見出しを除く）を本番と比べる
    body_diff, first = 0, None
    n = 0
    try:
        ri, pi = ledger_rows(ledger_path(out, seed)), ledger_rows(ledger_path(prod, seed))
        while True:
            a, b = next(ri, None), next(pi, None)
            if a is None and b is None:
                break
            if a is None or b is None:
                body_diff += 1
                first = first or ("長さ", [])
                break
            if b.get("record_type") == "run_header":
                res["header_diff_fields"] = diff_paths(a, b)
                continue
            n += 1
            if a != b:
                body_diff += 1
                if first is None:
                    first = (b.get("prediction_order"), diff_paths(a, b))
    except Exception as e:  # noqa
        errs.append(f"台帳の比べができない：{e!r}")
    res["ledger_body_rows"] = n
    res["ledger_body_diff_rows"] = body_diff
    res["ledger_first_diff"] = first
    # side の記録（本番と同じはずのもの）
    side_diff = {}
    try:
        so, sp = side_dir(out), side_dir(prod)
        for suf in SIDE_SAME:
            f = f"seed{seed:03d}.{suf}"
            if (sp / f).exists() or (so / f).exists():
                same = (sp / f).exists() and (so / f).exists() and sha256_file(sp / f) == sha256_file(so / f)
                if not same:
                    side_diff[f] = "違う"
    except Exception as e:  # noqa
        errs.append(f"side の比べができない：{e!r}")
    res["side_files_compared"] = list(SIDE_SAME)
    res["side_diff"] = side_diff
    # 旗（版の番号と二つの旗以外）を本番と比べる
    try:
        fo, fp = json.loads((out / "flag.json").read_text()), json.loads((prod / "flag.json").read_text())
        skip = {"commit", "sme_intern_cache", "sme_evict_trial_cache"}
        res["flag_diff"] = sorted(k for k in set(fo) | set(fp) if k not in skip and fo.get(k) != fp.get(k))
    except Exception as e:  # noqa
        errs.append(f"旗の比べができない：{e!r}")
    # 候補の記録
    cands = None
    try:
        cands = side_dir(out) / f"seed{seed:03d}.sme.candidates.jsonl.gz"
        import gzip
        trials = [json.loads(l)["trial"] for l in gzip.open(cands, "rt", encoding="utf-8")]
        res["candidate_rows"] = len(trials)
        if trials != list(range(1740)):
            errs.append(f"候補の記録の試行が 0〜1739 の順でない（{len(trials)} 行）")
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
    dest = REPLAY_DIR / arm / f"seed{seed:03d}"
    dest.mkdir(parents=True, exist_ok=True)
    if res["status"] == "ok":
        shutil.copy2(cands, dest / "sme.candidates.jsonl.gz")
        res["candidates_sha256"] = sha256_file(dest / "sme.candidates.jsonl.gz")
        res["replay_mismatches"] = 0
        shutil.rmtree(tmp)
    else:
        # 誤りの証拠は小さいものだけ残す（大きな再生の出力は消す）
        for f in ("log.txt", "time.txt", "command.json"):
            if (tmp / f).exists():
                shutil.copy2(tmp / f, dest / f)
        res["replay_mismatches"] = "止まった（log_tail と errors を見る）"
        # 確かめのために出力は残す（消すのは人が見てから）
        res["kept_tmp"] = str(tmp)
    (dest / "replay.json").write_text(json.dumps(res, ensure_ascii=False, indent=1) + "\n")
    return res


def pending(running):
    busy = {(j["arm"], j["seed"]) for j in running}
    for arm, seed in complete_runs():
        if (arm, seed) in busy:
            continue
        if (REPLAY_DIR / arm / f"seed{seed:03d}" / "replay.json").exists():
            continue
        yield arm, seed


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--maxpar", type=int, default=4)
    ap.add_argument("--total", type=int, default=12)
    ap.add_argument("--wait", action="store_true")
    a = ap.parse_args()
    WORK.mkdir(exist_ok=True)
    lock = open(WORK / "run_replay.lock", "w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        sys.exit("run_replay.py はもう動いている")
    head = subprocess.run(["git", "-C", str(REPLAY_SRC), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    dirty = subprocess.run(["git", "-C", str(REPLAY_SRC), "status", "--short"], capture_output=True, text=True).stdout.strip()
    if head != REPLAY_COMMIT or dirty:
        sys.exit(f"再生の作業場所が元のままでない：{head} {dirty!r}")
    others = [l for l in subprocess.run(["ps", "-eo", "args"], capture_output=True, text=True).stdout.splitlines()
              if len(l.split()) > 1 and l.split()[1] == "tools/selcands_sme.py"]
    if others:
        sys.exit("前の再生がまだ動いている（親の台本を止めた後の残り？）。先に確かめる：\n" + "\n".join(others))
    running = []
    while True:
        for j in list(running):
            rc = j["proc"].poll()
            if rc is not None:
                running.remove(j)
                r = check(j, rc)
                print(f"{datetime.now():%H:%M:%S} 終わり {j['arm']} 種{j['seed']}：{r['status']} {r['wall_seconds']}秒 "
                      f"最大常駐{r.get('peak_rss_mb')}MB {r['errors']}", flush=True)
        todo = [] if (WORK / "STOP").exists() else list(pending(running))
        if todo and len(running) < a.maxpar and prod_count() + len(running) + 1 <= a.total \
                and mem_available_gib() >= 6 and c_free_gb() >= 21:
            arm, seed = todo[0]
            running.append(start(arm, seed))
            print(f"{datetime.now():%H:%M:%S} 始め {arm} 種{seed}（本番 {prod_count()}、再生 {len(running)}、"
                  f"空き {mem_available_gib():.1f}GiB、C: {c_free_gb():.0f}GB）", flush=True)
            time.sleep(5)
            continue
        if not running and not todo:
            if not a.wait or (WORK / "STOP").exists():
                break
            left = [(arm, s) for arm in ARMS for s in SEEDS if not is_complete(arm, s)]
            if not left:
                break
        time.sleep(30)
    print(f"{datetime.now():%H:%M:%S} 再生の待ちは無い", flush=True)


if __name__ == "__main__":
    main()

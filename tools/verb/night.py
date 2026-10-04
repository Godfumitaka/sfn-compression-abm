"""承認された30本だけを順に受付へ出し、開始・完了・停止を二つの承認枝へ記録する。

模型は既存 v3_run を別プロセスで実行する。解析もその一本の受付の内側。
再開は完了済みを飛ばす。途中の出力を消したり同じ本を上書きしたりしない。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[2]
ROOT = SOURCE.parent
BASE = ROOT / "stage3_night"
REPORT_REPO = ROOT / "report-results"
REPORT_PATH = "control/2026-10-04_動詞の世界_Codex.md"
EVIDENCE_PATH = "control/2026-10-04_動詞の世界_Codex_段3試走"
WORK_BRANCH = "codex/verb-world-2026-10-04"
REPORT_BRANCH = "results-2026-09-27"
DESTINATION = "https://github.com/Godfumitaka/sfn-compression-abm.git"
JOBS = Path.home() / "jobs/jobs.py"
STOP = False


def now():
    return datetime.now().astimezone().isoformat(timespec="seconds")


def write_json(path, value):
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    tmp.replace(path)


def git(repo, *args):
    return subprocess.check_output(["git", "-c", "core.commitGraph=false", *args], cwd=repo, text=True).strip()


def checked_git(repo, *args):
    subprocess.run(["git", "-c", "core.commitGraph=false", "-c", "user.name=Codex", "-c", "user.email=codex@users.noreply.github.com", *args], cwd=repo, check=True)


def scan_range(repo, branch, base):
    """今回送るオブジェクトだけ検査。一致した秘密の値は表示しない。"""
    log = git(repo, "log", "--reverse", "--format=%H %s", f"{base}..{branch}")
    stat = git(repo, "diff", "--stat", base, branch)
    print(log or "送るコミットなし", flush=True)
    print(stat or "変更ファイルなし", flush=True)
    objects = git(repo, "rev-list", "--objects", branch, "^" + base).splitlines()
    secrets = [rb"-----BEGIN (?:RSA |EC |DSA |OPENSSH |ENCRYPTED )?PRIVATE KEY-----",
               rb"(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,})", rb"(?:AKIA|ASIA)[A-Z0-9]{16}",
               rb"\bsk-(?:proj-|svcacct-)?[A-Za-z0-9_-]{20,}", rb"\bxox[baprs]-[A-Za-z0-9-]{15,}",
               rb"\bAIza[A-Za-z0-9_-]{30,}", rb"https?://[^/\s:@]{1,80}:[^/\s@]{1,80}@",
               rb"(?im)^\s*[\"']?(?:password|passwd|secret|api_key|access_token|auth_token|client_secret)[\"']?\s*[:=]\s*[\"'][^\"'\n]{8,}[\"']"]
    private = [rb"/(?:Users|home)/[^/\s\"'<>]+/", rb"\b[A-Za-z0-9_-]+\.local\b"]
    blobs, maximum = 0, 0
    for item in objects:
        parts = item.split(" ", 1)
        oid = parts[0]
        kind = git(repo, "cat-file", "-t", oid)
        if kind not in ("blob", "commit"):
            continue
        size = int(git(repo, "cat-file", "-s", oid))
        if size > 100_000_000:
            raise RuntimeError("送信範囲に100MB超のオブジェクトがある")
        data = subprocess.check_output(["git", "cat-file", kind, oid], cwd=repo)
        if repo == REPORT_REPO and kind == "blob" and len(parts) == 2 and parts[1] == REPORT_PATH:
            # 持ち主が既に承認した旧報告のローカルパスだけを例外にする。
            approved = subprocess.check_output(["git", "show", f"4886b875e5c033072757e37a37ebd31d946af83a:{REPORT_PATH}"], cwd=repo)
            if not data.startswith(approved):
                raise RuntimeError("承認済みの旧報告本文が変わった")
            data = data[len(approved):]
        if any(re.search(p, data) for p in secrets):
            raise RuntimeError("送信範囲に秘密のパターン一致がある")
        if any(re.search(p, data) for p in private):
            raise RuntimeError("送信範囲に未承認の個人情報のパターン一致がある")
        emails = re.findall(rb"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b", data)
        if any(e != b"codex@users.noreply.github.com" for e in emails):
            raise RuntimeError("送信範囲に未承認のメールアドレスがある")
        if kind == "blob":
            blobs += 1
            maximum = max(maximum, size)
    audit = {"time": now(), "branch": branch, "base": git(repo, "rev-parse", base), "head": git(repo, "rev-parse", branch),
             "log": log, "diff_stat": stat, "blobs": blobs, "largest_blob_bytes": maximum, "secret_findings": 0, "private_findings": 0}
    with (BASE / "publish_audit.jsonl").open("a") as f:
        f.write(json.dumps(audit, ensure_ascii=False) + "\n")


def fetch_report():
    if git(REPORT_REPO, "remote", "get-url", "origin") != DESTINATION or git(REPORT_REPO, "remote", "get-url", "--push", "origin") != DESTINATION:
        raise RuntimeError("承認されたGitHub宛先と違う")
    if git(REPORT_REPO, "branch", "--show-current") != REPORT_BRANCH:
        raise RuntimeError("報告の枝が違う")
    checked_git(REPORT_REPO, "fetch", "--no-tags", "origin", f"refs/heads/{REPORT_BRANCH}:refs/remotes/origin/{REPORT_BRANCH}")
    ahead = int(git(REPORT_REPO, "rev-list", "--count", f"{REPORT_BRANCH}..origin/{REPORT_BRANCH}"))
    if ahead:
        checked_git(REPORT_REPO, "merge", "--no-edit", "--no-stat", "-m", "動詞の試走報告を報告枝の最新へ重ねる", f"origin/{REPORT_BRANCH}")


def publish(message, evidence=False):
    fetch_report()
    report = REPORT_REPO / REPORT_PATH
    report.write_text(report.read_text() + f"\n{now()} {message}\n")
    if evidence:
        target = REPORT_REPO / EVIDENCE_PATH
        target.mkdir(exist_ok=True)
        for p in sorted((BASE / "aggregate").iterdir()):
            if p.is_file():
                shutil.copy2(p, target / p.name)
    checked_git(REPORT_REPO, "add", "--", REPORT_PATH, EVIDENCE_PATH)
    checked_git(REPORT_REPO, "commit", "-m", "動詞の段3試走の進行と集計を追記")
    # ほかの担当の更新が挟まれば最新をmergeして再試行。rebase/forceは使わない。
    for attempt in range(3):
        fetch_report()
        scan_range(REPORT_REPO, REPORT_BRANCH, f"origin/{REPORT_BRANCH}")
        push = subprocess.run(["git", "-c", "core.commitGraph=false", "push", "--no-follow-tags", "origin",
                               f"refs/heads/{REPORT_BRANCH}:refs/heads/{REPORT_BRANCH}"], cwd=REPORT_REPO)
        if push.returncode == 0:
            sha = git(REPORT_REPO, "rev-parse", REPORT_BRANCH)
            write_json(BASE / "last_push.json", {"time": now(), "branch": REPORT_BRANCH, "commit": sha})
            return sha
        if attempt < 2:
            time.sleep(2)
    raise RuntimeError("報告のpushが3回通らない")


def prepare():
    BASE.mkdir(exist_ok=True)
    if (BASE / "plan.json").exists():
        raise SystemExit("事前計画が既にある。二重作成しない")
    if git(SOURCE, "branch", "--show-current") != WORK_BRANCH or git(SOURCE, "status", "--porcelain"):
        raise SystemExit("作業枝が違うか未コミットの変更がある")
    template = json.loads((ROOT / "stage2/pilot_s1_5000/command.json").read_text())["command"]
    sizes = [sum(p.stat().st_size for p in (ROOT / "stage2" / f"pilot_s{s}_5000").rglob("*") if p.is_file()) for s in (1, 2, 3)]
    estimate = sum(sizes) / 3 * 30
    plan = {"prepared": now(), "commit": git(SOURCE, "rev-parse", "HEAD"), "bin_width": 500,
            "stage2_sizes_bytes": sizes, "estimated_output_bytes": round(estimate), "margin_1_2_bytes": round(estimate * 1.2), "runs": []}
    for seed in range(1, 6):
        for arm in ("A", "C", "D"):
            for u in ("global", "abstain"):
                label = f"{arm}_{u}_s{seed:02d}"
                cmd = list(template)
                cmd[0] = sys.executable
                cmd[3] = str(BASE / label / "run")
                cmd[cmd.index("--seeds") + 1] = str(seed)
                cmd[cmd.index("--v39-u") + 1] = u
                if arm == "C":
                    cmd += ["--cf-learn"]
                if arm == "D":
                    cmd += ["--use-forget", "0.4"]
                plan["runs"].append({"label": label, "seed": seed, "arm": arm, "U": u, "command": cmd})
    write_json(BASE / "plan.json", plan)
    evidence = REPORT_REPO / EVIDENCE_PATH
    evidence.mkdir(exist_ok=True)
    public_plan = {**plan, "runs": [{**r, "command": ["python3.12", *r["command"][1:3], "<出力>/" + r["label"] + "/run", *r["command"][4:]]} for r in plan["runs"]]}
    write_json(evidence / "plan.json", public_plan)
    prerecord = (f"\n## アストラ承認後の段3試走（結果を見る前の固定記録）\n\n"
                 f"コード `{plan['commit']}`。既定40動詞・N3・λ=0.01873710622997919・5,000試行（horizonも5,000）。保持A/C/D（Dのτ=0.4）×U global/abstain×種1〜5の30本。種の順にA global、A abstain、C global、C abstain、D global、D abstainを一本ずつ出す。種21〜40は読まない・走らせない。Schuler変種は走らせない。\n\n"
                 f"**Uの事前記録**：今の `--v39-u global` を使う。固定M1では過去形のUの席の候補に骨組みの二引数述語も入り、最多が同点になって答えが出ない（実質は黙る）。これは段1の診断と今回の指示に基づく事前記録であり、今回の回答率の観測とは分ける。`--v39-u abstain` を比べる。候補を過去形だけに絞る変更はしない。\n\n"
                 f"**開始前の容量見込み**：段2のA/global・種1〜3の全出力は順に {sizes[0]:,}、{sizes[1]:,}、{sizes[2]:,} bytes。30本への単純外挿は {estimate/1024**3:.6f} GiB、1.2倍は {estimate*1.2/1024**3:.6f} GiB。C/Dの増分と解析ファイルは未実測。空きの下限20GiBを受付が毎回判定し、足りなければ待つ。\n\n"
                 "受付は各本 `python3 ~/jobs/jobs.py run --wait --owner Codex-動詞段3-<本> --mem 0.4 --disk-path <出力> -- python3.12 tools/verb/night.py one <本>`。一度に一本。解析は同じ受付の内側で、模型とは別プロセス。\n\n"
                 "**集計の固定定義**：500試行の区間（0–500、…、4500–5000、右端を含まない）。不規則語別のMarcus率=REG/(正しいIRR_k+REG)。黙りと他の答えを別に数え、REG/全過去形質問も出す。8語の均等平均と、その区間の実際の語の出現数による頻度加重平均を併記する。分母0の語は率を欠測とし、8語全体の平均も欠測、観測語だけの平均と重みの被覆率は別記する。\n\n"
                 "同一語の崩れと回復は、当該語の過去形質問の正答/REGの部分列で正答→REG→正答の完了を数える。黙り・他の答えは飛ばし、直前の正答・最初のREG・回復の三時点を残す。連続REGは一回の崩れ。新語V41〜V48は100試行ごとの既存の非学習試験からREG・各IRR名・黙り・その他を集計する。\n\n"
                 "過剰規則化時の予測直前状態から、選ばれた定義の当該語の名前の席のF/H/Uを記録する。対応する名前の席・定義が無ければ『定義が無い』に数え、他に当該語の名前をF/Hで持つ定義も生記録に残す。分類は既存selcandsと同じ：F/Hを持つ候補の中に、その定義なら門を通って正しい述語と引数を答えるものがあれば選び間違い、無ければ区別の喪失。候補の並びは走行どおりN3→F/H席数→新しさ→名前。台帳の状態指紋・世界・再予測・選ばれた候補の答えの一致が崩れれば集計を確定せず停止する。回答/黙り・記憶bits・定義数・F/H/U・一本の時間/RSSも残す。\n\n"
                 "**独立した比べの学び手は設計のみ**：語→例外形の辞書を空で始める。答える時点で登録済みならその形、無ければREG。今回の入力中に見えた正しい不規則形、又は質問の後に実際に開示された正しい形を、回答確定後に登録する。模型と同じ動詞出現・過去形質問・開示の並びと試験時点を用い、試験では更新しない。辞書を忘れない。(1)〜(3)は同じ集計定義で後日出す。今夜はこの学び手を実装・実行しない。\n\n"
                 f"命令30本は [事前計画](./{Path(EVIDENCE_PATH).name}/plan.json)。\n")
    sha = publish(prerecord)
    write_json(BASE / "preregistered.json", {"time": now(), "report_commit": sha})
    print(json.dumps({"preregistered": sha, "planned_runs": 30, "estimate_gib": estimate/1024**3}, ensure_ascii=False))


def read_plan():
    plan = json.loads((BASE / "plan.json").read_text())
    if len(plan["runs"]) != 30 or {(r["arm"], r["U"], r["seed"]) for r in plan["runs"]} != {(a, u, s) for s in range(1, 6) for a in ("A", "C", "D") for u in ("global", "abstain")}:
        raise RuntimeError("承認された30本と計画が違う")
    if git(SOURCE, "rev-parse", "HEAD") != plan["commit"] or git(SOURCE, "status", "--porcelain"):
        raise RuntimeError("事前に固定したコードが変わっている")
    return plan


def one(label):
    plan = read_plan()
    runs = [r for r in plan["runs"] if r["label"] == label]
    if len(runs) != 1:
        raise SystemExit("計画に無い本")
    run = runs[0]
    output = BASE / label
    output.mkdir(exist_ok=False)
    write_json(output / "admitted.json", {"time": now(), "label": label, "pid": os.getpid()})
    write_json(output / "command.json", {"commit": plan["commit"], "command": run["command"]})
    started = time.monotonic()
    peak = 0.0
    with (output / "run.log").open("w") as log:
        proc = subprocess.Popen(["/usr/bin/time", "-l", "-o", str(output / "time.txt"), *run["command"]], cwd=SOURCE, stdout=log, stderr=subprocess.STDOUT)
        while proc.poll() is None:
            table = {}
            for line in subprocess.check_output(["/bin/ps", "-axo", "pid=,ppid=,rss="], text=True).splitlines():
                pid, ppid, rss = map(int, line.split())
                table[pid] = (ppid, rss)
            descendants = {proc.pid}
            while True:
                more = {pid for pid, (ppid, _) in table.items() if ppid in descendants}
                if more <= descendants:
                    break
                descendants |= more
            peak = max(peak, sum(table.get(pid, (0, 0))[1] for pid in descendants) / 1024)
            time.sleep(1)
    model_seconds = time.monotonic() - started
    timed = (output / "time.txt").read_text()
    maximum = re.search(r"(\d+)\s+maximum resident set size", timed)
    res = {"label": label, "commit": plan["commit"], "returncode": proc.returncode, "model_seconds": round(model_seconds, 3),
           "process_peak_rss_bytes_time": int(maximum.group(1)) if maximum else None, "max_aggregate_rss_mib_sampled_1s": round(peak, 3)}
    write_json(output / "resources.json", res)
    if proc.returncode:
        return proc.returncode
    analysis_start = time.monotonic()
    with (output / "analysis.log").open("w") as log:
        analyzed = subprocess.run([sys.executable, "tools/verb/analyze.py", str(output / "run"), str(run["seed"]), str(output / "analysis")], cwd=SOURCE, stdout=log, stderr=subprocess.STDOUT)
    res.update(analysis_seconds=round(time.monotonic()-analysis_start, 3), supervised_wall_seconds=round(time.monotonic()-started, 3), analysis_returncode=analyzed.returncode)
    res["output_bytes"] = sum(p.stat().st_size for p in output.rglob("*") if p.is_file())
    write_json(output / "resources.json", res)
    if analyzed.returncode:
        return analyzed.returncode
    write_json(output / "complete.json", {"time": now(), "label": label})
    return 0


def stop_handler(_signum, _frame):
    global STOP
    STOP = True


def run_all():
    import fcntl
    from aggregate import aggregate
    plan = read_plan()
    if not (BASE / "preregistered.json").exists():
        raise RuntimeError("結果を見る前の記録がpushされていない")
    lock = (BASE / "pipeline.lock").open("w")
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    signal.signal(signal.SIGTERM, stop_handler)
    signal.signal(signal.SIGINT, stop_handler)
    current = None
    try:
        publish("段3の30本の逐次受付を開始。各本は --wait・--mem 0.4。解析済みの完走本だけ集計に入れる。")
        for index, run in enumerate(plan["runs"], 1):
            label = run["label"]
            output = BASE / label
            if (output / "complete.json").exists():
                continue
            if STOP:
                raise InterruptedError("停止指示")
            if output.exists():
                raise RuntimeError("途中の出力があるため上書きせず停止")
            cmd = [sys.executable, str(JOBS), "run", "--wait", "--owner", f"Codex-動詞段3-{label}", "--mem", "0.4", "--disk-path", str(output),
                   "--", sys.executable, str(Path(__file__).resolve()), "one", label]
            write_json(BASE / "status.json", {"time": now(), "state": "queued", "index": index, "label": label, "complete": index-1})
            admitted, waiting_reported = False, False
            with (BASE / f"{label}.jobs.log").open("w") as log:
                current = subprocess.Popen(cmd, cwd=SOURCE, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
                write_json(BASE / "active.json", {"time": now(), "controller_pid": os.getpid(), "jobs_pid": current.pid, "label": label})
                queued_at = time.monotonic()
                while current.poll() is None:
                    if STOP:
                        os.killpg(current.pid, signal.SIGTERM)
                        current.wait(timeout=30)
                        subprocess.run([sys.executable, str(JOBS), "release", "--pid", str(current.pid)], check=True)
                        raise InterruptedError("停止指示")
                    if not admitted and (output / "admitted.json").exists():
                        admitted = True
                        write_json(BASE / "status.json", {"time": now(), "state": "running", "index": index, "label": label, "complete": index-1})
                        publish(f"走行開始 {index}/30：`{label}`。受付済み。")
                    if not admitted and not waiting_reported and time.monotonic() - queued_at >= 30:
                        waiting_reported = True
                        free = shutil.disk_usage(BASE).free / 1024**3
                        publish(f"受付待ち {index}/30：`{label}`。出力先の空き {free:.3f} GiB。--wait は待機を続け、受付が通れば自動で開始する。")
                    time.sleep(2)
            rc = current.returncode
            current = None
            if rc != 0 or not (output / "complete.json").exists():
                raise RuntimeError(f"{label} の走行または照合が終了コード{rc}で停止")
            r = json.loads((output / "resources.json").read_text())
            aggregate(BASE, plan)
            peak_mb = (r["process_peak_rss_bytes_time"] or 0) / 1e6
            publish(f"走行・集計完了 {index}/30：`{label}`。模型 {r['model_seconds']:.3f}秒、解析 {r['analysis_seconds']:.3f}秒、模型の最大常駐 {peak_mb:.1f} MB、1秒間隔の子孫合計最大 {r['max_aggregate_rss_mib_sampled_1s']:.3f} MiB。区間別の暫定集計を更新。", evidence=True)
        aggregate(BASE, plan)
        tables = (BASE / "aggregate/tables.md").read_text()
        sha = publish("30/30本の走行・照合・集計が完了。比べの学び手は設計のみ。\n\n" + tables, evidence=True)
        write_json(BASE / "status.json", {"time": now(), "state": "complete", "complete": 30, "report_commit": sha})
    except BaseException as exc:
        if current is not None and current.poll() is None:
            os.killpg(current.pid, signal.SIGTERM)
            current.wait(timeout=30)
            subprocess.run([sys.executable, str(JOBS), "release", "--pid", str(current.pid)])
        reason = f"{type(exc).__name__}: {exc}"
        # ローカルのパス等を、外へ送る停止記録に混ぜない。
        reason = re.sub(r"/(?:Users|home)/[^\s'\"]+", "<ローカルパス>", reason)
        write_json(BASE / "status.json", {"time": now(), "state": "stopped", "reason": reason})
        try:
            aggregate(BASE, plan)
            publish(f"停止：{reason}。途中出力を保存。完走・照合済みだけの暫定集計を添付。", evidence=True)
        except BaseException as report_exc:
            write_json(BASE / "unpublished_stop.json", {"time": now(), "reason": reason, "publish_error_type": type(report_exc).__name__})
        raise


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=("prepare", "run", "one"))
    ap.add_argument("label", nargs="?")
    a = ap.parse_args()
    if a.mode == "prepare":
        prepare()
    elif a.mode == "run":
        run_all()
    else:
        return one(a.label)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

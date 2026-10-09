"""（二つ目、10/10 03:50：前の台本は終わった本の小さい記録づくりを待つ間に新しい本を始めなかったので、まだ始まっていない本をこちらに移した。前の台本は STOP_DESKTOP で新しい本を始めず、自分の走っている本の後始末だけをする）\nデスクトップの PC（WSL）で、第 1 波の順番待ちの本を走らせる（受け箱の指示 45・47、10/10 00:00 から。指示 50 で 24 時まで待った）。
命令：~/cloud/wave1/desktop_commands.json（3b の残り 18 本と、5a・世界 1・種 1 の c57467ea でのやり直し）。クラウドと同じ命令・設定・λ、出力先だけ D:（/mnt/d/sfn_runs/cloud/<本>/output）。
各本：cwd は版のきれいな作業場所（~/sfn/audit/_read/<jsonlog4cea|jsonloge9>）、PYTHONHASHSEED=0、LANG・LC_* を外す、setsid、/usr/bin/time -v。既にある出力の本は飛ばす。
同時の本数：9 本まで。新しい本は、MemAvailable −（この台本の走っている本の予約の合計 − その本の今の常駐）≧ 次の本の予約 ＋ 4GiB のときだけ始める。
空きの決まり（指示 24）：D: の空き 20GB 以上、C: の空き 10GB 以上。~/cloud/wave1/STOP_DESKTOP があれば新しい本を始めない。
終わった本（rc=0）は、クラウドの本と同じ形で上げる：push_small.sh で小さい記録（norm_hash など）、S3 に出力、GitHub に小さい記録と side（gzip -n）と第二段（ロック ~/cloud/wave1/git.lock）。
機械の欄は「デスクトップ（WSL）」。rc≠0 の本は記録して、Claude に知らせる（指示 40 の 2 のやり直しは、手で行う）。"""
import json, os, shutil, subprocess, threading, time
from pathlib import Path
H = Path.home(); W = H / "cloud/wave1"; LOG = W / "desktop_runner2.log"; DONE = W / "done.tsv"; RES = H / "v33prod/results"
cmds = json.load(open(W / "desktop_commands.json"))
MAXPAR = 9


def log(s):
    with open(LOG, "a") as f:
        f.write(time.strftime("%F %T ") + s + "\n")


def meminfo():
    return {l.split(":")[0]: int(l.split()[1]) * 1024 for l in open("/proc/meminfo")}


def rss_tree(pid):
    tot = 0
    for p in [pid] + subprocess.run(["pgrep", "-P", str(pid)], capture_output=True, text=True).stdout.split():
        try:
            tot += int(open(f"/proc/{p}/statm").read().split()[1]) * 4096
        except OSError:
            pass
    return tot


def space_ok():
    d = shutil.disk_usage("/mnt/d").free / 1e9; c = shutil.disk_usage("/mnt/c").free / 1e9
    return d >= 20 and c >= 10, f"D: {d:.0f}GB、C: {c:.0f}GB"


def start(c):
    rd = Path(c["argv"][3]).parent; rd.mkdir(parents=True, exist_ok=True)
    src = H / "sfn/audit/_read" / c["wt"]
    head = subprocess.run(["git", "-C", str(src), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    dirty = subprocess.run(["git", "-C", str(src), "status", "--porcelain"], capture_output=True, text=True).stdout
    assert head == c["commit"] and not dirty, f"{src} が {c['commit'][:7]} のきれいな状態でない"
    json.dump(c["argv"], open(rd / "native_command.json", "w"), ensure_ascii=False, indent=1)
    env = {k: v for k, v in os.environ.items() if k not in ("LANG", "LC_ALL", "LC_CTYPE")}; env["PYTHONHASHSEED"] = "0"
    out = open(rd / "run.log", "w"); err = open(rd / "time.log", "w")
    p = subprocess.Popen(["/usr/bin/time", "-v", *c["argv"]], cwd=src, env=env, stdout=out, stderr=err, start_new_session=True)
    return p, rd


def finish(c, rd, rc):
    with open(rd / "run.log", "a") as f:
        f.write(f"rc={rc}\n")
    name = c["name"]
    if rc != 0:
        DONE.open("a").write(f"{name}\trc={rc}\t{time.strftime('%F %T')}\t\t止まり（デスクトップ（WSL））\n")
        log(f"★ {name} は rc={rc}（デスクトップ（WSL））"); return
    r = subprocess.run(["bash", str(H / "cloud/push_small.sh"), str(rd), name, "-"], capture_output=True, text=True)
    if r.returncode != 0:
        log(f"★ {name} の小さい記録を作れなかった：{r.stderr[-300:]}"); return
    (rd / "small" / "machine.txt").write_text("デスクトップ（WSL）\n")
    b = (H / "cloud/BUCKET").read_text().strip()
    subprocess.run(f"source {H}/cloud/aws_env.sh; aws s3 sync --only-show-errors {rd}/output s3://{b}/cloud_runs/{name}/output && "
                   f"aws s3 cp --only-show-errors {rd}/small/files_sha256.tsv s3://{b}/cloud_runs/{name}/files_sha256.tsv", shell=True, executable="/bin/bash")
    side = next(iter(sorted((rd / "output/side").glob("*/seed[0-9][0-9][0-9].jsonl"))), None)
    st2 = next(iter(sorted((rd / "output/stage2").glob("*/seed[0-9][0-9][0-9].jsonl.gz"))), None)
    sh = f'''exec 8>{W}/git.lock; flock 8; cd {RES} && git pull -q --rebase origin results-2026-09-27; G=ataru-0608/cloud_runs/{name}; mkdir -p $G && cp {rd}/small/* $G/
{f'gzip -n -c {side} > $G/$(basename {side} .jsonl).side.jsonl.gz' if side else 'true'}
{f'cp {st2} $G/$(basename {st2} .jsonl.gz).stage2.jsonl.gz' if st2 else 'true'}
for f in $G/*.side.jsonl.gz $G/*.stage2.jsonl.gz; do [ -f "$f" ] && (cd $G && sha256sum $(basename $f) > $(basename $f).sha256); done
git add $G && {{ git diff --cached --quiet -- $G || git commit -q -m "第 1 波の一本（デスクトップ（WSL））：{name}（走行の係）" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>" -- $G; }}
for i in 1 2 3 4 5; do git push -q origin HEAD:results-2026-09-27 && break; sleep 20; git pull -q --rebase origin results-2026-09-27; done'''
    subprocess.run(sh, shell=True, executable="/bin/bash")
    DONE.open("a").write(f"{name}\trc=0\t{time.strftime('%F %T')}\t{time.strftime('%F %T')}\tok、デスクトップ（WSL）\n")
    log(f"済み {name}（デスクトップ（WSL））")


queue = [c for c in cmds if not Path(c["argv"][3]).exists()]
running = {}
log(f"始めた：{len(queue)} 本（同時 {MAXPAR} 本まで）")
while queue or running:
    for name, (p, rd, c) in list(running.items()):
        rc = p.poll()
        if rc is not None:
            del running[name]; threading.Thread(target=finish, args=(c, rd, rc)).start()   # 小さい記録づくり（D: の上で 10〜20 分）を待たずに次の本を始める
    if queue and len(running) < MAXPAR and not (W / "STOP_DESKTOP2").exists():
        ok, msg = space_ok()
        mi = meminfo()
        owed = sum(max(0, c["mem_gb"] * 1e9 - rss_tree(p.pid)) for p, rd, c in running.values())
        if ok and mi["MemAvailable"] - owed >= queue[0]["mem_gb"] * 1e9 + 4 * 2 ** 30:
            c = queue.pop(0); p, rd = start(c); running[c["name"]] = (p, rd, c)
            log(f"始めた {c['name']}（走っている {len(running)} 本、{msg}、MemAvailable {mi['MemAvailable'] / 2 ** 30:.1f}GiB）")
            time.sleep(10); continue
    time.sleep(60)
log("全部終わった")

#!/usr/bin/env python3
"""重い処理の受付表の Ubuntu 版（クラウドの機械用。2026-10-09、受け箱の指示 31・動詞の包みの README「Ubuntu 対応の既存 jobs 受付」）。
マックの jobs.py（mac/jobs_20261004/jobs.py）の写しで、命令・欄・条件 2・4・5 と重い Python の決まりは同じ。替えたのは、マック専用の測り方（pmset・sysctl・vm_stat・memory_pressure）を Linux の測り方にした所と、条件 1 の予算だけ：
  条件 1：予算 = 物理メモリ（/proc/meminfo の MemTotal）− 4 GiB（走行の係の決まり「空き 4 GiB を残す」）。
  条件 2：スワップの使用量 = /proc/meminfo の SwapTotal − SwapFree。
  条件 3：熱 = /sys/class/thermal の thermal_zone の温度がどの trip 点（passive・hot・critical）も超えていない、かつ cooling_device（Processor）の cur_state がどれも 0（CPU を熱で絞っていない）。
          どちらも測れない（両方の欄が一つも無い）ときは、熱の確認ができないとして拒む（値を推測で真にしない）。
  表・ロック・スワップの記録は、この jobs.py と同じフォルダ（例 /srv/jobs/）に置く。
以下はマックの元の説明（条件 1・3 の測り方だけ上のとおり読み替える）。
マックの重い処理の受付表（委任書 2026-10-04「マックの重い処理の受付表」）。模型のコードには触らない。
共有の受付表：~/jobs/registry.tsv（PID・担当・見込みの最大メモリ GB・開始時刻・コマンドの要約）。書くときは ~/jobs/registry.lock で排他。
命令：
  claim  ：始める前に呼ぶ。条件を全部満たせば表に書いて 0 を返す。満たさなければ理由を出して 1 を返す（表には書かない）。
           python3 ~/jobs/jobs.py claim --owner <担当> (--kind <既知の種類> | --mem <GB>) [--pid <PID>] [--cmd "<要約>"] [--disk-path <出力先>]
           --pid を省くと、呼んだシェル（jobs.py の親）の PID を書く。登録した PID の子孫（子・孫…）も登録済みとみなす。
  release：終わったら呼ぶ。表から消す。  python3 ~/jobs/jobs.py release [--pid <PID>]（省くと呼んだシェルの PID）
  status ：表、表に無い重い Python、空きメモリ、出力先のディスクの空き、スワップ、熱の状態を出す。  python3 ~/jobs/jobs.py status [--disk-path <出力先>]
  run    ：claim → 実行 → release をまとめて行う。  python3 ~/jobs/jobs.py run --owner <担当> --kind <種類> -- <コマンド …>
           拒まれたら実行せずに 1 を返す（待つかどうかは呼んだ側が決める）。--wait を付けると、通るまで 60 秒ごとに claim をやり直す。
  sampler：スワップと熱を 60 秒ごとに ~/jobs/swap.tsv に書き続ける（claim の条件 2 のため。claim・status は、動いていなければ自動で始める）。
claim の条件：
  1 表の見込みの合計 ＋ 新しい処理の見込み ≦ 24 GB（マックの値。Ubuntu 版は上の物理メモリ − 4 GiB）。
  2 スワップの使用量が直近 10 分で増えていない：swap.tsv の直近 10 分の記録の最大が、その窓の最初の値を超えていない。
    記録が 10 分ぶん無ければ（sampler を始めたばかり等）、拒む（仮の決定）。
  3 pmset -g therm に熱・性能の警告が無く、CPU の速度の制限（CPU_Speed_Limit）が 100。
    制限の行が無い（"No CPU power status has been recorded"）ときは、制限なしとみなす（仮の決定）。
  4 表に無い重い Python があれば拒み、その PID を出す。
  5 出力先のボリュームの空きが 20 GiB 未満なら拒み、空きを出す。予約の会計はしない。
    claim・run・status の --disk-path は出力先（未作成でもよい）。省略時は呼んだ場所。
    未作成なら最も近い既存の親で測る。測れないときは claim を拒む。
重い Python（仮の決定）：実行ファイルが Python の処理のうち、multiprocessing の resource_tracker と jobs.py 自身を除き、
  常駐メモリ（RSS）が 100 MB 以上か、multiprocessing の計算する子（spawn_main）であるもの。CPU 率は使わない（止まっている処理も数える）。
  監督役・見張り役の小さな処理（RSS 100 MB 未満で spawn_main でない）は数えない。status には全部の Python を出す。
死んだ PID の行は、claim・status・release のたびに消す。"""
from __future__ import annotations

import fcntl
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime

HOME = os.path.expanduser("~")
# 確かめ用：環境変数 JOBS_DIR で表・ロックの場所を、JOBS_SWAP でスワップの記録の場所を替えられる（本番は使わない）
DIR = os.environ.get("JOBS_DIR") or os.path.dirname(os.path.abspath(__file__))
REG = os.path.join(DIR, "registry.tsv")
LOCK = os.path.join(DIR, "registry.lock")
SWAP = os.environ.get("JOBS_SWAP") or os.path.join(DIR, "swap.tsv")
SAMPLER_PID = os.path.join(DIR, "sampler.pid")
def meminfo():
    out = {}
    for line in open("/proc/meminfo"):
        k, v = line.split(":", 1)
        out[k] = int(v.split()[0]) * 1024   # バイト
    return out


BUDGET_GB = round(meminfo()["MemTotal"] / 1024 ** 3 - 4.0, 1)   # 物理メモリ − 4 GiB
MIN_DISK_FREE_BYTES = 20 * 1024 ** 3
SWAP_WINDOW = 600
HEAVY_RSS_MB = 100
HEADER = "pid\towner\tmem_gb\tstart\tcmd"
# 見込みの最大メモリ（GB）。実測 × 1.2。未知の処理は、小さく一本走らせて実測してから決める
KNOWN = {
    "sme": (5.2, "SME 版の走行一本（マックの段 4 の一本の最大常駐 4.3 GiB × 1.2。control/2026-10-03_SME版の独立点検_走行の係.md）"),
    "collective8": (1.2, "集団化の 8 体の集団一つ（委任書の値）"),
    "collective2": (0.4, "集団化の一対一の集団一つ（まとめ役と二体の合計の最大 309.73 MiB × 1.2。control/2026-10-02_集団化の一対一_Codex.md）"),
    "v3run": (0.2, "今の規則の単体の走行一本（tools/v3_run.py、--workers 1。manifest の peak_rss_mb の最大 167.5 MB × 1.2）"),
}


def now():
    return datetime.now().strftime("%Y-%m-%dT%H:%M:%S")


def sh(cmd):
    return subprocess.run(cmd, capture_output=True, text=True).stdout


def alive(pid):
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def procs():
    """{pid: (ppid, rss_mb, command)}"""
    out = {}
    for line in sh(["/bin/ps", "-eo", "pid=,ppid=,rss=,args="]).splitlines():
        p = line.strip().split(None, 3)
        if len(p) == 4:
            out[int(p[0])] = (int(p[1]), int(p[2]) / 1024, p[3])
    return out


def short(cmd, n=110):
    """コマンドの最初の語（実行ファイル）を名前だけにして縮める。"""
    p = cmd.split(None, 1)
    return (os.path.basename(p[0]) + (" " + p[1] if len(p) > 1 else ""))[:n]


def origin(pid, ps):
    """spawn_main の子なら、spawn でも resource_tracker でもない一番近い祖先のコマンド（どの処理の子かを見るため）。"""
    p = ps.get(pid, (0, 0, ""))[0]
    while p in ps and ("spawn_main" in ps[p][2] or "resource_tracker" in ps[p][2]):
        p = ps[p][0]
    return f"PID {p}：{short(ps[p][2], 140)}" if p in ps else "—"


def is_python(cmd):
    exe = os.path.basename(cmd.split()[0]).lower()
    return exe.startswith("python") or exe == "python"


def heavy(cmd, rss):
    if not is_python(cmd) or "resource_tracker" in cmd or "jobs/jobs.py" in cmd:
        return False
    return rss >= HEAVY_RSS_MB or "spawn_main" in cmd


def read_reg():
    if not os.path.exists(REG):
        return []
    rows = []
    for line in open(REG, encoding="utf-8").read().splitlines()[1:]:
        if line.strip():
            p = line.split("\t")
            rows.append({"pid": int(p[0]), "owner": p[1], "mem_gb": float(p[2]), "start": p[3], "cmd": p[4] if len(p) > 4 else ""})
    return rows


def write_reg(rows):
    tmp = REG + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(HEADER + "\n")
        for r in rows:
            f.write(f"{r['pid']}\t{r['owner']}\t{r['mem_gb']}\t{r['start']}\t{r['cmd'].replace(chr(9), ' ')}\n")
    os.replace(tmp, REG)


class Locked:
    def __enter__(self):
        os.makedirs(DIR, exist_ok=True)
        self.f = open(LOCK, "w")
        fcntl.flock(self.f, fcntl.LOCK_EX)
        return self

    def __exit__(self, *a):
        fcntl.flock(self.f, fcntl.LOCK_UN)
        self.f.close()


def prune():
    """死んだ PID の行を消す（ロックの中で呼ぶ）。消した行を返す。"""
    rows = read_reg()
    keep = [r for r in rows if alive(r["pid"])]
    gone = [r for r in rows if not alive(r["pid"])]
    if gone or not os.path.exists(REG):
        write_reg(keep)
    return keep, gone


def registered_pids(rows, ps):
    """表の PID と、その子孫の PID。"""
    kids = {}
    for pid, (ppid, _r, _c) in ps.items():
        kids.setdefault(ppid, []).append(pid)
    out, stack = set(), [r["pid"] for r in rows]
    while stack:
        p = stack.pop()
        if p in out:
            continue
        out.add(p)
        stack += kids.get(p, [])
    return out


def unregistered_heavy(rows, ps):
    reg = registered_pids(rows, ps)
    return [(pid, rss, cmd) for pid, (_pp, rss, cmd) in sorted(ps.items()) if heavy(cmd, rss) and pid not in reg]


def therm():
    """Linux の熱の確認。返す値は (警告の並び, 絞りの最大の段（cooling_device の cur_state の最大、無ければ None）, 原の記録)。"""
    import glob
    warn, raw, zones, states = [], [], 0, []
    rd = lambda p: open(p).read().strip()
    for z in sorted(glob.glob("/sys/class/thermal/thermal_zone*")):
        try:
            t = int(rd(z + "/temp"))
        except (OSError, ValueError):
            continue
        zones += 1
        raw.append(f"{os.path.basename(z)} temp={t}")
        for tp in glob.glob(z + "/trip_point_*_type"):
            try:
                kind, lim = rd(tp), int(rd(tp.replace("_type", "_temp")))
            except (OSError, ValueError):
                continue
            if kind in ("passive", "hot", "critical") and lim > 0 and t >= lim:
                warn.append(f"{os.path.basename(z)} の温度 {t} が {kind} の点 {lim} を超えた")
    for c in sorted(glob.glob("/sys/class/thermal/cooling_device*")):
        try:
            kind, cur = rd(c + "/type"), int(rd(c + "/cur_state"))
        except (OSError, ValueError):
            continue
        states.append(cur)
        if cur != 0:
            warn.append(f"{os.path.basename(c)}（{kind}）の cur_state が {cur}（熱で絞っている）")
    raw.append(f"thermal_zone {zones} 個、cooling_device {len(states)} 個（cur_state の最大 {max(states) if states else None}）")
    if zones == 0 and not states:
        warn.append("熱を測る欄（thermal_zone・cooling_device）が一つも無い。熱の確認ができない")
    return warn, (max(states) if states else None), "\n".join(raw)


def swap_used_mb():
    m = meminfo()
    return (m["SwapTotal"] - m["SwapFree"]) / 1024 ** 2


def sampler_running():
    try:
        pid = int(open(SAMPLER_PID).read().strip())
        return alive(pid) and "jobs.py sampler" in procs().get(pid, (0, 0, ""))[2]
    except (OSError, ValueError):
        return False


def ensure_sampler():
    if os.environ.get("JOBS_SWAP"):
        return True   # 確かめ用の記録を使うときは始めない
    if not sampler_running():
        subprocess.Popen([sys.executable, os.path.abspath(__file__), "sampler"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         start_new_session=True)
        return False
    return True


def swap_window():
    """直近 SWAP_WINDOW 秒の (時刻, スワップ MB) の並び。"""
    if not os.path.exists(SWAP):
        return []
    t0 = time.time() - SWAP_WINDOW
    out = []
    for line in open(SWAP, encoding="utf-8").read().splitlines():
        p = line.split("\t")
        if len(p) >= 2 and p[1] != "None":
            t = float(p[0])
            if t >= t0 - 60:
                out.append((t, float(p[1])))
    return out


def swap_ok():
    w = swap_window()
    if not w or time.time() - w[0][0] < SWAP_WINDOW - 90:
        return False, f"スワップの記録が直近 10 分ぶん無い（記録 {len(w)} 点。sampler を始めたばかりなら 10 分待つ）"
    first, mx = w[0][1], max(v for _t, v in w)
    if mx > first:
        return False, f"スワップが直近 10 分で増えた（窓の最初 {first:.1f} MB → 最大 {mx:.1f} MB、今 {w[-1][1]:.1f} MB）"
    return True, f"スワップは直近 10 分で増えていない（{first:.1f} MB → 今 {w[-1][1]:.1f} MB）"


def mem_free():
    m = meminfo()
    gb = lambda k: f"{m[k] / 1024 ** 3:.1f} GiB"
    return {"MemTotal": gb("MemTotal"), "MemAvailable": gb("MemAvailable"), "MemFree": gb("MemFree")}


def disk_space(path):
    """出力先を実体に解決し、最も近い既存の親があるボリュームの空きを返す。"""
    target = os.path.realpath(os.path.expanduser(path or os.getcwd()))
    probe = target
    while not os.path.exists(probe):
        parent = os.path.dirname(probe)
        if parent == probe:
            raise OSError(f"既存の親が見つからない：{target}")
        probe = parent
    return target, probe, shutil.disk_usage(probe).free


def disk_message(target, probe, free):
    return f"出力先 {target}（測定先 {probe}）の空き {free / 1024 ** 3:.3f} GiB、下限 {MIN_DISK_FREE_BYTES / 1024 ** 3:.0f} GiB"


def cmd_claim(a):
    mem = a.mem if a.mem is not None else (KNOWN[a.kind][0] if a.kind in KNOWN else None)
    if mem is None:
        print(f"拒む：見込みのメモリが決まらない（--mem で GB を渡すか、--kind を {sorted(KNOWN)} から選ぶ。未知の処理は小さく一本走らせて実測してから）")
        return 1
    pid = a.pid or os.getppid()
    ensure_sampler()
    with Locked():
        rows, gone = prune()
        for r in gone:
            print(f"死んだ PID の行を消した：{r['pid']}（{r['owner']}）")
        ps = procs()
        reasons = []
        tot = sum(r["mem_gb"] for r in rows)
        if tot + mem > BUDGET_GB:
            reasons.append(f"メモリの予算を超える（表の合計 {tot:.1f} GB ＋ 新しい処理 {mem:.1f} GB ＞ {BUDGET_GB:.0f} GB）")
        ok, msg = swap_ok()
        if not ok:
            reasons.append(msg)
        warn, _limit, _raw = therm()
        reasons += warn
        un = unregistered_heavy(rows, ps)
        if un:
            reasons.append("表に無い重い Python がある：" + "、".join(f"PID {p}（{rss:.0f} MB、{short(c, 80)}）" for p, rss, c in un))
        try:
            target, probe, free = disk_space(a.disk_path)
            if free < MIN_DISK_FREE_BYTES:
                reasons.append("ディスクの空きが足りない：" + disk_message(target, probe, free))
        except OSError as e:
            reasons.append(f"出力先のディスクの空きを測れない：{e}")
        if any(r["pid"] == pid for r in rows):
            reasons.append(f"PID {pid} はもう表にある（同じ処理の二重の登録はしない）")
        if not alive(pid):
            reasons.append(f"PID {pid} は動いていない")
        if reasons:
            print("拒む：")
            for x in reasons:
                print("  -", x)
            return 1
        rows.append({"pid": pid, "owner": a.owner, "mem_gb": mem, "start": now(), "cmd": (a.cmd or short(ps.get(pid, (0, 0, ""))[2], 200))})
        write_reg(rows)
    print(f"受け付けた：PID {pid}、担当 {a.owner}、見込み {mem:.1f} GB（表の合計 {tot + mem:.1f} / {BUDGET_GB:.0f} GB）。{msg}")
    return 0


def cmd_release(a):
    pid = a.pid or os.getppid()
    with Locked():
        rows, _gone = prune()
        keep = [r for r in rows if r["pid"] != pid]
        write_reg(keep)
    print(f"消した：PID {pid}" if len(keep) != len(rows) else f"表に無い：PID {pid}（死んだ行は消した）")
    return 0


def cmd_status(a):
    running = ensure_sampler()
    with Locked():
        rows, gone = prune()
    ps = procs()
    print(f"# 受付表（{now()}）  見込みの合計 {sum(r['mem_gb'] for r in rows):.1f} / {BUDGET_GB:.0f} GB")
    for r in gone:
        print(f"  死んだ PID の行を消した：{r['pid']}（{r['owner']}）")
    print("PID\t担当\t見込み GB\t開始\t今の RSS 合計（子孫を含む）\tコマンド")
    for r in rows:
        tree = registered_pids([r], ps)
        rss = sum(ps[p][1] for p in tree if p in ps)
        print(f"{r['pid']}\t{r['owner']}\t{r['mem_gb']}\t{r['start']}\t{rss / 1024:.2f} GB\t{short(r['cmd'], 80)}")
    print("\n# 表に無い重い Python")
    un = unregistered_heavy(rows, ps)
    for pid, rss, c in un:
        print(f"PID {pid}（親 {ps[pid][0]}）\t{rss / 1024:.2f} GB\t{short(c, 60)}\n    もとの処理 {origin(pid, ps)}")
    if not un:
        print("（無い）")
    print("\n# Python の処理すべて（重い＝*、表に登録済み＝R）")
    reg = registered_pids(rows, ps)
    for pid, (pp, rss, c) in sorted(ps.items()):
        if is_python(c):
            print(f"{'*' if heavy(c, rss) else ' '}{'R' if pid in reg else ' '} PID {pid}（親 {pp}）\t{rss:.0f} MB\t{short(c)}")
    print("\n# 空きメモリ")
    for k, v in mem_free().items():
        print(f"{k}：{v}")
    print("\n# ディスクの空き")
    try:
        target, probe, free = disk_space(a.disk_path)
        print(disk_message(target, probe, free))
    except OSError as e:
        print(f"測れない：{e}")
    ok, msg = swap_ok()
    print(f"\n# スワップ：今 {swap_used_mb()} MB。{msg}。sampler：{'動いている' if running else '今始めた'}")
    warn, limit, raw = therm()
    print(f"\n# 熱：{'警告なし' if not warn else '、'.join(warn)}。cooling_device の cur_state の最大：{limit}")
    print(raw)
    return 0


def cmd_sampler(_a):
    os.makedirs(DIR, exist_ok=True)
    open(SAMPLER_PID, "w").write(str(os.getpid()))
    while True:
        warn, limit, _raw = therm()
        with open(SWAP, "a", encoding="utf-8") as f:
            f.write(f"{time.time():.0f}\t{swap_used_mb()}\t{now()}\t{'|'.join(warn) or 'ok'}\t{limit}\n")
        # 24 時間より古い記録を落とす（1 時間に一度）
        if int(time.time()) % 3600 < 60:
            t0 = time.time() - 86400
            lines = [l for l in open(SWAP, encoding="utf-8").read().splitlines() if l and float(l.split("\t")[0]) >= t0]
            open(SWAP, "w", encoding="utf-8").write("\n".join(lines) + "\n")
        time.sleep(60)


def cmd_run(a):
    import argparse  # noqa
    while True:
        ns = type("A", (), {"owner": a.owner, "mem": a.mem, "kind": a.kind, "pid": os.getpid(), "cmd": " ".join(a.command)[:200], "disk_path": a.disk_path})
        rc = cmd_claim(ns)
        if rc == 0:
            break
        if not a.wait:
            return 1
        time.sleep(60)
    try:
        return subprocess.call(a.command)
    finally:
        cmd_release(type("A", (), {"pid": os.getpid()}))


def main():
    sys.stdout.reconfigure(line_buffering=True)
    import argparse
    ap = argparse.ArgumentParser(description="重い処理の受付表（Ubuntu 版）")
    sp = ap.add_subparsers(dest="op", required=True)
    c = sp.add_parser("claim")
    c.add_argument("--owner", required=True)
    c.add_argument("--mem", type=float)
    c.add_argument("--kind", choices=sorted(KNOWN))
    c.add_argument("--pid", type=int)
    c.add_argument("--cmd")
    c.add_argument("--disk-path", help="出力先のボリュームを測る場所（省略時は呼んだ場所）")
    r = sp.add_parser("release")
    r.add_argument("--pid", type=int)
    s = sp.add_parser("status")
    s.add_argument("--disk-path", help="出力先のボリュームを測る場所（省略時は呼んだ場所）")
    sp.add_parser("sampler")
    sp.add_parser("known")
    u = sp.add_parser("run")
    u.add_argument("--owner", required=True)
    u.add_argument("--mem", type=float)
    u.add_argument("--kind", choices=sorted(KNOWN))
    u.add_argument("--wait", action="store_true")
    u.add_argument("--disk-path", help="出力先のボリュームを測る場所（省略時は呼んだ場所）")
    u.add_argument("command", nargs=argparse.REMAINDER)
    a = ap.parse_args()
    if a.op == "run" and a.command and a.command[0] == "--":
        a.command = a.command[1:]
    if a.op == "known":
        for k, (g, why) in KNOWN.items():
            print(f"{k}\t{g} GB\t{why}")
        return 0
    return {"claim": cmd_claim, "release": cmd_release, "status": cmd_status, "sampler": cmd_sampler, "run": cmd_run}[a.op](a)


if __name__ == "__main__":
    sys.exit(main())

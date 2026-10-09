#!/bin/bash
# ゲームの間、デスクトップの較正の本を一時停止する（受け箱の指示 20）。止めるのではなく、再開できる休み。
#   ~/game_mode.sh on      較正の本（~/calib_w1・~/calib_w2 の v3_run の模型の過程と、その子の過程）に SIGSTOP を送る
#   ~/game_mode.sh off     同じ過程に SIGCONT を送る
#   ~/game_mode.sh status  止まっている本の数を出す
# 対象は、引数の二つ目が tools/v3_run.py で、出力先が ~/calib_w1/・~/calib_w2/・/mnt/d/sfn_runs/cloud/ の過程、表層の解析の再生（selcands_sme・replay.py）と
# 第 1 波の見え方の見張り（wave1_refresh_loop.sh）と、その子孫だけ（指示 50 で足した）。
# AWS CLI・SSH・この係（Claude）の過程・表層の解析の見張りなど、ほかの過程には送らない。決まった番号にだけ送る（名前で探して送らない）。
# 止めた時刻と再開した時刻は ~/v33prod/results/ataru-0608/game_mode/pause_log.tsv に追記する（較正の時間から止めていた時間を引けるように）。
set -u
LOG=$HOME/v33prod/results/ataru-0608/game_mode/pause_log.tsv
mkdir -p "$(dirname "$LOG")"
[ -f "$LOG" ] || echo -e "time\taction\tn_runs\tn_processes\tpids" > "$LOG"

targets() {   # 較正の本の v3_run の過程と、その子孫の番号を出す（一行に一つ）
  python3 - <<'PY'
import os
procs = {}
for p in os.listdir("/proc"):
    if not p.isdigit():
        continue
    try:
        a = open(f"/proc/{p}/cmdline", "rb").read().split(b"\0")
        ppid = open(f"/proc/{p}/stat").read().rsplit(")", 1)[1].split()[1]
        procs[p] = (a, ppid)
    except Exception:
        pass
def target(a):
    # 較正の本（~/calib_w1・~/calib_w2）、第 1 波のデスクトップの本（出力先が /mnt/d/sfn_runs/cloud/、指示 45・47）、
    # 表層の解析の再生（tools/selcands_sme.py・surface の replay.py）と、その見え方を足す見張り（wave1_refresh_loop.sh）。指示 50 で足した
    if len(a) > 3 and a[1] == b"tools/v3_run.py" and (b"/calib_w1/" in a[3] or b"/calib_w2/" in a[3] or a[3].startswith(b"/mnt/d/sfn_runs/cloud/")):
        return True
    if len(a) > 1 and a[1] == b"tools/selcands_sme.py":
        return True
    if any(x.endswith(b"surface/replay.py") or x == b"replay.py" for x in a[:3]) and b"configs_wave1_replay.json" in b" ".join(a):
        return True
    if len(a) > 1 and a[0] == b"bash" and a[1].endswith(b"surface/wave1_refresh_loop.sh"):
        return True
    return False
roots = [p for p, (a, _) in procs.items() if target(a)]
out, todo = set(roots), list(roots)
while todo:
    q = todo.pop()
    for p, (_, pp) in procs.items():
        if pp == q and p not in out:
            out.add(p)
            todo.append(p)
print(f"#runs {len(roots)}")
for p in sorted(out, key=int):
    print(p)
PY
}

state_counts() {   # 止まっている（T）較正の本の数と、過程の数
  local runs=0 stopped=0 procs=0 sp=0
  while read -r line; do
    case $line in "#runs "*) runs=${line#\#runs }; continue;; esac
    procs=$((procs + 1))
    st=$(awk '{print $3}' /proc/$line/stat 2>/dev/null)
    [ "$st" == "T" ] && sp=$((sp + 1))
  done < <(targets)
  echo "$runs $procs $sp"
}

case "${1:-status}" in
  on|off)
    SIG=$([ "$1" == on ] && echo STOP || echo CONT)
    mapfile -t T < <(targets)
    RUNS=${T[0]#\#runs }; PIDS=("${T[@]:1}")
    [ ${#PIDS[@]} -gt 0 ] && kill -$SIG "${PIDS[@]}"
    echo -e "$(date '+%F %T')\t$1\t$RUNS\t${#PIDS[@]}\t${PIDS[*]}" >> "$LOG"
    read -r runs procs sp < <(state_counts)
    echo "$1：較正の本 $runs 本（過程 $procs）に SIG$SIG を送った。今止まっている過程 $sp。記録：$LOG"
    ;;
  status)
    read -r runs procs sp < <(state_counts)
    echo "較正の本 $runs 本（過程 $procs）のうち、止まっている過程 $sp"
    ;;
  *) echo "使い方：~/game_mode.sh on|off|status"; exit 2;;
esac

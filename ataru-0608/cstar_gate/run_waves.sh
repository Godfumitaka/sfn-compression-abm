#!/bin/bash
# 受け箱の指示 8：SME の係の高速化の旗の全長の関門（C*②、世界 2・種 1、全 1,740 試行）。SME の係の命令（run/commands.json、
# prepare_desktop_instruction15_01.py が作ったもの）を、その cwd と command のまま走らせる。模型のコードと命令は変えない。
# 並べ方：一本 11GB、同時 3 本まで（指示 8）。空き 4GiB を残す決まり（memroom_any.py）で、35GiB の WSL では 2 本まで。
#   波 1：original_C と off_C → off_C を original_C と比べる。
#   波 2：gc_C と encode_C → それぞれ original_C と比べる。
#   波 3：both_C → original_C と比べる。
#   比べが一つでも通らなければ、次の波を始めない（SME の係の命令の「一つでも不通・不一致なら次を始めない」）。
# 各本の始める前に：10/9 09:00 の期限、C: の空き 20GB 以上、メモリの見込み。各本は setsid で切り離し、/usr/bin/time -v で実時間と最大常駐を残す。
set -u
G=$HOME/cstar_gate; R=$G/run; LOG=$G/waves.log; PY=$(command -v python3.12)
say() { echo "$(date '+%F %T') $*" | tee -a $LOG; }
cfree() { df -BG /mnt/c | awk 'NR==2 {gsub("G","",$4); print $4}'; }
field() { python3 -c "import json,shlex,sys;c=[x for x in json.load(open('$R/commands.json'))['commands'] if x['case']=='$1'][0];print(c['cwd'] if '$2'=='cwd' else shlex.join(c['command']))"; }
start() {
  local c=$1
  if [ "$(date +%s)" -ge "$(date -d '2026-10-09 09:00' +%s)" ]; then say "★ 10/9 09:00 を過ぎたので $c を始めない"; return 1; fi
  if (( $(cfree) < 20 )); then say "★ C: の空き $(cfree)GB（20GB 未満）。$c を始めない"; return 1; fi
  while [[ $(python3 $HOME/queue/memroom_any.py 11) != ok ]]; do sleep 30; done
  local CWD; CWD=$(field $c cwd); local CMD; CMD=$(field $c cmd)
  ( cd "$CWD" && setsid bash -c "/usr/bin/time -v $CMD > $R/$c/run.log 2> $R/$c/time.log; echo rc=\$? >> $R/$c/run.log" < /dev/null > /dev/null 2>&1 & )
  say "始めた $c（cwd $CWD、$(python3 $HOME/queue/memroom_any.py 11 --show)、C: $(cfree)GB）"
  sleep 20
}
waitfor() { for c in "$@"; do until grep -q "^rc=" $R/$c/run.log 2>/dev/null; do sleep 60; done; say "終わった $c（$(grep '^rc=' $R/$c/run.log)、$(grep -E 'Elapsed|Maximum resident' $R/$c/time.log | sed 's/^\s*//' | tr '\n' ' ')）"; done; }
cmp1() {
  local c=$1
  if (cd $G/helpers && nice -n 15 ionice -c3 $PY compare_cli_instruction15_01.py $R/original_C/output $R/$c/output $R/$c/comparison.json > $R/$c/compare.out 2>&1); then
    say "比べ $c：通った（$(tail -1 $R/$c/compare.out)）"; return 0
  else say "★ 比べ $c：通らない（$R/$c/compare.out、comparison.json）。次の波を始めない"; return 1; fi
}
say "始める（指示 8、SME の係の命令 run/commands.json）"
start original_C || exit 3; start off_C || exit 3
waitfor original_C off_C
cmp1 off_C || exit 4
start gc_C || exit 3; start encode_C || exit 3
waitfor gc_C encode_C
cmp1 gc_C; a=$?; cmp1 encode_C; b=$?
(( a == 0 && b == 0 )) || exit 4
start both_C || exit 3
waitfor both_C
cmp1 both_C || exit 4
say "全部終わり：4 つの比べがすべて通った"

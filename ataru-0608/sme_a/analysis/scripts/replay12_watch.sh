#!/bin/bash
# 主の条件の本番（160 本）が全部走り終わったら、解析の再生（run_replay.py）の同時の本数を 12 本まで増やす（2026-10-06 の依頼）。
# 走っている run_replay.py は --maxpar 4 で始めていて、途中で上限を変えられず、ロックで二つ目も始められない。そのため：
#   1. 本番が全部終わる（160 本に .done があり、走っている本番が 0）まで待つ。
#   2. ~/sme_analysis/STOP を置く → 前の run_replay.py は新しい再生を始めず、走っている再生を最後まで確かめて（写しも消して）抜ける。
#   3. STOP を外し、run_replay.py --maxpar 12 --total 12 で始め直す。
#   nice・ionice（run_replay.py の中でかける）、C: の空きの決まり（run_replay.py の中で 21GB 以上を確かめる）、写しを確かめ後に消す手順は変えない。
# 待っているあいだに前の run_replay.py が自分で抜けた（追いついた）ときは、今までどおり --maxpar 4 --wait で始め直す。
set -u
W=$HOME/sme_analysis; LOG=$W/replay12_watch.log; RES=$HOME/v33prod/results; CTRL="control/2026-10-06_主の条件の解析_走行の係.md"
say() { echo "$(date '+%F %T') $*" >> $LOG; }
ndone() { ls $HOME/smeprod_a/sme/*/seed*/ledgers/cells/*/*.done 2>/dev/null | wc -l; }
prod() { ps -eo args | awk '$2=="tools/v3_run.py"' | grep -c "/home/tatsu/smeprod_a/sme/"; }
rr_pid() { ps -eo pid,args | awk '$2 ~ /python3\.12$/ && $3=="run_replay.py" {print $1}' | head -1; }
nsel() { ps -eo args | awk '$2=="tools/selcands_sme.py"' | wc -l; }
ctl() { ( cd $RES && git pull -q --rebase origin results-2026-09-27; echo "$1" >> "$CTRL"; git add "$CTRL" && git commit -q -m "主の条件の解析：再生の同時の本数（走行の係）

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>" && for i in 1 2 3 4 5; do git push -q origin HEAD:results-2026-09-27 2>/dev/null && break; git pull -q --rebase origin results-2026-09-27 || git rebase --abort; sleep 5; done ) >> $LOG 2>&1; }
start_rr() { ( cd $W && setsid nohup python3.12 run_replay.py "$@" >> $W/run_replay.log 2>&1 < /dev/null & ); sleep 5; say "run_replay.py $* を始めた（PID $(rr_pid)）"; }
say "見張りを始めた（本番の完了 $(ndone)/160、走っている本番 $(prod)、run_replay PID $(rr_pid)）"
while ! { (( $(ndone) >= 160 )) && (( $(prod) == 0 )); }; do
  if [ -z "$(rr_pid)" ] && (( $(nsel) == 0 )) && [ ! -f $W/STOP ]; then
    say "前の run_replay.py が本番の終わる前に抜けていたので、今までどおり --maxpar 4 --wait で始め直す"; start_rr --maxpar 4 --wait
  fi
  sleep 60
done
say "本番 160 本が全部走り終わった（走っている本番 0）"
if [ -n "$(rr_pid)" ]; then
  touch $W/STOP; say "STOP を置いた。前の run_replay.py（PID $(rr_pid)）が走っている再生を終えて抜けるのを待つ（再生 $(nsel) 本）"
  while [ -n "$(rr_pid)" ]; do sleep 30; done
fi
while (( $(nsel) > 0 )); do sleep 30; done
rm -f $W/STOP; say "前の run_replay.py が抜けた。STOP を外した"
start_rr --maxpar 12 --total 12
ctl "- $(date '+%m/%d %H:%M') 本番 160 本が全部走り終わったので、再生の同時の本数を 12 本までにした（run_replay.py --maxpar 12 --total 12）。nice・ionice・C: の空きの確かめ・写しを確かめ後に消す手順は変えていない。前の --maxpar 4 の台本は STOP で走っている再生を終えさせてから抜けた。"
say "終わり"

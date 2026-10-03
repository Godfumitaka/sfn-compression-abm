#!/bin/bash
# 集団化：例外の日の場面から来た束の中身（2026-10-03 の追加）。A・C の通信あり、集団の種 1〜20 の 40 集団。★ 記録を読むだけ。並列 1。
# 重い処理の合計（Codex の計算する処理＋こちらの colldefs.py の主＋この 1 本）が 4 を超えるときは、この 1 本を一時停止する。
set -u
W=/Users/tatsu-admin/sfn/sfn-compression-abm-spcana; cd $W
S="/Users/tatsu-admin/Documents/ChatGPT/New project/codex_collective20_2026-10-02"
M=$HOME/v33prod/results/mac/collective20_20261002
OUT=$HOME/v310cprod/集団化で届いた定義/束; mkdir -p $OUT/A $OUT/C
LOG=$HOME/v310cprod/collbundles_gate.log
codex() { pgrep -f "tools/v3_run.py" | while read p; do [ -z "$(pgrep -P $p)" ] && lsof -a -p $p -d cwd -Fn 2>/dev/null | grep -q "Documents/ChatGPT" && echo $p; done | wc -l | tr -d ' '; }
# こちらの colldefs.py は、主の処理 1 本ごとに計算する子 1 本（ほかに管理用の resource_tracker が付くが計算しない）。主の数を数える
mine() { pgrep -f "tools/colldefs.py" | wc -l | tr -d ' '; }
for g in $(seq -f %03g 1 20); do for arm in A C; do
  if [ $arm = A ]; then root="$S/outputs/pilot_w2_recvA_g$g"; c=$M/runs/pilot_w2_recvA_g$g/counts.json
  else root="$S/outputs_C/pilot_w2_recvA_g$g"; c=$M/C/runs/pilot_w2_recvA_g$g/counts.json; fi
  free=$(df -g / | tail -1 | awk '{print $4}'); if [ "$free" -lt 15 ]; then echo "STOP 空きが 15GB 未満"; break 2; fi
  echo "== $(date +%T) $arm g$g"
  python3.12 tools/collbundles.py $OUT/$arm/pilot_w2_recvA_g$g.json "$root" $c &
  pid=$!; st=run
  while kill -0 $pid 2>/dev/null; do
    n=$(( $(codex) + $(mine) + 1 ))
    if [ $n -gt 4 ] && [ $st = run ]; then kill -STOP $pid; st=stop; echo "$(date +%T) 一時停止（合計 $n）" >> $LOG
    elif [ $n -le 4 ] && [ $st = stop ]; then kill -CONT $pid; st=run; echo "$(date +%T) 再開（合計 $n）" >> $LOG; fi
    sleep 10
  done
  wait $pid || echo "FAILED $arm g$g"
done; done
echo "== CBDONE $(date +%T)"

#!/bin/bash
# 表層の解析の見張り（走行の係が tmux で始める）。読むだけ。模型は走らせない。
#   N 分ごとに surface.py を回す（完了の印 .done が新しく出た本だけ読み、表を作り直す）。
#   表（per_run・pairs・memory_bits_vs_errors・seal_states・effort・columns）が前に push したときと変わっていたら push_hook.sh を呼ぶ。
# 使い方：tmux new -d -s surface 'bash ~/surface/watch.sh'
#   環境変数：INTERVAL_MIN（既定 10）、JOBS（surface.py の過程の数、既定 4、4 まで）、
#             PUSH（1＝変わったら push_hook.sh を呼ぶ〈既定〉、0＝呼ばない）、
#             REPLAY（1＝候補の記録が無い本を replay.py で再生する。既定 0。configs.json の群に replay の設定が要る）、
#             REPLAY_MAXPAR（再生の同時の数、既定 2）
# 止め方：~/surface/STOP_WATCH を置く（次の回の前に抜ける）。又は tmux の窓で Ctrl-C。
# ログ：~/surface/watch.log（再生は ~/surface/replay.log）
set -u
S=$HOME/surface; LOG=$S/watch.log
INTERVAL_MIN=${INTERVAL_MIN:-10}
exec 9>$S/watch.lock
flock -n 9 || { echo "watch.sh はもう動いている"; exit 1; }
say() { echo "$(date '+%F %T') $*" | tee -a $LOG; }
fp() { (cd $S/out 2>/dev/null && cat per_run.csv pairs.csv memory_bits_vs_errors.csv seal_states.csv effort.csv columns.csv 2>/dev/null) | sha256sum | cut -c1-16; }
say "始める（${INTERVAL_MIN} 分ごと、PUSH=${PUSH:-1}、REPLAY=${REPLAY:-0}）"
while true; do
  [ -e $S/STOP_WATCH ] && { say "STOP_WATCH があるので抜ける"; exit 0; }
  if [ "${REPLAY:-0}" = 1 ]; then
    # replay.py は自分の錠で一つしか動かない（動いていれば、すぐ抜ける）
    setsid nohup python3.12 $S/replay.py --wait --maxpar "${REPLAY_MAXPAR:-2}" >> $S/replay.log 2>&1 < /dev/null &
  fi
  nice -n 15 ionice -c3 python3.12 $S/surface.py --jobs "${JOBS:-4}" >> $LOG 2>&1 || say "★ surface.py が失敗（watch.log を見る）"
  now=$(fp); last=$(cat $S/.last_pushed 2>/dev/null)
  if [ "$now" != "$last" ]; then
    if [ "${PUSH:-1}" = 1 ]; then
      if bash $S/push_hook.sh >> $LOG 2>&1; then echo "$now" > $S/.last_pushed; say "表を push した（$now）"
      else say "★ push_hook.sh が失敗（次の回にやり直す）"; fi
    else
      say "表が変わった（PUSH=0 なので push しない）"
    fi
  fi
  sleep $((INTERVAL_MIN * 60))
done

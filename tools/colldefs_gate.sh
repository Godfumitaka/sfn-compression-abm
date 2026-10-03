#!/bin/bash
# 並列の上限（Codex と合わせて重い処理 4 まで）を守るための一時停止の係（2026-10-02 夜）。
# Codex の重い処理（v3_run.py）が 3 以上なら（こちらは 2 本）、こちらの selcands（主と子）を SIGSTOP、3 以下なら SIGCONT。止める（終わらせる）ことはしない。
LOG=$HOME/v310cprod/colldefs_gate.log
state=run
while ! grep -q CDDONE $HOME/v310cprod/colldefs_all.log; do
  # 数えるのは、Codex の作業場所で動く v3_run.py のうち、子を持たない（包みのシェルでない、実際に計算する）処理
  n=$(pgrep -f "tools/v3_run.py" | while read p; do [ -z "$(pgrep -P $p)" ] && lsof -a -p $p -d cwd -Fn 2>/dev/null | grep -q "Documents/ChatGPT" && echo $p; done | wc -l | tr -d ' ')
  mine=$(pgrep -f "tools/colldefs.py")
  kids=$(for m in $mine; do pgrep -P $m; done)
  if [ "$n" -ge 3 ]; then
    [ -n "$mine$kids" ] && kill -STOP $mine $kids 2>/dev/null
    [ $state = run ] && echo "$(date +%T) 一時停止（Codex の重い処理 $n）" >> $LOG; state=stop
  else
    [ -n "$mine$kids" ] && kill -CONT $mine $kids 2>/dev/null
    [ $state = stop ] && echo "$(date +%T) 再開（Codex の重い処理 $n）" >> $LOG; state=run
  fi
  sleep 10
done
echo "$(date +%T) 終わり" >> $LOG

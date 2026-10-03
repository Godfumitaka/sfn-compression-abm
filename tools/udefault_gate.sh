#!/bin/bash
# udefault.py の一時停止の係（2026-10-03）。重い処理の合計が 4 を超えれば udefault を止め、4 以下で再開する（止めて捨てることはしない）。
# 数えるもの：Codex の作業場所で動く v3_run.py のうち子を持たない処理、こちらの colldefs.py・collbundles.py の主（Python の本体で動くもの）、
#   udefault.py の計算する子（multiprocessing.spawn）。シェルのコマンド文字列や caffeinate・resource_tracker は数えない。
LOG=$HOME/v310cprod/udefault_gate.log
st=stop   # 始めは止まっている前提（4 以下なら再開を送る。動いている処理に送っても害は無い）
codex() { pgrep -f "tools/v3_run.py" | while read p; do [ -z "$(pgrep -P $p)" ] && lsof -a -p $p -d cwd -Fn 2>/dev/null | grep -q "Documents/ChatGPT" && echo $p; done | wc -l | tr -d ' '; }
while ! grep -q UDDONE $HOME/v310cprod/udefault_all.log 2>/dev/null; do
  mainud=$(pgrep -f "MacOS/Python tools/udefault.py")
  kids=$(for m in $mainud; do pgrep -P $m; done)
  ud=0
  for c in $kids; do ps -o command= -p $c | grep -q "multiprocessing.spawn" && ud=$((ud + 1)); done
  n=$(( $(codex) + $(pgrep -f "MacOS/Python tools/colldefs.py" | wc -l) + $(pgrep -f "MacOS/Python tools/collbundles.py" | wc -l) + ud ))
  if [ $n -gt 4 ] && [ $st = run ]; then kill -STOP $mainud $kids; st=stop; echo "$(date +%T) 一時停止（合計 $n）" >> $LOG
  elif [ $n -le 4 ] && [ $st = stop ]; then kill -CONT $mainud $kids; st=run; echo "$(date +%T) 再開（合計 $n）" >> $LOG; fi
  sleep 10
done

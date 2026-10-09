#!/bin/bash
# デスクトップの 3b の本の合計を 9 本までにする（前の台本の本と二つ目の台本の本を合わせて）。9 本以上なら STOP_DESKTOP2 を置き、9 本未満なら外す。1 分ごと。
W=$HOME/cloud/wave1
while pgrep -f "desktop_runner2.py" > /dev/null || [ -e $W/STOP_DESKTOP2 ]; do
  n=$(ps -eo args | grep "^python3.12 tools/v3_run.py" | grep -c "wave1_3b_")
  if [ $n -ge 9 ]; then touch $W/STOP_DESKTOP2; else rm -f $W/STOP_DESKTOP2; fi
  grep -q "全部終わった" $W/desktop_runner2.log 2>/dev/null && break
  sleep 60
done

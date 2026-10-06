#!/bin/bash
# 2 分ごとに 10 秒、Windows の論理 CPU ごとの使用率（% Processor Time）と性能（% Processor Performance）を記録する。読むだけ。
PS=$(wslpath -w $HOME/slow_2026-10-06/percore.ps1)
while true; do
  T=$(date '+%F %T')
  powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$PS" 2>/dev/null | tr -d '\r' | grep -v "^$" | sed "s/^/$T\t/" >> $HOME/slow_2026-10-06/win_percore.tsv
  sleep 110
done

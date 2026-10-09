#!/bin/bash
# 10/10 06:00 まで、15 分ごとに wave1_refresh.py を走らせる（指示 44 の準備）。06:00 を過ぎたら抜ける。
while [ "$(date +%s)" -lt "$(date -d '2026-10-10 06:00' +%s)" ]; do python3 $HOME/surface/wave1_refresh.py >> $HOME/surface/wave1_refresh.log 2>&1; sleep 900; done

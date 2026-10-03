#!/bin/bash
# 既定の答えの作業が終わってから、時間の幅の関門を始める（Codex の重い処理が 2 以下になるのを待つ）
until grep -q UDDONE $HOME/v310cprod/udefault_all.log; do sleep 30; done
codex() { pgrep -f "tools/v3_run.py" | while read p; do [ -z "$(pgrep -P $p)" ] && lsof -a -p $p -d cwd -Fn 2>/dev/null | grep -q "Documents/ChatGPT" && echo $p; done | wc -l | tr -d ' '; }
until [ "$(codex)" -le 2 ]; do sleep 60; done
echo "$(date +%T) 始める（Codex $(codex)）"
/Users/tatsu-admin/sfn/sfn-compression-abm-horizon/tools/horizon_gates.sh

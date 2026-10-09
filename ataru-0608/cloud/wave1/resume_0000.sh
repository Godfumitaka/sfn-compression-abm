#!/bin/bash
# 指示 50 の 3：2026-10-10 00:00（日本時間）に、ゲームの間に止めたデスクトップの本を再開する（game_mode.sh off＝SIGCONT、時刻は pause_log.tsv に書かれる）。
# あわせて、第 1 波の見え方を足す見張り（wave1_refresh_loop.sh）を始め直す。新しい本（指示 45・47）は、走行の係が列を書いてから始める（00:02 の確認の仕事）。
until [ "$(date +%s)" -ge "$(date -d '2026-10-10 00:00' +%s)" ]; do sleep 30; done
$HOME/game_mode.sh off >> $HOME/cloud/wave1/resume_0000.log 2>&1
tmux new-session -d -s wave1refresh "bash $HOME/surface/wave1_refresh_loop.sh"
echo "$(date '+%F %T') 再開した（game_mode.sh off、見え方の見張りを始め直した）" >> $HOME/cloud/wave1/resume_0000.log

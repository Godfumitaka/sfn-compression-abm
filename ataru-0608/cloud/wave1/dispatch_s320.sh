#!/bin/bash
# 指示 41 の 2・3：種 3〜20 の残りを、新しいオンデマンドの c7a.8xlarge に 28 本ずつ配る（s320_m1〜m5.json）。上限で断られたら、その台数を記録して止まる。
set -u; source $HOME/cloud/aws_env.sh; W=$HOME/cloud/wave1; LOG=$W/dispatch_s320.log; K=$KEY_FILE
say() { echo "$(date '+%F %T') $*" >> $LOG; }
for i in 1 2 3 4 5; do
  out=$(bash $HOME/cloud/aws_launch.sh c7a.8xlarge 120 2>&1); last=$(echo "$out" | tail -1)
  if ! [[ "$last" =~ ^i-[0-9a-f]+\ [0-9.]+$ ]]; then say "★ m$i を立てられなかった：$(echo "$out" | tail -3 | tr '\n' ' ')"; break; fi
  read MID MIP <<< "$last"; echo "$MID $MIP" > $W/machine_m$i; say "立てた m$i $MID $MIP"
  for t in $(seq 1 30); do ssh -n -i $K -o StrictHostKeyChecking=accept-new -o ConnectTimeout=10 ubuntu@$MIP true 2>/dev/null && break; sleep 10; done
  ( timeout 1500 bash $HOME/cloud/aws_ship.sh $MIP codex/attn-json-log-4cea-2026-10-09 c79215980a913cc426a63f25048e0dfc6fd1f758 jsonlog4cea > $W/ship_m${i}a.log 2>&1 < /dev/null && \
    timeout 1500 bash $HOME/cloud/aws_ship.sh $MIP codex/attn-json-log-e9-2026-10-09 c57467eab13ee9ef84277059024ab892756fd2f8 jsonloge9 > $W/ship_m${i}b.log 2>&1 < /dev/null && \
    ssh -n -i $K ubuntu@$MIP 'mkdir -p ~/wave1' && scp -q -r -i $K $W/configs35 $W/s320_m$i.json $W/wave1_start.py ubuntu@$MIP:~/wave1/ && \
    ssh -n -i $K ubuntu@$MIP "export PATH=\$HOME/.local/bin:\$PATH; python3.12 ~/wave1/wave1_start.py ~/wave1/s320_m$i.json" >> $LOG 2>&1 && say "m$i で 28 本を始めた" ) || say "★ m$i の準備か開始に失敗（$W/ship_m${i}*.log）" &
  sleep 5
done
wait; say "配り終えた"

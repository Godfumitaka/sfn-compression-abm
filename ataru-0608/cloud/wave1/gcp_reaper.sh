#!/bin/bash
# 指示 64 の 3：D・D＋注意の Google Cloud の機械を、走っている模型が無く、割り当てた本が全部持ち帰り済み（done.tsv に rc=0 か止まりの行がある）になったら消す。
# 関門の機械（sfn-coll-gate）は扱わない。10 分ごと。
GO="-i $HOME/.ssh/google_compute_engine -o UserKnownHostsFile=$HOME/.ssh/gcp_known_hosts -o ConnectTimeout=15"; W=$HOME/cloud/wave1; LOG=$W/gcp_reaper.log
declare -A IP=([g8]=34.57.154.198 [g4]=34.45.150.3 [g16a]=136.107.100.7 [g16b]=35.243.229.179)
declare -A NAME=([g8]=sfn-d-c3d8 [g4]=sfn-d-c3d4 [g16a]=sfn-d-c3d16a [g16b]=sfn-d-c3d16b)
declare -A ZONE=([g8]=us-central1-a [g4]=us-central1-a [g16a]=us-east4-a [g16b]=us-east1-b)
left=4
while [ $left -gt 0 ]; do
  left=0
  for m in g8 g4 g16a g16b; do
    [ -e $W/reaped_$m ] && continue
    left=$((left+1))
    grep -q "D 始めた\|100 本を全部始めた" $W/sched57.log || continue
    grep -q "100 本を全部始めた" $W/sched57.log || continue
    n=$(ssh -n $GO tatsu@${IP[$m]} 'ps -eo args | grep -c "^python3.12 tools/v3_run.py"' 2>/dev/null); [ "$n" == "0" ] || continue
    miss=$(python3 -c "import json;d=open('$W/done.tsv').read();print(sum(1 for c in json.load(open('$W/s57_$m.json')) if '\n'+c['name']+'\t' not in '\n'+d))")
    [ "$miss" == "0" ] || continue
    if gcloud compute instances delete ${NAME[$m]} --zone ${ZONE[$m]} --quiet > /dev/null 2>&1; then
      touch $W/reaped_$m; echo "$(date '+%F %T') 消した ${NAME[$m]}（Google Cloud）" | tee -a $LOG >> $HOME/cloud/instances.log
    fi
  done
  sleep 600
done

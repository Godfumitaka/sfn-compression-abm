#!/bin/bash
# 指示 41：上限（vCPU 192）で m5 の機械が立たなかったので、残りの 14 本（s320_m5.json）を、m3 の 2b の 10 本が終わって芯が空いたら m3 で始める。
set -u; source $HOME/cloud/aws_env.sh; W=$HOME/cloud/wave1; read MID MIP < $W/machine_m3
until [ "$(ssh -n -i $KEY_FILE ubuntu@$MIP 'ps -eo args | grep -c "^python3.12 tools/v3_run.py"')" -le 18 ]; do sleep 120; done
scp -q -i $KEY_FILE $W/s320_m5.json ubuntu@$MIP:~/wave1/ && ssh -n -i $KEY_FILE ubuntu@$MIP 'export PATH=$HOME/.local/bin:$PATH; python3.12 ~/wave1/wave1_start.py ~/wave1/s320_m5.json' >> $W/dispatch_s320.log 2>&1 && echo "$(date '+%F %T') m5 の 14 本を m3 で始めた" >> $W/dispatch_s320.log

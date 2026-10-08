#!/bin/bash
# クラウドの機械の上で、割り当てられた第 1 波の本を一本 1 芯で始める。引数：命令の JSON、作業場所の名前、行の番号
# 出力先は命令の出力先の「/home/tatsu/…」部分を、この機械の ~/cloud_runs/wave1/<行>/ に置き換える。setsid、time -v、PYTHONHASHSEED=0、LANG・LC_* を外す。
set -u
J=$1; WT=$2; ROW=$3; SRC=$HOME/sfn/audit/_read/$WT
N=$(python3 -c "import json;print(len(json.load(open('$J'))))")
for i in $(seq 0 $((N-1))); do
  read -r ARM SEED < <(python3 -c "import json;x=json.load(open('$J'))[$i];print(x['arm'],x['seed'])")
  D=$HOME/cloud_runs/wave1/$ROW/$ARM/seed$(printf %03d $SEED); [ -e $D/output ] && continue; mkdir -p $D
  python3 - "$J" "$i" "$D" <<'PY'
import json, sys
x = json.load(open(sys.argv[1]))[int(sys.argv[2])]; D = sys.argv[3]
c = list(x["command"]); c[3] = D + "/output"
json.dump(c, open(D + "/native_command.json", "w"), ensure_ascii=False, indent=1)
PY
  CMD=$(python3 -c "import json,shlex;print(shlex.join(json.load(open('$D/native_command.json'))))")
  echo "cd $SRC && env -u LC_ALL -u LANG -u LC_CTYPE PYTHONHASHSEED=0 /usr/bin/time -v $CMD > $D/run.log 2> $D/time.log; echo rc=\$? >> $D/run.log" > $D/run.sh
  setsid nohup bash $D/run.sh < /dev/null > /dev/null 2>&1 &
  echo "$(date '+%F %T') 始めた $ARM 種 $SEED"
  sleep 2
done

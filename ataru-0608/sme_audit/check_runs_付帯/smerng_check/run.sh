#!/bin/bash
# 6e93e0b で、本番の w2_A_L50・種 1 と同じ命令・同じ環境（出力先だけ別）
cd $HOME/sfn/audit/_read/smerng
CMD=$(python3 -c "import json,shlex;print(shlex.join(json.load(open('$HOME/smerng_check/command.json'))['command']))")
env -u LC_CTYPE -u LC_ALL -u LANG PYTHONHASHSEED=0 bash -c "/usr/bin/time -v $CMD" > $HOME/smerng_check/run.log 2>&1
echo "== 終わり $(date +%T)" >> $HOME/smerng_check/run.log

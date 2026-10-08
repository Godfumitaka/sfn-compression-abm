#!/bin/bash
# 較正の走らせ直し（受け箱の指示 19 の 4）：32 芯の機械の上で、13 本を一本 1 芯で並べる。命令は今の較正と同じ（run_calib.sh）、出力先だけが違う。
# 世界 1 の種 41〜48、世界 2 の種 43・45〜48（マックの種 41・42・44 以外）。
set -euo pipefail; HERE=$(cd "$(dirname "$0")" && pwd)
for s in 41 42 43 44 45 46 47 48; do bash $HERE/run_calib.sh 1 $s $HOME/cloud_runs/calib; sleep 2; done
for s in 43 45 46 47 48; do bash $HERE/run_calib.sh 2 $s $HOME/cloud_runs/calib; sleep 2; done

#!/bin/bash
# 最初に、デスクトップの走行と 200 試行の全バイト一致を確かめる（D: の対と同じ比べ方：台帳の見出し一行と時間の欄を除く）。
# デスクトップの基準の一覧：ataru-0608/cloud/ref200_desktop_wsl.tsv（世界 1・種 41・試行 200、デスクトップの WSL の中で走らせた本）。
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd); ROOT=$HOME/cloud_runs/verify200
bash $HERE/run_calib.sh 1 41 $ROOT 200
D=$ROOT/w1_seed041
until grep -q "^rc=" $D/run.log 2>/dev/null; do sleep 60; done
grep -q "^rc=0" $D/run.log || { echo "★ 走行が失敗した（$D/run.log）"; exit 3; }
python3 $HERE/norm_hash.py $D/output $D/norm_hash.tsv
python3 $HERE/norm_hash.py --compare $HERE/ref200_desktop_wsl.tsv $D/norm_hash.tsv && echo "一致：デスクトップと同じ（時間の欄を除く）" || { echo "★ 一致しない。第 1 波は始めない"; exit 4; }
grep -E "Elapsed|User time|Maximum resident" $D/time.log

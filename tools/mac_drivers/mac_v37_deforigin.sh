#!/bin/bash
# v3.7 のマックの腕に、デスクトップの道具 tools/def_origin.py（af40142 の写し、作業場所 sfn-compression-abm-v37mac2 ＝ 73a16ea）をかけて上げる見張り。
# 並びの台本（tools/mac_v37_0928.sh）は止めない。腕ごとに、その腕の control/ の短い報告が上がったあと（結果の作業場所の git が空いてから）かける。
set -u
W=/Users/tatsu-admin/sfn/sfn-compression-abm-v37mac2
OUT=$HOME/v37prod; RES=$HOME/v33prod/results; LOG=$OUT/mac_v37.log
say() { echo "$(date '+%F %T') $*" | tee -a "$LOG"; }
while IFS=$'\t' read -r -u 3 mach arm rest; do
  [[ -z "$mach" || "$mach" == \#* ]] && continue
  until grep -qE "control/.*_v3.7_${arm}_マック.md を上げ" "$LOG"; do sleep 60; done
  (cd $W && python3.12 tools/def_origin.py $OUT/$arm $arm $RES mac) >> "$LOG" 2>&1 && say "腕 $arm に定義の生まれと型またぎ（def_origin）を足して上げた" || say "★ 腕 $arm の def_origin が失敗（$LOG）"
done 3< "$W/tools/prod_v37_mac_arms.tsv"
say "DEFORIGINDONE"

#!/bin/bash
# 2026-09-28 夕の判断「v3.7 を止める」：走っている腕（v37new_n70_f00）の区切りで止める。台帳は消さない。
# 並びの見張り（mac_v37_0928.sh）の本体と、def_origin の見張りを止め、走っている腕の台本は走り終えさせる。終わったら、その腕に
# 数え（v37_arm_counts）→ control/ の短い報告 → def_origin をかけ、止めた状態を書く。
set -u
W=/Users/tatsu-admin/sfn/sfn-compression-abm-v37mac; W2=/Users/tatsu-admin/sfn/sfn-compression-abm-v37mac2
OUT=$HOME/v37prod; RES=$HOME/v33prod/results; LOG=$OUT/mac_v37.log
CUR=v37new_n70_f00; MAINPID=${MAINPID:?}; SIDEPID=${SIDEPID:?}; RUNPID=${RUNPID:?}
say() { echo "$(date '+%F %T') $*" | tee -a "$LOG"; }
say "v3.7 を止める（2026-09-28 夕の判断）：見張りの本体（$MAINPID）と def_origin の見張り（$SIDEPID）を止め、走っている腕 $CUR（台本 $RUNPID）は走り終えさせる"
kill -TERM $MAINPID $SIDEPID 2>/dev/null
while kill -0 $RUNPID 2>/dev/null; do sleep 30; done
say "腕 $CUR の台本が終わった"
S1=$( (cd $W && python3.12 tools/v37_arm_counts.py $OUT/$CUR $CUR 4) 2>>"$LOG" | tail -1 ); say "数え：$S1"
F="$(date +%Y-%m-%d_%H%M)_v3.7_${CUR}_マック.md"
printf '# v3.7 の腕 %s（マックの Code、%s）　判断しない\n\n- 結果：results-2026-09-27 の mac/%s/。台帳は ~/v37prod/%s に全部残した。\n- 数え（tools/v37_arm_counts.py）：%s\n- v3.7 はこの腕の区切りで止めた（2026-09-28 夕の判断）。\n' "$CUR" "$(date '+%F %T')" "$CUR" "$CUR" "$S1" > "$RES/control/$F"
( cd $RES && git add "control/$F" && git commit -q -m "control：$F" && for i in 1 2 3 4 5 6; do git push -q origin HEAD:results-2026-09-27 2>/dev/null && break; git pull -q --rebase origin results-2026-09-27 || git rebase --abort; sleep 10; done ) && say "control/$F を上げた"
echo "control/$F" >> $HOME/v33prod/audit_seen.txt
(cd $W2 && python3.12 tools/def_origin.py $OUT/$CUR $CUR $RES mac) >> "$LOG" 2>&1 && say "腕 $CUR に def_origin を足して上げた" || say "★ 腕 $CUR の def_origin が失敗"
say "V37STOPPED（v3.7 はここで止めた。次の腕は始めない）"

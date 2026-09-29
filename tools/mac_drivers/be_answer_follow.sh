#!/bin/bash
# B＋E の残りの腕（L90・L1・L50_Uabs）が終わるたびに（mac_be.log の「一行を上げた」）、答えの出どころ × 当たり外れ × 生まれた型を数え、
# control/2026-09-29_BE_答えの出どころと当たり外れ_マック.md の表を作り直して上げる（数えるだけ。走行は触らない）。
set -u
unset LC_CTYPE LC_ALL LANG
W=/Users/tatsu-admin/sfn/sfn-compression-abm-v310mac; cd $W
P=$HOME/v310prod; A=$P/answer_src; RES=$HOME/v33prod/results; LOG=$A/follow.log
F="control/2026-09-29_BE_答えの出どころと当たり外れ_マック.md"
for ARM in v310BE_L90 v310BE_L1 v310BE_L50_Uabs; do
  until grep -q "腕 $ARM の一行を上げた\|腕 $ARM の一行を上げられなかった\|腕 $ARM の B＋E の要約が失敗" $P/mac_be.log 2>/dev/null; do sleep 60; done
  echo "$(date '+%F %T') $ARM を数える" >> $LOG
  python3.12 tools/v39_miss_source.py $A/$ARM.json $P/$ARM >> $LOG 2>&1 || { echo "★ $ARM を数えられなかった" >> $LOG; continue; }
  JS="$A/four.json"; for x in v310BE_L90 v310BE_L1 v310BE_L50_Uabs; do [[ -s $A/$x.json ]] && JS="$JS $A/$x.json"; done
  python3.12 tools/v310be_answer_table.py $A/tables.md $JS >> $LOG 2>&1
  ( cd $RES && git pull -q --rebase origin results-2026-09-27 \
    && python3.12 - "$F" "$A/tables.md" "$(date +%H:%M)" "$ARM" <<'PY'
import sys, pathlib, re
f, t, hm, arm = sys.argv[1:5]
p = pathlib.Path(f); s = p.read_text(encoding="utf-8")
head = s[:s.index("### ")]
head = re.sub(r"（マックの Code、[^）]*）", lambda m: m.group(0)[:-1] + f"・{hm} に {arm.replace('v310BE_', '')}）", head, count=1)
p.write_text(head + pathlib.Path(t).read_text(encoding="utf-8"), encoding="utf-8")
PY
    git add "$F" && git commit -q -m "control：B＋E の答えの出どころと当たり外れに $ARM を足す（マック）" \
    && for i in 1 2 3 4 5; do git push -q origin HEAD:results-2026-09-27 2>/dev/null && break; git pull -q --rebase origin results-2026-09-27 || { git rebase --abort; break; }; sleep 5; done \
    && git fetch -q origin results-2026-09-27 && git diff --quiet origin/results-2026-09-27 -- "$F" ) >> $LOG 2>&1 \
    && echo "$(date '+%F %T') $ARM を足して上げた" >> $LOG || echo "$(date '+%F %T') ★ $ARM を上げられなかった" >> $LOG
done
echo "$(date '+%F %T') FOLLOWDONE" >> $LOG

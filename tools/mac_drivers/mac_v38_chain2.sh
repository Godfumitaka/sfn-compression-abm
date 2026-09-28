#!/bin/bash
# 2026-09-29 0 時ごろの追記：数えの作業（tools/miss_anatomy.py）と前の台本（tools/mac_drivers/mac_v38_chain.sh）が終わってから、続けて流す。
#   v38new_n40_f10 → v38new_n40_f00 → v38new_n40_f025（各 80 本、並列 6、台帳は全部残す）。解析と上げは tools/prod_v38.sh の中。
#   腕ごとに、tools/spoken_by_birthtype.py の数えを control/ に一行で書く。上げに失敗したら、ログに書いて次へ進む。
#   始める前に「空き − 5 GB ＜ 30 GB」なら、そこで止めてログに書く。
# 端末から切り離して走らせる（tools/mac_drivers/launch_detached.py）。ログ：~/v38prod/mac_v38.log の [chain2] の行。
set -u
unset LC_CTYPE LC_ALL LANG   # ★ bash 3.2 の読み違いを避ける（mac_v38_chain.sh と同じ）
W=/Users/tatsu-admin/sfn/sfn-compression-abm-v38mac4
OUT=$HOME/v38prod; RES=$HOME/v33prod/results; LOG=$OUT/mac_v38.log
WAITPID=${WAITPID:-}; ANATLOG=${ANATLOG:-}
say() { echo "$(date '+%F %T') [chain2] $*" >> "$LOG"; }
freegb() { df -Pk "$OUT" | awk 'NR==2 {printf "%d", $4/1048576}'; }
say "待つ：前の台本（${WAITPID:-無し}）と数えの作業（${ANATLOG:-無し} の DONE）"
if [[ -n "$WAITPID" ]]; then while kill -0 $WAITPID 2>/dev/null; do sleep 60; done; fi
if [[ -n "$ANATLOG" ]]; then until grep -q DONE "$ANATLOG" 2>/dev/null; do sleep 60; done; fi
say "待ち終わり。NSIM 0.4 の f の三つの腕を始める"
for arm in v38new_n40_f10 v38new_n40_f00 v38new_n40_f025; do
  if (( $(freegb) - 5 < 30 )); then say "★ 空き $(freegb) GB − 見込み 5 GB が 30 GB を切るので、ここで止める（$arm は始めない）"; break; fi
  say "腕 $arm を始める（並列 6、空き $(freegb) GB）"
  n0=$(wc -l < $OUT/prod_v38.log 2>/dev/null || echo 0)
  (cd $W && MACHINE=mac JOBS=6 MINFREE_GB=30 SEEDS_LIMIT=0 OUT=$OUT HOST=mac RESULTS=$RES PY=python3.12 ARMSF=tools/prod_v38_mac_arms.tsv ONLY=$arm caffeinate -i -s bash tools/prod_v38.sh >> $OUT/prod_v38_stdout.log 2>&1)
  say "腕 $arm の台本が終わった rc=$?"
  tail -n +$((n0+1)) $OUT/prod_v38.log | grep -q "腕 $arm が results-2026-09-27 に上がっていることを確かめた" || say "★ 腕 $arm の上げが確かめられていない（prod_v38.log を見る）。次へ進む"
  J=$( (cd $W && python3.12 tools/spoken_by_birthtype.py $OUT/$arm $arm 4) 2>>"$LOG" | tail -1 )
  L=$(python3.12 - "$J" <<'P' 2>>"$LOG"
import json,sys
try: d=json.loads(sys.argv[1])
except Exception as e: print("数えが無い", e); sys.exit()
g=d.get
print(f"実際の発話 {g('発話',0):,}（外れ {g('外れ',0):,}）・違う型で生まれた定義が話した外れ {g('外れ_違う型で生まれた定義',0):,}・開示を受けた外れ {g('外れ_開示あり',0):,}・"
      f"そのあと同じ定義が同じ型で話した発話 当たり {g('その後の発話_当たり',0):,}・外れ {g('その後の発話_外れ',0):,}"
      f"（次の一回：当たり {g('その次の発話_当たり',0):,}・外れ {g('その次の発話_外れ',0):,}）")
P
)
  say "$arm：$L"
  F="$(date +%Y-%m-%d_%H%M)_v3.8_${arm}_マック.md"
  printf '%s\n' "- $arm（v3.8、NSIM 0.4、80 本、$(date '+%F %T')、台本 tools/mac_drivers/mac_v38_chain2.sh・数え tools/spoken_by_birthtype.py）：$L" > "$RES/control/$F"
  ( cd $RES && git add "control/$F" && git commit -q -m "control：$F" && for i in 1 2 3 4 5 6; do git push -q origin HEAD:results-2026-09-27 2>/dev/null && break; git pull -q --rebase origin results-2026-09-27 || git rebase --abort; sleep 10; done
    git fetch -q origin results-2026-09-27 && git diff --quiet origin/results-2026-09-27 -- "control/$F" ) >> "$LOG" 2>&1 && say "control/$F を上げた（確かめ済み）" || say "★ control/$F を上げられなかった（次へ進む）"
done
say "CHAIN2DONE"

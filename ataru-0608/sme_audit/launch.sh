#!/bin/bash
# SME 版の本番（全部の 160 本）。2026-10-03 夜の委任書と追記。
# 始める条件：点検 1〜8 が全部通った（~/smeprod/点検通過 を走行の係が置く）と、U の走行が全部終わった（~/uabs/chain.log の「全部終わり」）。
# 条件（腕）ごとに、元の台本 run_after_audit.py（変えていない）を、その条件の 20 本だけの命令の写しで呼ぶ。並列 4。
# 各条件の前に C: の空きを確かめ、20GB を切っていたら新しい条件を始めずに止める（追記 1）。
set -u
P=$HOME/smeprod; LOG=$P/launch.log; RES=$HOME/v33prod/results; CTRL="control/2026-10-03_SME版の独立点検_走行の係.md"
SRC=$HOME/sfn/audit/_read/sme
say() { echo "$(date '+%F %T') $*" >> $LOG; }
cfree() { df -BG /mnt/c | awk 'NR==2 {gsub("G","",$4); print $4}'; }
used() { df -B1 / | awk 'NR==2 {print $3}'; }
ctl() { ( cd $RES && git pull -q --rebase origin results-2026-09-27; echo "$1" >> "$CTRL"; git add "$CTRL" && git commit -q -m "SME 版の本番の進み（走行の係）

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>" && for i in 1 2 3 4 5; do git push -q origin HEAD:results-2026-09-27 2>/dev/null && break; git pull -q --rebase origin results-2026-09-27 || git rebase --abort; sleep 5; done ) >> $LOG 2>&1; }
until [ -f $P/点検通過 ] && grep -q "全部終わり" $HOME/uabs/chain.log; do sleep 60; done
[ "$(git -C $SRC rev-parse HEAD)" == "bdaa110097395f97fa920461ba96a61843a2b73b" ] && [ -z "$(git -C $SRC status --short)" ] || { say "★ 土台が bdaa110 のままでない"; exit 2; }
say "始める（土台 bdaa110、並列 4、C: $(cfree)GB、使用量 $(used)）"
ctl "- $(date '+%H:%M') 本番を始めた（全部の 160 本、土台 bdaa110、条件の順 w2_A_L50→w1_A_L50→w2_D_tau04→w1_D_tau04→w2_C_L50→w2_A_zero→w1_C_L50→w1_A_zero、並列 4）。C: の空き $(cfree)GB、WSL の使用量 $(used) B。"
for ARM in w2_A_L50 w1_A_L50 w2_D_tau04 w1_D_tau04 w2_C_L50 w2_A_zero w1_C_L50 w1_A_zero; do
  c=$(cfree)
  if (( c < 20 )); then say "★ C: の空き ${c}GB、$ARM の前で止める"; ctl "- $(date '+%H:%M') ★ C: の空き ${c}GB（20GB 未満）。条件 $ARM の前で止めた。"; exit 3; fi
  D=$P/plan_$ARM; mkdir -p $D; cp $P/plan/run_after_audit.py $D/
  python3 -c "
import json; c=json.load(open('$P/plan/sme.commands.json')); json.dump([x for x in c if x['arm']=='$ARM'],open('$D/sme.commands.json','w'),ensure_ascii=False,indent=2)"
  say "条件 $ARM を始める（C: ${c}GB）"
  python3.12 $D/run_after_audit.py --source $SRC --workers 4 >> $P/run_$ARM.out 2>&1
  rc=$?; n=$(ls $P/sme/$ARM/*/ledgers/cells/*/seed*.done 2>/dev/null | wc -l)
  say "条件 $ARM 終わり rc=$rc 完走 $n"
  ctl "- $(date '+%H:%M') 条件 $ARM：完走 $n／20、rc=$rc。C: の空き $(cfree)GB、WSL の使用量 $(used) B。"
  [ $rc == 0 ] || { say "★ 条件 $ARM で台本が止まった"; ctl "- ★ 条件 $ARM で台本が止まった（rc=$rc、~/smeprod/run_$ARM.out）。新しい条件を始めない。"; exit 4; }
done
ctl "- $(date '+%H:%M') 本番の 160 本が走り終わった（仮の結果）。"
say "全部終わり"

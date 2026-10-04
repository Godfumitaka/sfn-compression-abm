#!/bin/bash
# SME 版の本番の続き（2026-10-04 の委任書「速くした版へ切り替える確かめ」の段 3）。
# まだ始まっていない本を 869a249（~/sfn/audit/_read/smefast）で走らせる。走っている本・終わった本はそのまま（bdaa110）。
# 元の台本 run_after_audit.py（変えていない）を、一本ずつの命令の写し（出力先と旗は ~/smeprod/plan/sme.commands.json のまま）で呼ぶ。
# 同時に走る本数（bdaa110 で走っている本を含む）は 4 本まで。メモリの空きが 6GiB 未満なら次の本を待つ。
# 条件の区切りで C: の空きを確かめ、20GB を切っていたら次の条件を始めずに止める。
set -u
P=$HOME/smeprod; LOG=$P/launch2.log; RES=$HOME/v33prod/results; CTRL="control/2026-10-03_SME版の独立点検_走行の係.md"
SRC=$HOME/sfn/audit/_read/smefast; VER=$P/版の一覧.tsv
say() { echo "$(date '+%F %T') $*" >> $LOG; }
cfree() { df -BG /mnt/c | awk 'NR==2 {gsub("G","",$4); print $4}'; }
used() { df -B1 / | awk 'NR==2 {print $3}'; }
memfree() { free -g | awk '/^Mem:/ {print $7}'; }
running() { ps -eo args | grep "tools/v3_run.py" | grep -c "/home/tatsu/smeprod/sme/"; }
ctl() { ( cd $RES && git pull -q --rebase origin results-2026-09-27; echo "$1" >> "$CTRL"; git add "$CTRL" && git commit -q -m "SME 版の本番の進み（走行の係）

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>" && for i in 1 2 3 4 5; do git push -q origin HEAD:results-2026-09-27 2>/dev/null && break; git pull -q --rebase origin results-2026-09-27 || git rebase --abort; sleep 5; done ) >> $LOG 2>&1; }
[ "$(git -C $SRC rev-parse HEAD)" == "869a2496dbe2ab0963ce7eaf3560719af58cd263" ] && [ -z "$(git -C $SRC status --short)" ] || { say "★ 869a249 の作業場所が元のままでない"; exit 2; }
python3 - <<'PY' > $P/残り.tsv
import json, os
for c in json.load(open("/home/tatsu/smeprod/plan/sme.commands.json")):
    if not os.path.exists(c["command"][3]):
        print(f"{c['arm']}\t{c['seed']}")
PY
say "始める（869a249、残り $(wc -l < $P/残り.tsv) 本、C: $(cfree)GB、走っている本 $(running)）"
prev=""
while IFS=$'\t' read -r ARM SEED; do
  if [[ $ARM != "$prev" ]]; then
    if [[ -n $prev ]]; then ctl "- $(date '+%H:%M') 条件 $prev の本をすべて始めた（区切り）。C: の空き $(cfree)GB、WSL の使用量 $(used) B。"; fi
    c=$(cfree)
    if (( c < 20 )); then say "★ C: の空き ${c}GB、$ARM の前で止める"; ctl "- $(date '+%H:%M') ★ C: の空き ${c}GB（20GB 未満）。条件 $ARM の前で止めた。"; exit 3; fi
    prev=$ARM
  fi
  while (( $(running) >= 4 )) || (( $(memfree) < 6 )); do sleep 30; done
  S=$(printf %03d $SEED); D=$P/plan1/${ARM}_seed$S; mkdir -p $D; cp $P/plan/run_after_audit.py $D/
  python3 -c "
import json; c=json.load(open('$P/plan/sme.commands.json')); json.dump([x for x in c if x['arm']=='$ARM' and x['seed']==$SEED],open('$D/sme.commands.json','w'),ensure_ascii=False,indent=2)"
  echo -e "$ARM\t$SEED\t869a249\t$(date '+%F %T')" >> $VER
  say "始める $ARM 種 $SEED（走っている本 $(running)、メモリの空き $(memfree)GiB）"
  ( python3.12 $D/run_after_audit.py --source $SRC --workers 1 > $D/runner.out 2>&1; echo "rc=$?" >> $D/runner.out ) &
  sleep 20
done < $P/残り.tsv
wait
ctl "- $(date '+%H:%M') 本番の 160 本が走り終わった（仮の結果）。C: の空き $(cfree)GB。"
say "全部終わり"

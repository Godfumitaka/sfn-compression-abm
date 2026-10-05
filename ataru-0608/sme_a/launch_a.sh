#!/bin/bash
# SME 版の本番、同点規則 (a)（858f708、--sme-call-seed --sme-tie-uniform）。2026-10-05 夜の依頼。
# 8 条件 × 種 1〜20 を ~/smeprod_a/plan/sme.commands.json の順に走らせる。保持 C の条件の前では、走行の係が C の確かめを済ませるまで待つ（~/smeprod_a/C許可）。
# 元の台本 run_after_audit.py（変えていない）を一本ずつの命令の写しで呼ぶ。各本は setsid で、この台本のセッションから切り離して始める
#   （この台本や tmux を止めても、走っている本は止まらない）。
# 同時の本数：8 本まで。新しい本を始めてもメモリの空きが 4GiB 以上残るときだけ始める：
#   空き（MemAvailable）−（新しい本の最大 2.5GiB）−（走っている各本の「その版の最大 − 今の使用」の和）≥ 4GiB。
#   版の最大：858f708 は 7.7GiB（マックの全走行の実測）。
# 条件の区切りで C: の空きを確かめ、20GB を切っていたら次の条件を始めずに止める。
set -u
P=$HOME/smeprod_a; LOG=$P/launch_a.log; RES=$HOME/v33prod/results; CTRL="control/2026-10-05_デスクトップ_(a)版の本番_走行の係.md"
SRC=$HOME/sfn/audit/_read/smetie; VER=$P/版の一覧.tsv
say() { echo "$(date '+%F %T') $*" >> $LOG; }
cfree() { df -BG /mnt/c | awk 'NR==2 {gsub("G","",$4); print $4}'; }
used() { df -B1 / | awk 'NR==2 {print $3}'; }
running() { ps -eo args | awk '$2=="tools/v3_run.py"' | grep -c "/home/tatsu/smeprod_a/sme/"; }
room() { python3 $P/memroom.py; }
ctl() { ( cd $RES && git pull -q --rebase origin results-2026-09-27; echo "$1" >> "$CTRL"; git add "$CTRL" && git commit -q -m "SME 版の本番の進み（走行の係）

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>" && for i in 1 2 3 4 5; do git push -q origin HEAD:results-2026-09-27 2>/dev/null && break; git pull -q --rebase origin results-2026-09-27 || git rebase --abort; sleep 5; done ) >> $LOG 2>&1; }
[ "$(git -C $SRC rev-parse HEAD)" == "$(git -C $HOME/sfn/sfn-compression-abm rev-parse 858f708)" ] && [ -z "$(git -C $SRC status --short)" ] || { say "★ 858f708 の作業場所が元のままでない"; exit 2; }
python3 - <<'PY' > $P/残り.tsv
import json, os
for c in json.load(open("/home/tatsu/smeprod_a/plan/sme.commands.json")):
    if not os.path.exists(c["command"][3]):
        print(f"{c['arm']}\t{c['seed']}")
PY
say "始める（858f708、残り $(wc -l < $P/残り.tsv) 本、C: $(cfree)GB、走っている本 $(running)）"
prev=""
while IFS=$'\t' read -r ARM SEED; do
  if [[ $ARM != "$prev" ]]; then
    if [[ -n $prev ]]; then ctl "- $(date '+%H:%M') 条件 $prev の本をすべて始めた（区切り）。C: の空き $(cfree)GB、WSL の使用量 $(used) B、走っている本 $(running)。"; fi
    c=$(cfree)
    if (( c < 20 )); then say "★ C: の空き ${c}GB、$ARM の前で止める"; ctl "- $(date '+%H:%M') ★ C: の空き ${c}GB（20GB 未満）。条件 $ARM の前で止めた。"; exit 3; fi
    if [[ $ARM == *_C_* ]] && [ ! -f $P/C許可 ]; then
      say "保持 C の条件 $ARM の前で、C の確かめを待つ"; ctl "- $(date '+%H:%M') 保持 C の条件の前で止まって待っている（control/2026-10-04_SME鍵の計算の高速化_Codex.md の「(a)：C_on」の確かめを走行の係が済ませるまで）。"
      until [ -f $P/C許可 ]; do sleep 60; done
      say "C の確かめが済んだので続ける"
    fi
    prev=$ARM
  fi
  while (( $(running) >= 8 )) || [[ $(room) != ok ]]; do sleep 30; done
  S=$(printf %03d $SEED); D=$P/plan1/${ARM}_seed$S; mkdir -p $D; cp $P/plan/run_after_audit.py $D/
  python3 -c "
import json; c=json.load(open('$P/plan/sme.commands.json')); json.dump([x for x in c if x['arm']=='$ARM' and x['seed']==$SEED],open('$D/sme.commands.json','w'),ensure_ascii=False,indent=2)"
  echo -e "$ARM\t$SEED\t858f708\t$(date '+%F %T')" >> $VER
  say "始める $ARM 種 $SEED（走っている本 $(running)、$(python3 $P/memroom.py --show)）"
  setsid bash -c "python3.12 $D/run_after_audit.py --source $SRC --workers 1 > $D/runner.out 2>&1; echo rc=\$? >> $D/runner.out" < /dev/null > /dev/null 2>&1 &
  sleep 30
done < $P/残り.tsv
while (( $(running) > 0 )); do sleep 60; done
ctl "- $(date '+%H:%M') 本番の 160 本が走り終わった（仮の結果）。C: の空き $(cfree)GB。"
say "全部終わり"

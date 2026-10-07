#!/bin/bash
# 走行の列の一行を走らせる（build_commands.py で作った JSON を使う）。2026-10-07、受け箱の指示 1 (2) の準備。
# 使い方：launch_row.sh <行の JSON> <版の作業場所（その commit を detach で取り出したもの）>   （tmux の中で）
# - 元の台本 run_after_audit.py（変えていない、~/smeprod_a/plan/run_after_audit.py の写し）を一本ずつ呼ぶ。各本は setsid で切り離す。
# - 同時の本数：~/queue/MAXRUN の数（無ければ 8）まで。毎回読み直すので、走りながら 12 まで上げられる。
#   新しい本の最大は ~/queue/NEWPEAK_GIB（無ければ 2.0）。全部の v3_run.py の「最大 − 今」と合わせて、空き 4GiB を残すときだけ始める。
# - 一本を始めるたびに C: の空きを確かめ、20GB を切っていたら新しい本を始めずに止まって受け箱・報告に書く。
# - 走っている本は止めない。消さない。
set -u
J=$1; SRC=$2; Q=$HOME/queue
NUM=$(python3 -c "import json;print(json.load(open('$J'))['row'])"); COMMIT=$(python3 -c "import json;print(json.load(open('$J'))['commit'])")
LOG=$Q/row$NUM.log; VER=$Q/版の一覧.tsv; PL=$Q/plan_row$NUM
say() { echo "$(date '+%F %T') $*" >> $LOG; }
cfree() { df -BG /mnt/c | awk 'NR==2 {gsub("G","",$4); print $4}'; }
running() { ps -eo args | awk '$2=="tools/v3_run.py"' | wc -l; }
maxrun() { cat $Q/MAXRUN 2>/dev/null || echo 8; }
room() { python3 $Q/memroom_any.py "$(cat $Q/NEWPEAK_GIB 2>/dev/null || echo 2.0)"; }
[ "$(git -C $SRC rev-parse HEAD)" == "$(git -C $HOME/sfn/sfn-compression-abm rev-parse $COMMIT)" ] && [ -z "$(git -C $SRC status --short)" ] || { say "★ $COMMIT の作業場所が元のままでない"; exit 2; }
[ -f $VER ] || echo -e "row\tarm\tseed\t版\t始めた" > $VER
N=$(python3 -c "import json;print(len(json.load(open('$J'))['plan']))")
say "始める：行 #$NUM、$N 本、版 $COMMIT、C: $(cfree)GB、走っている本 $(running)"
for i in $(seq 0 $((N-1))); do
  read -r ARM SEED OUT < <(python3 -c "import json;x=json.load(open('$J'))['plan'][$i];print(x['arm'],x['seed'],x['command'][3])")
  [ -e "$OUT" ] && { say "既にある出力なので飛ばす：$OUT"; continue; }
  while (( $(running) >= $(maxrun) )) || [[ $(room) != ok ]]; do sleep 30; done
  c=$(cfree); if (( c < 20 )); then say "★ C: の空き ${c}GB（20GB 未満）。$ARM 種 $SEED の前で止める"; exit 3; fi
  D=$PL/${ARM}_seed$(printf %03d $SEED); mkdir -p $D; cp $HOME/smeprod_a/plan/run_after_audit.py $D/
  python3 -c "import json;x=json.load(open('$J'))['plan'][$i];json.dump([x],open('$D/sme.commands.json','w'),ensure_ascii=False,indent=2)"
  echo -e "$NUM\t$ARM\t$SEED\t$COMMIT\t$(date '+%F %T')" >> $VER
  say "始める $ARM 種 $SEED（走っている本 $(running)、上限 $(maxrun)）"
  setsid bash -c "python3.12 $D/run_after_audit.py --source $SRC --workers 1 > $D/runner.out 2>&1; echo rc=\$? >> $D/runner.out" < /dev/null > /dev/null 2>&1 &
  sleep 20
done
say "行 #$NUM の本をすべて始めた。終わるのを待つ"
while ps -eo args | awk '$2=="tools/v3_run.py"' | grep -q "$(python3 -c "import json;print(json.load(open('$J'))['plan'][0]['command'][3].rsplit('/',2)[0])")/"; do sleep 60; done
FAIL=$(grep -L "^rc=0" $PL/*/runner.out 2>/dev/null | wc -l)
say "行 #$NUM の本がすべて終わった（rc が 0 でない本 $FAIL）"

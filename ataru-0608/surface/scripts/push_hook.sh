#!/bin/bash
# 表層の解析の表を results の枝へ push する（watch.sh が、表が変わったときに呼ぶ）。走行の係が中身を見てから使う。
#   ~/surface/out/ の表と meta.json を ~/v33prod/results/ataru-0608/surface/ に、道具の写しを その scripts/ に置き、
#   その場所だけを commit して、pull --rebase（--autostash）してから push する。衝突したら 5 回までやり直す。
set -u
RES=$HOME/v33prod/results; BR=results-2026-09-27; REL=ataru-0608/surface; DEST=$RES/$REL; S=$HOME/surface
TRAILER="Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
[ "$(git -C $RES branch --show-current)" = "$BR" ] || { echo "★ $RES の枝が $BR でない"; exit 2; }
rebasing() { [ -d "$(git -C $RES rev-parse --git-path rebase-merge)" ] || [ -d "$(git -C $RES rev-parse --git-path rebase-apply)" ]; }
rebasing && { echo "★ $RES が rebase の途中"; exit 2; }
mkdir -p $DEST/scripts
cp -p $S/out/per_run.csv $S/out/pairs.csv $S/out/memory_bits_vs_errors.csv $S/out/seal_states.csv $S/out/effort.csv $S/out/columns.csv $S/out/meta.json $S/out/mechanism_*.csv $S/out/mechanism_meta.json $DEST/
cp -p $S/surface.py $S/mechanism.py $S/replay.py $S/crosscheck.py $S/configs.json $S/pairs.json $S/watch.sh $S/push_hook.sh $DEST/scripts/
git -C $RES add -- $REL
if git -C $RES diff --cached --quiet -- $REL; then echo "$(date '+%F %T') push_hook：変わりなし"; exit 0; fi
N=$(python3.12 -c "import json;print(json.load(open('$S/out/meta.json'))['本数'])")
git -C $RES commit -q -m "表層の解析：表を作り直した（${N} 本、デスクトップの走行の係）" -m "$TRAILER" -- $REL || { echo "★ commit できない"; exit 1; }
for i in 1 2 3 4 5; do
  if git -C $RES pull -q --rebase --autostash origin $BR && git -C $RES push -q origin HEAD:$BR; then
    echo "$(date '+%F %T') push_hook：push した（$i 回目、$(git -C $RES rev-parse --short HEAD)）"; exit 0
  fi
  rebasing && git -C $RES rebase --abort
  sleep $((i * 20))
done
echo "★ push が 5 回失敗した（commit は手元に残っている）"; exit 1

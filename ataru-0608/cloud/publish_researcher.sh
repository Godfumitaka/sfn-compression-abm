#!/bin/bash
# 受け箱の指示 28 の 3：持ち帰った較正の本ごとに、researcher の calibration.jsonl.gz と sha256 を ataru-0608/cloud_runs/<本>/researcher/ に上げる。
# 引数：本の名前（例 calib_w1_seed047）。D: に持ち帰った出力（/mnt/d/sfn_runs/cloud/<本>/output）から写す。
set -euo pipefail
NAME=$1; SRC=/mnt/d/sfn_runs/cloud/$NAME/output/researcher; RES=$HOME/v33prod/results; DEST=$RES/ataru-0608/cloud_runs/$NAME/researcher
F=$(ls $SRC/*/seed*.calibration.jsonl.gz 2>/dev/null | head -1); [ -n "$F" ] || { echo "★ $NAME に較正の原記録が無い"; exit 2; }
mkdir -p $DEST && cp $F $DEST/ && (cd $DEST && sha256sum $(basename $F) > $(basename $F).sha256)
# D: の写しが機械の上の sha256（持ち帰りのときの一覧）と同じことを確かめる
REL=${F#/mnt/d/sfn_runs/cloud/$NAME/output/}
want=$(awk -F'\t' -v p="$REL" '$1==p {print $3}' /mnt/d/sfn_runs/cloud/$NAME/small/files_sha256.tsv)
got=$(cut -d' ' -f1 $DEST/$(basename $F).sha256)
[ "$want" == "$got" ] || { echo "★ sha256 が持ち帰りの一覧と違う（$want／$got）"; exit 3; }
cd $RES && git pull -q --rebase origin results-2026-09-27 && git add ataru-0608/cloud_runs/$NAME/researcher && git commit -q -m "較正の原記録：$NAME（走行の係）" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>" -- ataru-0608/cloud_runs/$NAME/researcher
for i in 1 2 3 4 5; do git push -q origin HEAD:results-2026-09-27 && break; sleep 20; git pull -q --rebase origin results-2026-09-27; done
echo "$NAME：較正の原記録 $(basename $F)（$(stat -c %s $F) バイト、sha256 $got）を上げた"

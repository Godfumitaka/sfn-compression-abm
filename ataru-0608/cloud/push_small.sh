#!/bin/bash
# 出力はクラウドに置いたまま、表と sha256 と小さい記録だけを GitHub（results-2026-09-27 の ataru-0608/cloud_runs/）に上げる。
# 使い方：push_small.sh <一本のフォルダ（output・time.log・native_command.json のある所）> <名前>
set -euo pipefail
D=$1; NAME=$2; HERE=$(cd "$(dirname "$0")" && pwd); RES=$HOME/v33prod/results; DEST=$RES/ataru-0608/cloud_runs/$NAME
mkdir -p $DEST
(cd $D/output && find . -type f -printf "%P\t%s\n" | sort | while IFS=$'\t' read -r p s; do echo -e "$p\t$s\t$(sha256sum "$p" | cut -d' ' -f1)"; done) > $DEST/files_sha256.tsv
python3 $HERE/norm_hash.py $D/output $DEST/norm_hash.tsv
cp $D/native_command.json $D/time.log $DEST/ 2>/dev/null || true
for f in flag.json manifest.jsonl; do [ -f $D/output/$f ] && cp $D/output/$f $DEST/; done
find $D/output/ledgers -name "*.done" -exec cp {} $DEST/ \; 2>/dev/null || true
cd $RES && git pull -q --rebase origin results-2026-09-27 && git add ataru-0608/cloud_runs/$NAME && git commit -q -m "クラウドの一本の小さい記録：$NAME（走行の係）" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>" -- ataru-0608/cloud_runs/$NAME
for i in 1 2 3 4 5; do git push -q origin HEAD:results-2026-09-27 && break; sleep 20; git pull -q --rebase origin results-2026-09-27; done
echo "上げた：ataru-0608/cloud_runs/$NAME（大きい出力は $D/output に残してある）"

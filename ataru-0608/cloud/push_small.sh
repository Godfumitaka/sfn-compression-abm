#!/bin/bash
# 一本が終わったら（クラウドの機械の上で）：大きい出力は S3 に上げ、表と sha256 と小さい記録だけを <一本のフォルダ>/small/ に集める。
# small/ は、デスクトップが aws_fetch_small.sh で持ってきて GitHub に上げる（クラウドに GitHub の鍵は置かない）。
# 使い方：push_small.sh <一本のフォルダ（output・time.log・native_command.json のある所）> <名前> <バケット>
set -euo pipefail
D=$1; NAME=$2; BUCKET=$3; HERE=$(cd "$(dirname "$0")" && pwd); S=$D/small
mkdir -p $S
(cd $D/output && find . -type f -printf "%P\t%s\n" | sort | while IFS=$'\t' read -r p s; do echo -e "$p\t$s\t$(sha256sum "$p" | cut -d' ' -f1)"; done) > $S/files_sha256.tsv
python3 $HERE/norm_hash.py $D/output $S/norm_hash.tsv
cp $D/native_command.json $D/time.log $S/ 2>/dev/null || true
for f in flag.json manifest.jsonl; do [ -f $D/output/$f ] && cp $D/output/$f $S/; done
find $D/output/ledgers -name "*.done" -exec cp {} $S/ \; 2>/dev/null || true
if [ "$BUCKET" != "-" ]; then aws s3 sync --only-show-errors $D/output s3://$BUCKET/cloud_runs/$NAME/output
aws s3 cp --only-show-errors $S/files_sha256.tsv s3://$BUCKET/cloud_runs/$NAME/files_sha256.tsv; fi   # バケットが「-」なら S3 には上げない（機械に S3 の権限が無いとき。デスクトップが持ってきて上げる）
echo "S3 に上げた：s3://$BUCKET/cloud_runs/$NAME/（小さい記録は $S）"

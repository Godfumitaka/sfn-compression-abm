#!/bin/bash
# 指示 29 の 4・31 の 2：止めた較正の重複の途中の出力を、機械を消す前に、D: と S3 に残す（消さない）。
# 引数：機械の IP、機械の上のフォルダ（cloud_runs/<束>/<本>）…。各本を tar.gz にして D:（/mnt/d/sfn_runs/cloud/stopped_dup/）へ運び、中身の一覧を確かめ、sha256 を書いて S3 に上げる。
set -u; source $HOME/cloud/aws_env.sh
IP=$1; shift; D=/mnt/d/sfn_runs/cloud/stopped_dup; mkdir -p $D; B=$(cat $BUCKET_FILE)
for R in "$@"; do
  N=$(echo $R | tr / _); F=$D/$N.tar.gz
  [ -s $F.sha256 ] && { echo "既にある：$F"; continue; }
  ssh -i $KEY_FILE -o ServerAliveInterval=30 -o ServerAliveCountMax=4 ubuntu@$IP "tar czf - -C ~/$R ." > $F.part && mv $F.part $F || { echo "★ $R を運べなかった"; continue; }
  n=$(tar tzf $F | wc -l) && (cd $D && sha256sum $(basename $F) > $(basename $F).sha256)
  aws s3 cp --only-show-errors $F s3://$B/cloud_runs/stopped_dup/ && aws s3 cp --only-show-errors $F.sha256 s3://$B/cloud_runs/stopped_dup/
  echo "$(date '+%F %T') 残した：$R（ファイル $n、$(stat -c %s $F) バイト）→ $F・s3://$B/cloud_runs/stopped_dup/"
done

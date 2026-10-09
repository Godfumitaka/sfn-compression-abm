#!/bin/bash
# Google Cloud の機械用（利用者 tatsu、鍵 ~/.ssh/google_compute_engine）。aws_fetch_run_par.sh の写し（指示 57）
# クラウドの一本が終わったら（デスクトップで）：機械の上で小さい記録を作らせ、出力をデスクトップの D: に持ってきて、デスクトップから S3 に上げ、小さい記録を GitHub に上げる。
# 機械に S3 の権限（IAM の役割）を付けられないため（鍵に IAM の権限が無い）、S3 にはデスクトップが上げる。C: は使わない（D: に置く）。
# 引数：機械の公開 IP、機械の上の一本のフォルダ（例 /home/ubuntu/cloud_runs/calib/w1_seed041）、名前（例 calib_w1_seed041）
set -euo pipefail; source $(dirname "$0")/aws_env.sh
IP=$1; RD=$2; NAME=$3; SSH="ssh -i $HOME/.ssh/google_compute_engine -o UserKnownHostsFile=$HOME/.ssh/gcp_known_hosts -o ConnectTimeout=15 -o ServerAliveInterval=30 -o ServerAliveCountMax=4 tatsu@$IP"; LOCAL=/mnt/d/sfn_runs/cloud/$NAME; B=$(bucket)
$SSH "grep -q '^rc=0' $RD/run.log" || { echo "★ $NAME はまだ終わっていないか、失敗した"; exit 2; }
$SSH "bash ~/cloud/push_small.sh $RD $NAME -"
mkdir -p $LOCAL && scp -q -r -o ServerAliveInterval=30 -o ServerAliveCountMax=4 -i $HOME/.ssh/google_compute_engine -o UserKnownHostsFile=$HOME/.ssh/gcp_known_hosts tatsu@$IP:$RD/output tatsu@$IP:$RD/small tatsu@$IP:$RD/native_command.json tatsu@$IP:$RD/time.log $LOCAL/
# 持ってきたものが機械の上と同じことを、ファイルごとの sha256 で確かめる
(cd $LOCAL/output && find . -type f -printf "%P\n" | sort | while read -r p; do echo -e "$p\t$(stat -c %s "$p")\t$(sha256sum "$p" | cut -d' ' -f1)"; done) > $LOCAL/fetched_sha256.tsv
diff <(cut -f1,3 $LOCAL/small/files_sha256.tsv) <(cut -f1,3 $LOCAL/fetched_sha256.tsv) > /dev/null || { echo "★ 持ってきた出力が機械の上と違う"; exit 3; }
aws s3 sync --only-show-errors $LOCAL/output s3://$B/cloud_runs/$NAME/output && aws s3 cp --only-show-errors $LOCAL/small/files_sha256.tsv s3://$B/cloud_runs/$NAME/files_sha256.tsv
exec 8>$HOME/cloud/wave1/git.lock; flock 8   # 何本も同時に持ち帰るとき、報告の枝への書き込みだけを一つずつにする（10/09 15:30）
DEST=$HOME/v33prod/results/ataru-0608/cloud_runs/$NAME; mkdir -p $DEST && cp $LOCAL/small/* $DEST/
cd $HOME/v33prod/results && git pull -q --rebase origin results-2026-09-27 && git add ataru-0608/cloud_runs/$NAME && { git diff --cached --quiet -- ataru-0608/cloud_runs/$NAME || git commit -q -m "クラウドの一本の小さい記録：$NAME（走行の係）" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>" -- ataru-0608/cloud_runs/$NAME; }
for i in 1 2 3 4 5; do git push -q origin HEAD:results-2026-09-27 && break; sleep 20; git pull -q --rebase origin results-2026-09-27; done
echo "$NAME：D: に置いた（$LOCAL）、S3 に上げた（s3://$B/cloud_runs/$NAME/）、小さい記録を GitHub に上げた"

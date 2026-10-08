#!/bin/bash
# クラウドの一本の「小さい記録」（sha256 の一覧・比べ用の sha256・命令・time.log・flag・manifest・.done）を、デスクトップへ持ってきて GitHub に上げる。
# 大きい出力は、クラウドで S3 に上げる（push_small.sh の中）。引数：機械の公開 IP、クラウドの一本のフォルダ、名前
set -euo pipefail; source $(dirname "$0")/aws_env.sh
IP=$1; RD=$2; NAME=$3; DEST=$HOME/v33prod/results/ataru-0608/cloud_runs/$NAME
mkdir -p $DEST
scp -i $KEY_FILE -r "ubuntu@$IP:$RD/small/*" $DEST/
cd $HOME/v33prod/results && git pull -q --rebase origin results-2026-09-27 && git add ataru-0608/cloud_runs/$NAME && git commit -q -m "クラウドの一本の小さい記録：$NAME（走行の係）" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>" -- ataru-0608/cloud_runs/$NAME
for i in 1 2 3 4 5; do git push -q origin HEAD:results-2026-09-27 && break; sleep 20; git pull -q --rebase origin results-2026-09-27; done

#!/bin/bash
# 立てた機械に、模型の版と台本を送り、setup を走らせる。クラウドには GitHub の鍵を置かない（版は git の束で送る）。
# 引数：機械の公開 IP
set -euo pipefail; source $(dirname "$0")/aws_env.sh
IP=$1; SSH="ssh -i $KEY_FILE -o StrictHostKeyChecking=accept-new ubuntu@$IP"
B=$HOME/cloud/attnprep_e9ed84a.bundle
git -C $HOME/sfn/sfn-compression-abm bundle create $B e9ed84ae3ee6c458f392cd58cadf9fc030639900 refs/remotes/origin/codex/attn-preparation-2026-10-08 2>/dev/null || \
  git -C $HOME/sfn/sfn-compression-abm bundle create $B refs/remotes/origin/codex/attn-preparation-2026-10-08
$SSH "mkdir -p ~/cloud"
scp -i $KEY_FILE $B $HOME/cloud/*.sh $HOME/cloud/*.py $HOME/cloud/*.json $HOME/cloud/ref200_desktop_wsl.tsv ubuntu@$IP:~/cloud/
$SSH "BUNDLE=~/cloud/attnprep_e9ed84a.bundle bash ~/cloud/setup.sh"

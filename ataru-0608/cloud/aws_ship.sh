#!/bin/bash
# 立てた機械に、模型の版と台本を送り、setup を走らせる。クラウドには GitHub の鍵を置かない（版は git の束で送る）。
# 引数：機械の公開 IP
set -euo pipefail; source $(dirname "$0")/aws_env.sh
IP=$1; BR=${2:-codex/attn-preparation-2026-10-08}; VER=${3:-e9ed84ae3ee6c458f392cd58cadf9fc030639900}; WTN=${4:-attnprep}; SSH="ssh -i $KEY_FILE -o StrictHostKeyChecking=accept-new ubuntu@$IP"
git -C $HOME/sfn/sfn-compression-abm fetch -q origin $BR
B=$HOME/cloud/${WTN}_${VER:0:7}.bundle
git -C $HOME/sfn/sfn-compression-abm bundle create $B refs/remotes/origin/$BR
$SSH "mkdir -p ~/cloud"
scp -i $KEY_FILE $B $HOME/cloud/*.sh $HOME/cloud/*.py $HOME/cloud/*.json $HOME/cloud/ref200_desktop_wsl.tsv ubuntu@$IP:~/cloud/
$SSH "BUNDLE=~/cloud/$(basename $B) VERSION=$VER WT=$WTN bash ~/cloud/setup.sh"

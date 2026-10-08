#!/bin/bash
# 使い終わった機械をすぐ消す。引数：機械の ID。この台本で立てた機械（Project の札が sfn-runner）だけを消す。
set -euo pipefail; source $(dirname "$0")/aws_env.sh
ID=$1
TAG=$(aws ec2 describe-instances --instance-ids $ID --query "Reservations[0].Instances[0].Tags[?Key=='Project'].Value | [0]" --output text)
[ "$TAG" == "$TAG_PROJECT" ] || { echo "★ $ID はこの係の機械ではない（札 $TAG）。消さない"; exit 2; }
aws ec2 terminate-instances --instance-ids $ID --query 'TerminatingInstances[0].CurrentState.Name' --output text
echo "$(date '+%F %T') 消した $ID" | tee -a $HOME/cloud/instances.log

#!/bin/bash
# 使い終わった機械をすぐ消す。引数：機械の ID。この台本で立てた機械（Project の札が sfn-runner）だけを消す。模型の本がまだ走っていれば消さない。
set -euo pipefail; source $(dirname "$0")/aws_env.sh
ID=$1
TAG=$(aws ec2 describe-instances --instance-ids $ID --query "Reservations[0].Instances[0].Tags[?Key=='Project'].Value | [0]" --output text)
[ "$TAG" == "$TAG_PROJECT" ] || { echo "★ $ID はこの係の機械ではない（札 $TAG）。消さない"; exit 2; }
# 残す印（~/cloud/KEEP_<ID>）がある機械は消さない（まだ持ち帰っていない出力があるとき、次の走行に使うとき）
[ -e $HOME/cloud/KEEP_$ID ] && { echo "★ $ID には残す印（$(cat $HOME/cloud/KEEP_$ID)）がある。消さない"; exit 4; }
# まだ模型の本が走っている機械は消さない（同じ機械に、別の見張りの本が並んでいるため。最後に終わった見張りが消す）
IP=$(aws ec2 describe-instances --instance-ids $ID --query 'Reservations[0].Instances[0].PublicIpAddress' --output text)
if [ "$IP" != "None" ] && [ -n "$IP" ]; then
  N=$(ssh -i $KEY_FILE -o ConnectTimeout=15 -o ServerAliveInterval=30 -o ServerAliveCountMax=4 ubuntu@$IP 'ps -eo args | grep -c "^python3.12 tools/v3_run.py"' 2>/dev/null || echo "?")
  [ "$N" == "0" ] || { echo "★ $ID ではまだ模型の本が $N 本走っている（又は数えられない）。消さない（最後に終わった見張りが消す）"; exit 3; }
fi
aws ec2 terminate-instances --instance-ids $ID --query 'TerminatingInstances[0].CurrentState.Name' --output text
echo "$(date '+%F %T') 消した $ID" | tee -a $HOME/cloud/instances.log

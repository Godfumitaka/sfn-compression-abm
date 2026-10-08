#!/bin/bash
# 機械を一台立てる。引数：機械の種類（許されたものだけ） [根のディスクの GB、既定 200]。立てた機械の ID と公開 IP を出す。
# 受け箱に Claude の始めの指示が来るまで、使わない。
set -euo pipefail; source $(dirname "$0")/aws_env.sh
TYPE=$1; DISK=${2:-200}
[[ " $ALLOWED_TYPES " == *" $TYPE "* ]] || { echo "★ 許されていない機械の種類：$TYPE（許されるのは $ALLOWED_TYPES）"; exit 2; }
AMI=$(aws ec2 describe-images --owners 099720109477 --filters "Name=name,Values=ubuntu/images/hvm-ssd-gp3/ubuntu-noble-24.04-amd64-server-*" "Name=state,Values=available" --query "sort_by(Images,&CreationDate)[-1].ImageId" --output text)   # Canonical（099720109477）の公式 Ubuntu Server 24.04 LTS の最新
SG=$(aws ec2 describe-security-groups --filters Name=group-name,Values=$SG_NAME --query 'SecurityGroups[0].GroupId' --output text)
ID=$(aws ec2 run-instances --image-id $AMI --instance-type $TYPE --key-name $KEY_NAME --security-group-ids $SG \
  --block-device-mappings "DeviceName=/dev/sda1,Ebs={VolumeSize=$DISK,VolumeType=gp3,DeleteOnTermination=true}" \
  --instance-initiated-shutdown-behavior terminate \
  --tag-specifications "ResourceType=instance,Tags=[{Key=Project,Value=$TAG_PROJECT},{Key=Name,Value=sfn-$TYPE}]" \
  --query 'Instances[0].InstanceId' --output text)
echo "$(date '+%F %T') 立てた $ID（$TYPE、AMI $AMI、ディスク ${DISK}GB）" | tee -a $HOME/cloud/instances.log
aws ec2 wait instance-running --instance-ids $ID
IP=$(aws ec2 describe-instances --instance-ids $ID --query 'Reservations[0].Instances[0].PublicIpAddress' --output text)
echo "$ID $IP"

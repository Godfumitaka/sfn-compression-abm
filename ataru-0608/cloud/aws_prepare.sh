#!/bin/bash
# アストラの鍵が入った後に一度だけ：SSH の鍵の組と入口（セキュリティグループ）を作る。入口はデスクトップの公開 IP からの SSH（22）だけ。
# SSH の秘密鍵は ~/.ssh に置き、GitHub に上げない・表示しない。
set -euo pipefail; source $(dirname "$0")/aws_env.sh
aws sts get-caller-identity --query Account --output text > /dev/null || { echo "★ AWS の鍵が使えない（aws configure はアストラが行う）"; exit 2; }
if ! aws ec2 describe-key-pairs --key-names $KEY_NAME > /dev/null 2>&1; then
  mkdir -p ~/.ssh && umask 077 && aws ec2 create-key-pair --key-name $KEY_NAME --key-type ed25519 --query KeyMaterial --output text > $KEY_FILE && chmod 600 $KEY_FILE
  echo "SSH の鍵の組を作った（秘密鍵は $KEY_FILE、上げない）"
fi
MYIP=$(curl -s https://checkip.amazonaws.com | tr -d '\n'); [[ $MYIP =~ ^[0-9.]+$ ]] || { echo "★ 公開 IP が取れない"; exit 2; }
VPC=$(aws ec2 describe-vpcs --filters Name=isDefault,Values=true --query 'Vpcs[0].VpcId' --output text)
SG=$(aws ec2 describe-security-groups --filters Name=group-name,Values=$SG_NAME Name=vpc-id,Values=$VPC --query 'SecurityGroups[0].GroupId' --output text 2>/dev/null)
if [ "$SG" == "None" ] || [ -z "$SG" ]; then
  SG=$(aws ec2 create-security-group --group-name $SG_NAME --description "SSH from desktop only" --vpc-id $VPC --query GroupId --output text)
  aws ec2 create-tags --resources $SG --tags Key=Project,Value=$TAG_PROJECT
fi
aws ec2 authorize-security-group-ingress --group-id $SG --protocol tcp --port 22 --cidr $MYIP/32 2>/dev/null || true
echo "入口 $SG：SSH は $MYIP/32 からだけ"

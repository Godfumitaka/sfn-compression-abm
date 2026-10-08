# AWS の決まり（受け箱の指示 17）。鍵の値はここに書かない。aws configure はアストラが自分で行う。
export AWS_REGION=us-east-1 AWS_DEFAULT_REGION=us-east-1
export PATH=$HOME/.local/bin:$PATH
ALLOWED_TYPES="c7a.xlarge c7a.8xlarge m7a.8xlarge r7a.8xlarge c7a.16xlarge m7a.16xlarge r7a.16xlarge"   # 指示 18：32 芯（8xlarge）を足した
AMI_OWNER=099720109477   # Canonical の公式 Ubuntu Server 24.04 LTS（x86_64）は ec2 describe-images で引く（鍵に SSM の権限が無いため）
KEY_NAME=sfn-runner; KEY_FILE=$HOME/.ssh/sfn-runner.pem; SG_NAME=sfn-runner-ssh; TAG_PROJECT=sfn-runner
BUCKET_FILE=$HOME/cloud/BUCKET    # S3 のバケットの名前（アストラが決め、Claude が伝えたら、この一行のファイルに書く）
bucket() { [ -s $BUCKET_FILE ] && cat $BUCKET_FILE || { echo "★ バケットの名前がまだ無い（$BUCKET_FILE）" >&2; return 1; }; }

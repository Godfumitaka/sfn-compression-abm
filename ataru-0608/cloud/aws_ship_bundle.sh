#!/bin/bash
# 受け箱の指示 30：係が置いた git bundle から版を取り出して、機械に送る（origin の枝からではなく）。
# 引数：機械の IP、bundle のファイル、README の sha256、README の HEAD コミット、README の tree の hash、作業場所の名前
# 1. bundle の sha256 が README と同じことを確かめる。2. デスクトップで bundle を取り出し、コミットと tree が README と同じことを確かめる。
# 3. 機械に送って setup し、機械の上でも HEAD と tree が同じことを確かめる。どれかが違えば、走らせずに止まる（rc≠0）。
set -euo pipefail; source $(dirname "$0")/aws_env.sh
IP=$1; B=$2; WANT_SHA=$3; WANT_COMMIT=$4; WANT_TREE=$5; WTN=$6
SSH="ssh -i $KEY_FILE -o StrictHostKeyChecking=accept-new -o ServerAliveInterval=30 -o ServerAliveCountMax=4 ubuntu@$IP"
got=$(sha256sum "$B" | cut -d' ' -f1); [ "$got" == "$WANT_SHA" ] || { echo "★ bundle の sha256 が README と違う（$got／$WANT_SHA）。走らせない"; exit 2; }
T=$(mktemp -d); git -C $HOME/sfn/sfn-compression-abm bundle verify -q "$B" >/dev/null 2>&1 || true
git clone -q --no-checkout $HOME/sfn/sfn-compression-abm $T/r && git -C $T/r fetch -q "$B" "+refs/*:refs/bundle/*"
c=$(git -C $T/r rev-parse "$WANT_COMMIT^{commit}"); t=$(git -C $T/r rev-parse "$WANT_COMMIT^{tree}")
[ "$c" == "$WANT_COMMIT" ] && [ "$t" == "$WANT_TREE" ] || { echo "★ デスクトップで取り出した版が README と違う（commit $c、tree $t）。走らせない"; exit 3; }
echo "デスクトップで確かめた：sha256・commit・tree が README と同じ"
$SSH "mkdir -p ~/cloud"
scp -q -i $KEY_FILE "$B" $HOME/cloud/*.sh $HOME/cloud/*.py $HOME/cloud/*.json ubuntu@$IP:~/cloud/
$SSH "BUNDLE=~/cloud/$(basename $B) VERSION=$WANT_COMMIT WT=$WTN bash ~/cloud/setup.sh"
r=$($SSH "cd ~/sfn/audit/_read/$WTN && git rev-parse HEAD HEAD^{tree} | tr '\n' ' '")
[ "$r" == "$WANT_COMMIT $WANT_TREE " ] || { echo "★ 機械の上の版が README と違う（$r）。走らせない"; exit 4; }
echo "機械の上で確かめた：HEAD $WANT_COMMIT、tree $WANT_TREE"

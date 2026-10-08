#!/bin/bash
# クラウド（AWS の Ubuntu Server 24.04）の機械を、デスクトップと同じ形にする。鍵や合い言葉はここに無い。GitHub の鍵も置かない。
# 版はデスクトップから git の束（aws_ship.sh が送る）で受け取る。使い方：BUNDLE=~/cloud/attnprep_e9ed84a.bundle bash setup.sh
set -euo pipefail
PYVER=3.12.13; VERSION=${VERSION:-e9ed84ae3ee6c458f392cd58cadf9fc030639900}; BUNDLE=${BUNDLE:-$HOME/cloud/attnprep_e9ed84a.bundle}; WT=${WT:-attnprep}   # 高速化の版は VERSION・BUNDLE・WT を替える
sudo apt-get update -y -q && sudo apt-get install -y -q git curl tmux time gzip unzip
command -v uv >/dev/null || curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH=$HOME/.local/bin:$PATH
uv python install $PYVER
ln -sf "$(uv python find $PYVER)" $HOME/.local/bin/python3.12
python3.12 --version | grep -q "Python $PYVER" || { echo "★ Python $PYVER でない"; exit 2; }
# 模型の版（準備版）を、きれいな作業場所に取り出す。模型は標準の部品だけを使う（pip の追加は要らない、デスクトップで確かめた）
mkdir -p $HOME/sfn/audit/_read
[ -d $HOME/sfn/sfn-compression-abm/.git ] || git init -q $HOME/sfn/sfn-compression-abm
git -C $HOME/sfn/sfn-compression-abm fetch -q $BUNDLE "+refs/*:refs/bundle/*"   # 束の中の参照を全部取る（束には remote の参照だけが入っているため）
git -C $HOME/sfn/sfn-compression-abm worktree add -q --detach $HOME/sfn/audit/_read/$WT $VERSION
[ "$(git -C $HOME/sfn/audit/_read/$WT rev-parse HEAD)" == "$VERSION" ] && [ -z "$(git -C $HOME/sfn/audit/_read/$WT status --short)" ] || { echo "★ 作業場所が版 $VERSION のきれいな形でない"; exit 2; }
(cd $HOME/sfn/audit/_read/$WT && python3.12 tools/v3_run.py --help > /dev/null) && echo "模型の版 $VERSION：--help 通った"
# 出力を S3 に上げるための AWS CLI（機械の権限（IAM の役割）で上げる。鍵は置かない）
command -v aws >/dev/null || { cd /tmp && curl -sS -o awscliv2.zip https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip && unzip -q -o awscliv2.zip && sudo ./aws/install; }
aws --version
echo "済み。次は verify200.sh で、デスクトップとの 200 試行の一致を確かめる。"

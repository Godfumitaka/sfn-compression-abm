#!/bin/bash
# クラウド（AWS の Ubuntu）の機械を、デスクトップと同じ形にする。鍵や合い言葉はここに書かない。
# 前もって：GitHub の読み書きの権限を、この機械に人が設定しておく（例：gh auth login、又は配備の鍵）。
# 使い方：bash setup.sh
set -euo pipefail
PYVER=3.12.13; VERSION=e9ed84ae3ee6c458f392cd58cadf9fc030639900; BRANCH=codex/attn-preparation-2026-10-08
REPO=https://github.com/Godfumitaka/sfn-compression-abm.git
sudo apt-get update -y && sudo apt-get install -y git curl tmux time gzip
command -v uv >/dev/null || curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH=$HOME/.local/bin:$PATH
uv python install $PYVER
ln -sf "$(uv python find $PYVER)" $HOME/.local/bin/python3.12
python3.12 --version | grep -q "Python $PYVER" || { echo "★ Python $PYVER でない"; exit 2; }
# 模型の版（準備版）を、きれいな作業場所に取り出す。模型は標準の部品だけを使う（pip の追加は要らない、デスクトップで確かめた）
mkdir -p $HOME/sfn $HOME/sfn/audit/_read
[ -d $HOME/sfn/sfn-compression-abm ] || git clone -q $REPO $HOME/sfn/sfn-compression-abm
git -C $HOME/sfn/sfn-compression-abm fetch -q origin $BRANCH
git -C $HOME/sfn/sfn-compression-abm worktree add -q --detach $HOME/sfn/audit/_read/attnprep $VERSION
[ -z "$(git -C $HOME/sfn/audit/_read/attnprep status --short)" ] || { echo "★ 作業場所がきれいでない"; exit 2; }
(cd $HOME/sfn/audit/_read/attnprep && python3.12 tools/v3_run.py --help > /dev/null) && echo "模型の版 $VERSION：--help 通った"
# 結果の枝（表・sha256・小さい記録を上げる先）
mkdir -p $HOME/v33prod
[ -d $HOME/v33prod/results ] || git clone -q -b results-2026-09-27 --single-branch $REPO $HOME/v33prod/results
# 行を取る道具（デスクトップと同じもの）を、この機械の場所に合わせて置く
mkdir -p $HOME/queue $HOME/smeprod_a/plan
HERE=$(cd "$(dirname "$0")" && pwd)
for f in queue_row.py build_commands.py launch_row.sh memroom_any.py; do sed "s#/home/tatsu#$HOME#g" $HERE/$f > $HOME/queue/$f; done
cp $HERE/run_after_audit.py $HOME/smeprod_a/plan/run_after_audit.py
echo 8 > $HOME/queue/MAXRUN; echo 2 > $HOME/queue/NEWPEAK_GIB
echo "済み。次は verify200.sh で、デスクトップとの 200 試行の一致を確かめる。"

#!/bin/bash
# 枠の大きさ（vCPU）から、立てられる台数を出す（受け箱の指示 18）。立てはしない。
# 引数：機械の種類 オンデマンドの枠（vCPU） スポットの枠（vCPU）   例：aws_plan.sh c7a.8xlarge 32 32
# 8xlarge は 32 芯、16xlarge は 64 芯、xlarge は 4 芯。枠の引き上げが通ったら、同じ台本で台数だけ増える。
set -euo pipefail; source $(dirname "$0")/aws_env.sh
TYPE=$1; OD=$2; SP=$3
[[ " $ALLOWED_TYPES " == *" $TYPE "* ]] || { echo "★ 許されていない種類：$TYPE"; exit 2; }
case $TYPE in *.xlarge) V=4;; *.8xlarge) V=32;; *.16xlarge) V=64;; *) echo "★ 芯の数が分からない"; exit 2;; esac
echo "$TYPE（$V 芯）：オンデマンド $((OD / V)) 台（枠 $OD）、スポット $((SP / V)) 台（枠 $SP）。今走っている同じ枠の機械の芯は、ここから引いて考える。"

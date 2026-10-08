#!/bin/bash
# スポットがまた止められたときの立て直し（受け箱の指示 26、台帳 D-07βγ）。Claude に聞かずに次の順で行う：
#  1. c7a.8xlarge のスポットを、その時点で一番安いゾーンに立てる（止められたゾーンは避ける）。
#  2. 空きが無ければ m7a.8xlarge のスポット、次に r7a.8xlarge のスポット。
#  3. どれも立たなければ、30 分おきに 1 からやり直す（オンデマンドの枠は使わない）。
#  4. 立ったら、旗つきの版を送って setup し、止められた本（引数の本）だけを最初からやり直す。
#  5. 時刻・ゾーン・種類・単価を ~/cloud/spot_history.tsv に書く（報告の表に写す）。
# 引数：止められたゾーン 本の一覧（例 "w1_seed041 w2_seed048"）。最後の行に「ID IP」を出す。
set -u; source $HOME/cloud/aws_env.sh
BADAZ=$1; RUNS=$2; HIST=$HOME/cloud/spot_history.tsv
[ -f $HIST ] || echo -e "time\tevent\tinstance\ttype\taz\tspot_price_usd_per_h\tnote" > $HIST
while true; do
  for TYPE in c7a.8xlarge m7a.8xlarge r7a.8xlarge; do
    BEST=$(aws ec2 describe-spot-price-history --instance-types $TYPE --product-descriptions "Linux/UNIX" --start-time $(date -u +%FT%TZ) \
      --query 'SpotPriceHistory[].[AvailabilityZone,SpotPrice]' --output text | sort -k2 -g | awk -v bad="$BADAZ" '$1!=bad' | head -1)
    AZ=$(echo "$BEST" | awk '{print $1}'); PRICE=$(echo "$BEST" | awk '{print $2}')
    [ -z "$AZ" ] && continue
    SUBNET=$(aws ec2 describe-subnets --filters Name=default-for-az,Values=true Name=availability-zone,Values=$AZ --query 'Subnets[0].SubnetId' --output text)
    OUT=$(SUBNET=$SUBNET bash $HOME/cloud/aws_launch.sh $TYPE 80 spot 2>&1)
    LINE=$(echo "$OUT" | tail -1)
    if [[ $LINE =~ ^i-[0-9a-f]+\ [0-9.]+$ ]]; then
      ID=${LINE% *}; IP=${LINE#* }
      echo -e "$(date '+%F %T')\t立てた\t$ID\t$TYPE\t$AZ\t$PRICE\t止められたゾーン $BADAZ を避けた" >> $HIST
      for i in $(seq 1 30); do ssh -i $KEY_FILE -o StrictHostKeyChecking=accept-new -o ConnectTimeout=10 ubuntu@$IP true 2>/dev/null && break; sleep 10; done
      bash $HOME/cloud/aws_ship.sh $IP codex/attn-exact-speed-2026-10-08 7294389d70795c847790472aa836b93dc1ca7fd5 attnfast > $HOME/cloud/ship_respawn_$ID.log 2>&1 || { echo -e "$(date '+%F %T')\tsetup 失敗\t$ID\t$TYPE\t$AZ\t$PRICE\t" >> $HIST; bash $HOME/cloud/aws_terminate.sh $ID; continue; }
      for r in $RUNS; do w=${r:1:1}; s=$((10#${r:7:3}))
        ssh -i $KEY_FILE -o ConnectTimeout=15 ubuntu@$IP "WT=attnfast EXTRA_FLAGS='--stage2-speed on' bash ~/cloud/run_calib.sh $w $s ~/cloud_runs/calib_fast" >> $HOME/cloud/ship_respawn_$ID.log 2>&1
      done
      echo -e "$(date '+%F %T')\t始め直した\t$ID\t$TYPE\t$AZ\t$PRICE\t本：$RUNS" >> $HIST
      echo "$ID $IP"; exit 0
    else
      echo -e "$(date '+%F %T')\t立たない\t-\t$TYPE\t$AZ\t$PRICE\t$(echo "$OUT" | grep -o 'InsufficientInstanceCapacity\|MaxSpotInstanceCountExceeded\|[A-Za-z]*Exception' | head -1)" >> $HIST
    fi
  done
  echo -e "$(date '+%F %T')\t30 分待つ\t-\t-\t-\t-\tどの種類も立たなかった" >> $HIST
  sleep 1800
done

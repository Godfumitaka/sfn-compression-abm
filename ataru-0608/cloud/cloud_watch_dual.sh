#!/bin/bash
# 旗つきの較正 10 本の見張り（受け箱の指示 27）：同じ 10 本を、オンデマンド（確実）とスポット（三台目）の二台で並べている。
# 10 分ごとに、まだ持ってきていない本について、どちらかの機械で終わっていれば（rc=0）、先に終わった方を aws_fetch_run.sh で持ってくる（D:・S3・GitHub）。
# どちらの機械の本を使ったかと、クラウドで終わった時刻を ~/cloud/calib_fast_done.tsv に書く。
# スポットが止められたら、もう立て直さない（指示 27 の 2）。オンデマンドに任せる。10 本を全部持ってきたら、二台とも消す。失敗した本は記録して待つ。
# 引数：オンデマンドの ID IP、スポットの ID IP
set -u; source $HOME/cloud/aws_env.sh
OD_ID=$1; OD_IP=$2; SP_ID=$3; SP_IP=$4; SP_ALIVE=1
DONE=$HOME/cloud/calib_fast_done.tsv; LOG=$HOME/cloud/cloud_watch_fast.log
RUNS="w1_seed041 w1_seed042 w1_seed044 w1_seed046 w1_seed048 w2_seed043 w2_seed045 w2_seed046 w2_seed047 w2_seed048"
[ -f $DONE ] || echo -e "run\tcloud_finished\tfetched_at\tstatus" > $DONE
say() { echo "$(date '+%F %T') $*" >> $LOG; }
probe() { ssh -i $KEY_FILE -o ConnectTimeout=15 ubuntu@$1 "echo \"rc:\$(grep -h '^rc=' ~/cloud_runs/calib_fast/$2/run.log 2>/dev/null | tail -1)\"; echo \"fin:\$(stat -c %y ~/cloud_runs/calib_fast/$2/run.log 2>/dev/null | cut -c1-19)\"" 2>/dev/null; }
say "見張り（二台）を始めた：オンデマンド $OD_ID（$OD_IP）、スポット $SP_ID（$SP_IP）"
while true; do
  if (( SP_ALIVE )); then
    S=$(aws ec2 describe-instances --instance-ids $SP_ID --query "Reservations[0].Instances[0].State.Name" --output text 2>/dev/null)
    [ "$S" == "running" ] || { SP_ALIVE=0; say "★ スポット $SP_ID は $S。もう立て直さず、オンデマンドに任せる（指示 27 の 2）"; }
  fi
  n=0
  for r in $RUNS; do
    if grep -q "^$r	" $DONE; then n=$((n+1)); continue; fi
    best=""; bestfin=""
    for side in od sp; do
      [ $side == sp ] && (( ! SP_ALIVE )) && continue
      ip=$([ $side == od ] && echo $OD_IP || echo $SP_IP)
      st=$(probe $ip $r) || continue
      rc=$(echo "$st" | sed -n 's/^rc://p'); fin=$(echo "$st" | sed -n 's/^fin://p')
      if [ "$rc" == "rc=0" ]; then
        if [ -z "$best" ] || [[ "$fin" < "$bestfin" ]]; then best=$side; bestfin=$fin; fi
      elif [ -n "$rc" ] && [ $side == od ]; then
        grep -q "^$r	" $DONE || { echo -e "$r\t$fin（UTC）\t\t失敗 $rc（オンデマンド）" >> $DONE; say "★ $r がオンデマンドで失敗した（$rc）。機械は消さずに待つ"; }
      fi
    done
    if [ -n "$best" ]; then
      ip=$([ $best == od ] && echo $OD_IP || echo $SP_IP); where=$([ $best == od ] && echo "オンデマンド $OD_ID" || echo "スポット $SP_ID")
      if bash $HOME/cloud/aws_fetch_run.sh $ip /home/ubuntu/cloud_runs/calib_fast/$r calib_fast_$r >> $LOG 2>&1; then
        echo -e "$r\t$bestfin（UTC、$where）\t$(date '+%F %T')\tok" >> $DONE; say "持ってきた $r（$where で先に終わった $bestfin UTC）"; n=$((n+1))
      else say "★ $r を持ってこられなかった（次の回にやり直す）"; fi
    fi
  done
  if [ $n -ge 10 ]; then
    if grep -q "失敗" $DONE; then say "★ 失敗した本があるので、機械を消さずに待つ"; sleep 600; continue; fi
    bash $HOME/cloud/aws_terminate.sh $OD_ID >> $LOG 2>&1; (( SP_ALIVE )) && bash $HOME/cloud/aws_terminate.sh $SP_ID >> $LOG 2>&1
    say "10 本（旗つき）を全部持ってきたので、機械を消した"; break
  fi
  sleep 600
done

#!/bin/bash
# クラウドの較正の旗つき（受け箱の指示 25、--stage2-speed on、スポット）の見張り。スポットが止められたら spot_respawn.sh（指示 26）で立て直す。元は cloud_watch.sh（デスクトップの tmux cloudwatch で動かす）。10 分ごとに：
#  - 機械の上で終わった本（run.log に rc=0）を、まだ持ってきていなければ aws_fetch_run.sh で持ってくる（D:・S3・GitHub の小さい記録）。
#  - 終わった時刻を ~/cloud/calib13_done.tsv に書く（指示 19 の「先に 1,740 試行を終えた方を使う」の比べのため）。
#  - 13 本を全部持ってきたら、機械を消して抜ける（使い終わった機械はすぐ消す）。
#  - 失敗した本（rc が 0 でない）があれば記録して、消さずに待つ（係が見て決める）。
# 引数：機械の ID、公開 IP
set -u; source $HOME/cloud/aws_env.sh
ID=$1; IP=$2; SSH="ssh -i $KEY_FILE -o ConnectTimeout=15 ubuntu@$IP"; DONE=$HOME/cloud/calib_fast_done.tsv; LOG=$HOME/cloud/cloud_watch_fast.log
RUNS="w1_seed041 w1_seed042 w1_seed044 w1_seed046 w1_seed048 w2_seed043 w2_seed045 w2_seed046 w2_seed047 w2_seed048"
[ -f $DONE ] || echo -e "run\tcloud_finished\tfetched_at\tstatus" > $DONE
say() { echo "$(date '+%F %T') $*" >> $LOG; }
say "見張りを始めた（$ID、$IP）"
while true; do
  n=0
  for r in $RUNS; do
    if grep -q "^$r	" $DONE; then n=$((n+1)); continue; fi
    st=$($SSH "echo \"rc:\$(grep -h '^rc=' ~/cloud_runs/calib_fast/$r/run.log 2>/dev/null | tail -1)\"; echo \"fin:\$(stat -c %y ~/cloud_runs/calib_fast/$r/run.log 2>/dev/null | cut -c1-19)\"" 2>/dev/null) || { S=$(aws ec2 describe-instances --instance-ids $ID --query "Reservations[0].Instances[0].State.Name" --output text 2>/dev/null); say "★ SSH が通らない（機械の状態 $S）"; [ "$S" == "terminated" ] && { BADAZ=$(aws ec2 describe-instances --instance-ids $ID --query "Reservations[0].Instances[0].Placement.AvailabilityZone" --output text); LEFT=$(for x in $RUNS; do grep -q "^$x	" $DONE || echo -n "$x "; done); say "★ スポットで止められた（$ID、$BADAZ）。まだの本（$LEFT）を、指示 26 の決まりで立て直してやり直す"; NEW=$(bash $HOME/cloud/spot_respawn.sh "$BADAZ" "$LEFT" | tail -1); ID=${NEW% *}; IP=${NEW#* }; SSH="ssh -i $KEY_FILE -o ConnectTimeout=15 ubuntu@$IP"; say "立て直した：$ID（$IP）"; }; break; }
    rc=$(echo "$st" | sed -n 's/^rc://p'); fin=$(echo "$st" | sed -n 's/^fin://p')
    if [ "$rc" == "rc=0" ]; then
      if bash $HOME/cloud/aws_fetch_run.sh $IP /home/ubuntu/cloud_runs/calib_fast/$r calib_fast_$r >> $LOG 2>&1; then
        echo -e "$r\t$fin（UTC）\t$(date '+%F %T')\tok" >> $DONE; say "持ってきた $r（クラウドで終わった $fin UTC）"; n=$((n+1))
      else say "★ $r を持ってこられなかった（次の回にやり直す）"; fi
    elif [ -n "$rc" ]; then
      grep -q "^$r	" $DONE || { echo -e "$r\t$fin（UTC）\t\t失敗 $rc" >> $DONE; say "★ $r が失敗した（$rc）。機械は消さずに待つ"; }
      n=$((n+1))
    fi
  done
  if [ $n -ge 10 ]; then
    if grep -q "失敗" $DONE; then say "★ 失敗した本があるので、機械を消さずに待つ"; sleep 600; continue; fi
    bash $HOME/cloud/aws_terminate.sh $ID >> $LOG 2>&1 && say "10 本（旗つき）を全部持ってきたので、機械 $ID を消した"; break
  fi
  sleep 600
done

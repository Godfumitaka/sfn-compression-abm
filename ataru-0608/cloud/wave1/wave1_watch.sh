#!/bin/bash
# 第 1 波の見張り（受け箱の指示 33 の 1）：10 分ごとに、終わった本（rc=0）を aws_fetch_run.sh で D:・S3・GitHub（小さい記録）に運び、
# 台帳本体（ledgers の jsonl.gz）を ataru-0608/cloud_runs/<本>/ledgers/ に sha256 と一緒に上げる（一本 20MB まで。超えたら上げずに記録する）。
# rc≠0 の本は記録だけして持ってこない（止まりは列と報告に書く）。全部が終わった（rc がある）ら抜ける。機械は消さない（次の種に使うかは指示を待つ）。
set -u; source $HOME/cloud/aws_env.sh
ID=$1; IP=$2; CMDS=$HOME/cloud/wave1/wave1_s12_commands.json; DONE=$HOME/cloud/wave1/done.tsv; LOG=$HOME/cloud/wave1/watch.log; RES=$HOME/v33prod/results
[ -f $DONE ] || echo -e "name\trc\tfinished\tfetched_at\tstatus" > $DONE
say() { echo "$(date '+%F %T') $*" >> $LOG; }
say "見張りを始めた（$ID、$IP）"
while true; do
  left=0
  while read -r NAME RD; do
    grep -q "^$NAME	" $DONE && continue
    st=$(ssh -i $KEY_FILE -o ConnectTimeout=15 -o ServerAliveInterval=30 -o ServerAliveCountMax=4 ubuntu@$IP "echo \"rc:\$(grep -h '^rc=' $RD/run.log 2>/dev/null | tail -1)\"; echo \"fin:\$(stat -c %y $RD/run.log 2>/dev/null | cut -c1-19)\"" 2>/dev/null) || { left=$((left+1)); continue; }
    rc=$(echo "$st" | sed -n 's/^rc://p'); fin=$(echo "$st" | sed -n 's/^fin://p')
    [ -z "$rc" ] && { left=$((left+1)); continue; }
    if [ "$rc" != "rc=0" ]; then echo -e "$NAME\t$rc\t$fin\t\t止まり" >> $DONE; say "★ $NAME は $rc（持ってこない）"; continue; fi
    if bash $HOME/cloud/aws_fetch_run.sh $IP $RD $NAME >> $LOG 2>&1; then
      L=$(ls /mnt/d/sfn_runs/cloud/$NAME/output/ledgers/cells/*/seed*.jsonl.gz 2>/dev/null | head -1); msg="台帳なし"
      if [ -n "$L" ]; then
        sz=$(stat -c %s $L)
        if [ $sz -le 20971520 ]; then
          (cd $RES && git pull -q --rebase origin results-2026-09-27; G=ataru-0608/cloud_runs/$NAME/ledgers; mkdir -p $G && cp $L $G/ && (cd $G && sha256sum $(basename $L) > $(basename $L).sha256) && git add $G && git commit -q -m "第 1 波の台帳：$NAME（走行の係）" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>" -- $G; for i in 1 2 3 4 5; do git push -q origin HEAD:results-2026-09-27 && break; sleep 20; git pull -q --rebase origin results-2026-09-27; done) >> $LOG 2>&1 && msg="台帳 $sz バイトを上げた" || msg="★ 台帳を上げられなかった"
        else msg="★ 台帳が $sz バイト（20MB 超）。上げていない"; fi
      fi
      echo -e "$NAME\trc=0\t$fin\t$(date '+%F %T')\tok、$msg" >> $DONE; say "持ってきた $NAME（$fin UTC 終了）、$msg"
    else say "★ $NAME を持ってこられなかった（次の回にやり直す）"; left=$((left+1)); fi
  done < <(python3 -c "import json;[print(c['name'],c['rundir']) for c in json.load(open('$CMDS'))]")
  [ $left -eq 0 ] && { say "28 本の全部に rc が出たので、見張りを終える"; break; }
  sleep 600
done

#!/bin/bash
# 第 1 波の見張り（受け箱の指示 33 の 1）：10 分ごとに、終わった本（rc=0）を aws_fetch_run.sh で D:・S3・GitHub（小さい記録）に運び、
# 受け箱の指示 34：side/<cell>/seedNNN.jsonl を gzip（-n、時刻を入れない）したものと、stage2/<cell>/seedNNN.jsonl.gz を、ataru-0608/cloud_runs/<本>/ に sha256 と一緒に上げる
# （小さい記録は aws_fetch_run.sh が上げる）。台帳本体は S3 と D: に置くだけ。一つが 50MB を超えたら上げずに記録する。
# 直し（05:30、指示 35 の 3）：side は seedNNN.side.jsonl.gz、第二段は seedNNN.stage2.jsonl.gz の名前で上げる（前は同じ名前で、第二段が side を上書きしていた）。
# 直し（04:25）：ループの中の ssh・持ち帰りが一覧の stdin を読んでしまい、一回目で抜けていた。ssh -n と < /dev/null にした。
# rc≠0 の本は記録だけして持ってこない（止まりは列と報告に書く）。全部が終わった（rc がある）ら抜ける。機械は消さない（次の種に使うかは指示を待つ）。
set -u; source $HOME/cloud/aws_env.sh
# 直し（16:00、指示 42）：~/cloud/wave1/KEEP_WATCHING がある間は、全部済んでも抜けない（後から本が足されるため）。
# 直し（15:30）：持ち帰りは機械ごとに並べて行い、報告の枝への書き込み（git）だけを git.lock で一つずつにする。
# 直し（13:55、指示 41）：機械ごとに一つずつ走らせる。引数の残りは命令の一覧のファイル
ID=$1; IP=$2; shift 2; CMDS="$*"; DONE=$HOME/cloud/wave1/done.tsv; LOG=$HOME/cloud/wave1/watch.log; RES=$HOME/v33prod/results
[ -f $DONE ] || echo -e "name\trc\tfinished\tfetched_at\tstatus" > $DONE
say() { echo "$(date '+%F %T') $*" >> $LOG; }
say "見張りを始めた（$ID、$IP、$CMDS）"
while true; do
  left=0
  while read -r NAME RD; do
    grep -q "^$NAME	" $DONE && continue
    st=$(ssh -n -i $KEY_FILE -o ConnectTimeout=15 -o ServerAliveInterval=30 -o ServerAliveCountMax=4 ubuntu@$IP "echo \"rc:\$(grep -h '^rc=' $RD/run.log 2>/dev/null | tail -1)\"; echo \"fin:\$(stat -c %y $RD/run.log 2>/dev/null | cut -c1-19)\"" 2>/dev/null) || { left=$((left+1)); continue; }
    rc=$(echo "$st" | sed -n 's/^rc://p'); fin=$(echo "$st" | sed -n 's/^fin://p')
    [ -z "$rc" ] && { left=$((left+1)); continue; }
    if [ "$rc" != "rc=0" ]; then echo -e "$NAME\t$rc\t$fin\t\t止まり" >> $DONE; say "★ $NAME は $rc（持ってこない）"; continue; fi
    if bash $HOME/cloud/aws_fetch_run_par.sh $IP $RD $NAME >> $LOG 2>&1 < /dev/null; then
      O=/mnt/d/sfn_runs/cloud/$NAME/output; G=ataru-0608/cloud_runs/$NAME; msg=""
      SIDE=$(ls $O/side/*/seed[0-9][0-9][0-9].jsonl 2>/dev/null | head -1); ST2=$(ls $O/stage2/*/seed[0-9][0-9][0-9].jsonl.gz 2>/dev/null | head -1)
      ( exec 8>$HOME/cloud/wave1/git.lock; flock 8; cd $RES && git pull -q --rebase origin results-2026-09-27; mkdir -p $G
        [ -n "$SIDE" ] && gzip -n -c $SIDE > $G/$(basename $SIDE .jsonl).side.jsonl.gz
        [ -n "$ST2" ] && cp $ST2 $G/$(basename $ST2 .jsonl.gz).stage2.jsonl.gz
        for f in $G/*.side.jsonl.gz $G/*.stage2.jsonl.gz; do [ -f "$f" ] || continue; [ $(stat -c %s $f) -le 52428800 ] || { echo "★ $(basename $f) が 50MB 超。上げない"; mv $f /mnt/d/sfn_runs/cloud/$NAME/; continue; }; (cd $G && sha256sum $(basename $f) > $(basename $f).sha256); done
        git add $G && git commit -q -m "第 1 波の side と第二段の記録：$NAME（走行の係）" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>" -- $G
        for i in 1 2 3 4 5; do git push -q origin HEAD:results-2026-09-27 && break; sleep 20; git pull -q --rebase origin results-2026-09-27; done ) >> $LOG 2>&1 < /dev/null
      msg="side $( [ -n "$SIDE" ] && stat -c %s $SIDE || echo 無し) バイト（gzip 前）、第二段 $( [ -n "$ST2" ] && stat -c %s $ST2 || echo 無し) バイトを上げた"
      echo -e "$NAME\trc=0\t$fin\t$(date '+%F %T')\tok、$msg" >> $DONE; say "持ってきた $NAME（$fin UTC 終了）、$msg"
    else say "★ $NAME を持ってこられなかった（次の回にやり直す）"; left=$((left+1)); fi
  done < <(python3 -c "import json,sys;[print(c['name'],c['rundir']) for f in sys.argv[1:] for c in json.load(open(f))]" $CMDS)
  [ $left -eq 0 ] && [ ! -e $HOME/cloud/wave1/KEEP_WATCHING ] && { say "全部の本に rc が出たので、見張りを終える"; break; }
  sleep 600
done

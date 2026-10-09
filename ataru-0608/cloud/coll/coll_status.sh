#!/bin/bash
# 関門の進みを、python を使わずに（bash と curl だけ）5 分ごとに GCS に上げる。機械の既定のサービス口座の token（metadata）を使う。
B=sfn-gate-status-577b8173
while true; do
  R=/mnt/coll_gate_gcp/run-same-host
  { echo "時刻 $(date -u +%FT%T)"; cat ~/coll_chain.log 2>/dev/null; echo "--- phase1"; grep -E "始める|終わった|ALLDONE|passed|拒む|STOP" ~/coll_phase1_gcp.log 2>/dev/null | tail -12
    echo "--- phase2"; grep -E "始める|終わった|ALLDONE|passed|拒む|STOP" ~/coll_phase2_gcp.log 2>/dev/null | tail -12
    echo "--- gates"; ls $R/gates 2>/dev/null; echo "--- STOP"; cat $R/STOP.json 2>/dev/null; echo "--- 模型の数 $(ps -eo args | grep -c '[o]bserve')"; } > /tmp/status.txt
  T=$(curl -s -H "Metadata-Flavor: Google" http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/token | sed -n 's/.*"access_token":"\([^"]*\)".*/\1/p')
  curl -s -X POST -H "Authorization: Bearer $T" -H "Content-Type: text/plain; charset=utf-8" --data-binary @/tmp/status.txt "https://storage.googleapis.com/upload/storage/v1/b/$B/o?uploadType=media&name=status.txt" > /dev/null
  sleep 300
done

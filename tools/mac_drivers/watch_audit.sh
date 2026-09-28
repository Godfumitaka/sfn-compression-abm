#!/bin/bash
# 外出中の決まり（2026-09-27 委任書 6）：結果のブランチ results-2026-09-27 の audit/ と control/ を 10 分おきに見る。
# 見たことのあるファイルの一覧（~/v33prod/audit_seen.txt）に無いファイルが出たら、その名前と中身の頭を書き出して終わる（見張り直しは呼び出し側）。
# 自分（マックの Code）が上げた control/ のファイルは、上げたときに一覧に足しておく。
set -u
REPO=/Users/tatsu-admin/sfn/sfn-compression-abm
SEEN=$HOME/v33prod/audit_seen.txt
LOG=$HOME/v33prod/watch_audit.log
touch "$SEEN"
while true; do
  if git -C "$REPO" fetch -q origin results-2026-09-27 2>>"$LOG"; then
    NEW=$(git -C "$REPO" -c core.quotepath=false ls-tree -r --name-only origin/results-2026-09-27 -- audit control | grep -vxF -f "$SEEN" || true)
    echo "$(date '+%F %T') 見た（新しいファイル $(printf '%s' "$NEW" | grep -c . || true)）" >> "$LOG"
    if [[ -n "$NEW" ]]; then
      echo "$(date '+%F %T') 新しいファイル"
      printf '%s\n' "$NEW"
      exit 0
    fi
  else
    echo "$(date '+%F %T') fetch が失敗" >> "$LOG"
  fi
  sleep 600
done

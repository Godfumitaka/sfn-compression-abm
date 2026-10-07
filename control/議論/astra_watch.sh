#!/bin/bash
# Astra の待機：control/議論/*/状態.md の一行目が「次: Astra」の相談があるときだけ codex を起動する。
# 見るだけ（git fetch）の間は、模型の使用量はかからない。
# 使い方：tmux の中で  CODEX_PROFILE=<いつもの Astra のプロファイル名> bash astra_watch.sh
set -u
REPO="${REPO:-$HOME/astra_debate/res}"        # results-2026-09-27 の専用の clone
BRANCH="${BRANCH:-results-2026-09-27}"
INTERVAL="${INTERVAL:-300}"                    # 秒
DAILY_MAX="${DAILY_MAX:-12}"                   # 一日に Astra を起こす上限
MAX_ROUNDS="${MAX_ROUNDS:-4}"                  # 一つの相談での Astra の返事の上限
CODEX_PROFILE="${CODEX_PROFILE:-}"
STATE_DIR="$HOME/astra_debate"
LOG="$STATE_DIR/watch.log"
mkdir -p "$STATE_DIR"

log() { echo "$(date '+%F %T') $*" >> "$LOG"; }

set_state() {  # $1=状態.md  $2=新しい一行目
  python3 - "$1" "$2" <<'PY'
import sys
p, new = sys.argv[1], sys.argv[2]
lines = open(p, encoding="utf-8").read().splitlines()
lines = [new] + lines[1:] if lines else [new]
open(p, "w", encoding="utf-8").write("\n".join(lines) + "\n")
PY
}

sync_repo() {
  cd "$REPO" || return 1
  git fetch -q origin "$BRANCH" >>"$LOG" 2>&1 || return 1
  git rebase -q "origin/$BRANCH" >>"$LOG" 2>&1 || { git rebase --abort >/dev/null 2>&1; return 1; }
}

push_repo() {
  local i
  for i in 1 2 3 4; do
    git push -q origin "HEAD:$BRANCH" >>"$LOG" 2>&1 && return 0
    sleep $((2 ** i))
    git pull -q --rebase origin "$BRANCH" >>"$LOG" 2>&1
  done
  return 1
}

today_count() { grep -c "^$(date +%F) .* 起動$" "$LOG" 2>/dev/null; }

log "待機を始めた（間隔 ${INTERVAL} 秒、一日 ${DAILY_MAX} 回まで）"
while true; do
  if sync_repo; then
    for st in "$REPO"/control/議論/*/状態.md; do
      [ -f "$st" ] || continue
      [ "$(head -n 1 "$st")" = "次: Astra" ] || continue
      dir=$(dirname "$st"); name=$(basename "$dir")
      rounds=$(ls "$dir" | grep -c '_Astra\.md$')
      if [ "$rounds" -ge "$MAX_ROUNDS" ]; then
        log "$name 往復の上限"
        set_state "$st" "次: Claude（往復の上限）"
        git add "$st" && git commit -q -m "議論 ${name}：往復の上限" && push_repo
        continue
      fi
      if [ "$(today_count)" -ge "$DAILY_MAX" ]; then
        log "一日の上限に達したので、今日は起こさない"
        break
      fi
      n=$(ls "$dir" | grep -c '^[0-9][0-9]_.*\.md$')
      next=$(printf '%02d' $((n + 1)))
      out="$dir/${next}_Astra.md"
      log "$name ${next} 起動"
      prompt="control/議論/Astraへの決まり.md を読み、それに従ってください。議論のフォルダ control/議論/${name}/ の全部のファイルを番号順に読み、次の返事（${next}_Astra.md の中身）だけを書いてください。"
      if [ -n "$CODEX_PROFILE" ]; then
        codex exec -p "$CODEX_PROFILE" -s read-only -C "$REPO" -o "$out" "$prompt" >>"$LOG" 2>&1
      else
        codex exec -s read-only -C "$REPO" -o "$out" "$prompt" >>"$LOG" 2>&1
      fi
      if [ -s "$out" ]; then
        set_state "$st" "次: Claude"
        git add "$out" "$st"
        git commit -q -m "議論 ${name}：${next} を Astra が書いた"
        push_repo || log "$name push に失敗"
        log "$name ${next} 済み"
      else
        rm -f "$out"
        set_state "$st" "次: Claude（Astra の起動に失敗。watch.log を見る）"
        git add "$st" && git commit -q -m "議論 ${name}：Astra の起動に失敗" && push_repo
        log "$name ${next} 返事が空"
      fi
    done
  else
    log "GitHub との同期に失敗（次の回にもう一度）"
  fi
  sleep "$INTERVAL"
done

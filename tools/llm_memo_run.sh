#!/bin/zsh -i
# メモの試し・一組（委任書 2026-10-01 夜）。世界 2 の三条件を並行に、次に世界 1 の三条件を並行に。
# 使い方  caffeinate -i zsh -i tools/llm_memo_run.sh <出力の場所> <学習の場面をここまでで止める> <世界の並び…>
# ★ 鍵は環境変数から読むだけ（ここには書かない）。費用の上限は LLM_BUDGET（帳簿の合計の上限）。
cd "$(dirname "$0")/.."
OUT=$1; STOP=$2; shift 2
for W in "$@"; do
  for C in full long short; do
    python3.12 llm_trial/memo.py "$OUT" "$W" "$C" "$STOP" > "$OUT/w${W}_${C}.log" 2>&1 &
  done
  wait
  echo "世界 $W 終わり $(date '+%H:%M')"
done
echo MEMODONE

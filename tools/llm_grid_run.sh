#!/bin/zsh -i
# メモの試し・上限の格子（予約の委任書 2026-10-01 深夜）。世界 2 の 7 系列と診断を並行に → 関門 → 通れば世界 1 の 7 系列。
# 使い方  LLM_BUDGET=<帳簿の合計の上限> caffeinate -i zsh -i tools/llm_grid_run.sh <出力の場所>
# ★ 鍵は環境変数から読むだけ（ここには書かない）。系列が途中で落ちたら、記録から続けて 3 回まで走らせ直す。
cd "$(dirname "$0")/.."
OUT=$1
mkdir -p "$OUT"
run() {
  for k in 1 2 3; do
    python3.12 llm_trial/memo_grid.py "$OUT" "$1" "$2" >> "$OUT/w$1_$2.log" 2>&1 && return 0
    echo "落ちた（$k 回目） $(date '+%H:%M:%S')" >> "$OUT/w$1_$2.log"
    sleep 30
  done
  return 1
}
CONDS=(full L1000 L400 L250 L150 L100 c150)
echo "世界 2 始め $(date '+%H:%M')"
for C in $CONDS; do run 2 "$C" & done
run 2 diag &
wait
echo "世界 2 終わり $(date '+%H:%M')"
python3.12 llm_trial/memo_grid_gate.py "$OUT" > "$OUT/関門.txt"
G=$(head -1 "$OUT/関門.txt")
echo "関門 $G $(date '+%H:%M')"
if [[ "$G" == PASS ]]; then
  for C in $CONDS; do run 1 "$C" & done
  wait
  echo "世界 1 終わり $(date '+%H:%M')"
fi
echo GRIDDONE

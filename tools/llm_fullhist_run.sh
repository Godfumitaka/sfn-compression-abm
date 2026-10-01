#!/bin/zsh -i
# 全履歴の条件の段階（委任書 2026-10-02 朝）。世界 2 で段階 1 → 2 → 3 → 4 の順に。通った段階があれば、同じ段階で世界 1 を走らせて止まる。
# 使い方  LLM_BUDGET=<帳簿の合計の上限> caffeinate -i zsh -i tools/llm_fullhist_run.sh <出力の場所>
# ★ 鍵は環境変数から読むだけ。落ちたら記録から続けて 3 回まで走らせ直す。
cd "$(dirname "$0")/.."
OUT=$1
mkdir -p "$OUT"
run() {
  for k in 1 2 3; do
    python3.12 llm_trial/fullhist_stages.py "$OUT" "$1" "$2" >> "$OUT/段階$2_w$1.log" 2>&1 && return 0
    echo "落ちた（$k 回目） $(date '+%H:%M:%S')" >> "$OUT/段階$2_w$1.log"
    sleep 30
  done
  return 1
}
for S in 1 2 3 4; do
  echo "段階 $S 世界 2 始め $(date '+%H:%M')"
  run 2 "$S" || { echo "段階 $S 世界 2 が落ちた"; break; }
  P=$(python3.12 -c "import json,sys;print(json.load(open(sys.argv[1]))['通過'])" "$OUT/段階${S}_w2_要約.json")
  echo "段階 $S 世界 2 通過 $P $(date '+%H:%M')"
  if [[ "$P" == True ]]; then
    run 1 "$S"
    P1=$(python3.12 -c "import json,sys;print(json.load(open(sys.argv[1]))['通過'])" "$OUT/段階${S}_w1_要約.json")
    echo "段階 $S 世界 1 通過 $P1 $(date '+%H:%M')"
    break
  fi
done
echo FHDONE

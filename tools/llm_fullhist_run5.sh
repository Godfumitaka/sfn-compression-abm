#!/bin/zsh -i
# LLM 大きな模型の本番の続き（2026-10-02 夕方）：組 3 の確かめ。S基準・S全部ドアを世界 2・組 3 で並行に。
# S全部ドアが関門を通ったときだけ、S全部ドアを世界 1・組 3 で一度。S全部の組 3 は走らせない。
# 使い方  LLM_BUDGET=<帳簿の合計の上限> caffeinate -i zsh -i tools/llm_fullhist_run5.sh <出力の場所>
cd "$(dirname "$0")/.."
OUT=$1
run() {   # 世界 段階 組
  for k in 1 2 3; do
    python3.12 llm_trial/fullhist_stages.py "$OUT" "$1" "$2" "$3" >> "$OUT/段階$2_w$1_組$3.log" 2>&1 && return 0
    echo "落ちた（$k 回目） $(date '+%H:%M:%S')" >> "$OUT/段階$2_w$1_組$3.log"
    sleep 30
  done
  return 1
}
summ() { python3.12 -c "import json,sys;d=json.load(open(sys.argv[1]));print(d['通過'], d['最もありそうな答えが正しい（16 問）'])" "$1"; }
echo "S基準・S全部ドア 世界 2 組 3 始め $(date '+%H:%M')"
run 2 S基準 3 &
run 2 S全部ドア 3 &
wait
echo "S基準 世界 2 組 3：$(summ "$OUT/段階S基準_w2_組3_要約.json") $(date '+%H:%M')"
P=$(summ "$OUT/段階S全部ドア_w2_組3_要約.json"); echo "S全部ドア 世界 2 組 3：$P $(date '+%H:%M')"
if [[ ${P%% *} == True ]]; then
  run 1 S全部ドア 3
  echo "S全部ドア 世界 1 組 3：$(summ "$OUT/段階S全部ドア_w1_組3_要約.json") $(date '+%H:%M')"
fi
echo FH5DONE

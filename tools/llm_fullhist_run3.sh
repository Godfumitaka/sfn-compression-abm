#!/bin/zsh -i
# 全履歴の段階 2（委任書「例外を増やす・大きな模型」2026-10-02 昼）の 1：Haiku 4.5、世界 2、新5 の条件で例外の割合 0.4・0.5（並行）。
# どちらか一つだけ通れば、組 3 で世界 2 をやり直し、通れば世界 1（組 3）。両方通ったら、どちらを確かめるかは委任書に無いので止まる。
# 使い方  LLM_BUDGET=<帳簿の合計の上限> caffeinate -i zsh -i tools/llm_fullhist_run3.sh <出力の場所>
cd "$(dirname "$0")/.."
OUT=$1
mkdir -p "$OUT"
run() {   # 世界 段階 組
  for k in 1 2 3; do
    python3.12 llm_trial/fullhist_stages.py "$OUT" "$1" "$2" "$3" >> "$OUT/段階$2_w$1_組$3.log" 2>&1 && return 0
    echo "落ちた（$k 回目） $(date '+%H:%M:%S')" >> "$OUT/段階$2_w$1_組$3.log"
    sleep 30
  done
  return 1
}
summ() { python3.12 -c "import json,sys;d=json.load(open(sys.argv[1]));print(d['通過'], d['最もありそうな答えが正しい（16 問）'])" "$1"; }
echo "例外04・例外05 世界 2 始め $(date '+%H:%M')"
run 2 例外04 1 &
run 2 例外05 1 &
wait
P4=$(summ "$OUT/段階例外04_w2_要約.json"); P5=$(summ "$OUT/段階例外05_w2_要約.json")
echo "例外04 世界 2：$P4　例外05 世界 2：$P5 $(date '+%H:%M')"
PASSED=""
[[ ${P4%% *} == True ]] && PASSED="例外04"
if [[ ${P5%% *} == True ]]; then
  if [[ -n $PASSED ]]; then echo "両方通った：どちらを組 3 で確かめるかは委任書に無いので止まる"; echo FH3DONE; exit 0; fi
  PASSED="例外05"
fi
if [[ -n $PASSED ]]; then
  echo "採用する条件：$PASSED（決めた時刻 $(date '+%Y-%m-%d %H:%M:%S')）"
  run 2 $PASSED 3
  P=$(summ "$OUT/段階${PASSED}_w2_組3_要約.json"); echo "確かめ $PASSED 世界 2 組 3：$P $(date '+%H:%M')"
  if [[ ${P%% *} == True ]]; then
    run 1 $PASSED 3
    P=$(summ "$OUT/段階${PASSED}_w1_組3_要約.json"); echo "確かめ $PASSED 世界 1 組 3：$P $(date '+%H:%M')"
  fi
else
  echo "どちらも通らなかった $(date '+%H:%M')"
fi
echo FH3DONE

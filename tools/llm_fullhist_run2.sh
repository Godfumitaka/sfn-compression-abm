#!/bin/zsh -i
# 全履歴の段階の組み直し（追記 2026-10-02 朝）。元の条件から一項目だけ変える。世界 2 で 新1→新2→新3→新4→新5 の順、通った段階で止める。
#   新1＝段階 "1"（済み）、新3＝段階 "2"（追記の前に始めたもの。走り終わるのを待って読む）、新2・新4・新5 をここで走らせる。
# 通った段階があれば、調整に使っていない組（組 3。仮の決定）で、同じ条件の 16 問を世界 2 でやり直し、15 問以上なら世界 1（組 3）でも確かめて止まる。
# 使い方  LLM_BUDGET=<帳簿の合計の上限> caffeinate -i zsh -i tools/llm_fullhist_run2.sh <出力の場所>
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
summ() {  # 要約のファイル → 通過（True/False）と、最もありそうな答えが正しい数
  python3.12 -c "import json,sys;d=json.load(open(sys.argv[1]));print(d['通過'], d['最もありそうな答えが正しい（16 問）'])" "$1"
}
PASSED=""
P=$(summ "$OUT/段階1_w2_要約.json"); echo "新1（段階 1）世界 2：$P"
[[ ${P%% *} == True ]] && PASSED=1
if [[ -z $PASSED ]]; then
  echo "新2 世界 2 始め $(date '+%H:%M')"; run 2 新2 1
  P=$(summ "$OUT/段階新2_w2_要約.json"); echo "新2 世界 2：$P $(date '+%H:%M')"
  [[ ${P%% *} == True ]] && PASSED=新2
fi
if [[ -z $PASSED ]]; then
  echo "新3（段階 2）世界 2 の終わりを待つ $(date '+%H:%M')"
  until [[ -f "$OUT/段階2_w2_要約.json" ]]; do sleep 30; done
  P=$(summ "$OUT/段階2_w2_要約.json"); echo "新3（段階 2）世界 2：$P $(date '+%H:%M')"
  [[ ${P%% *} == True ]] && PASSED=2
fi
for S in 新4 新5; do
  [[ -n $PASSED ]] && break
  echo "$S 世界 2 始め $(date '+%H:%M')"; run 2 $S 1
  P=$(summ "$OUT/段階${S}_w2_要約.json"); echo "$S 世界 2：$P $(date '+%H:%M')"
  [[ ${P%% *} == True ]] && PASSED=$S
done
if [[ -n $PASSED ]]; then
  echo "採用する条件：段階 $PASSED（決めた時刻 $(date '+%Y-%m-%d %H:%M:%S')）"
  run 2 $PASSED 3
  P=$(summ "$OUT/段階${PASSED}_w2_組3_要約.json"); echo "確かめ 段階 $PASSED 世界 2 組 3：$P $(date '+%H:%M')"
  N=${P##* }
  if (( N >= 15 )); then
    run 1 $PASSED 3
    P=$(summ "$OUT/段階${PASSED}_w1_組3_要約.json"); echo "確かめ 段階 $PASSED 世界 1 組 3：$P $(date '+%H:%M')"
  fi
else
  echo "どの段階も通らなかった $(date '+%H:%M')"
fi
echo FH2DONE

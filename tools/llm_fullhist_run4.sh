#!/bin/zsh -i
# LLM 大きな模型の本番（Sonnet 5.5・effort medium、委任書 2026-10-02 夕方）。世界 2、全履歴。
# 基準と五つの段階を、三つずつ並行に走らせる（S基準・S完全・S全部ドア → S推論・S80・S全部）。まとまりの前に、費用の残りと見積もりを比べ、足りなければ止める。
# 通った段階がちょうど一つなら、組 3 で世界 2 を一度、通れば世界 1（組 3）を一度。二つ以上通ったら、どれを確かめるかは委任書に無いので止まる。
# 使い方  LLM_BUDGET=<帳簿の合計の上限> caffeinate -i zsh -i tools/llm_fullhist_run4.sh <出力の場所>
cd "$(dirname "$0")/.."
OUT=$1
mkdir -p "$OUT"
typeset -A EST
EST=(S基準 1.3 S完全 1.4 S全部ドア 1.3 S推論 1.4 S80 3.6 S全部 4.4)   # 見積もり（ドル。費用の見積もりの報告の値に 1 割の余裕）
left() { python3.12 -c "import json,os;s=sum(json.loads(l)['cost'] for l in open(os.path.expanduser('~/llm_trial_out/費用.jsonl')));print(round(float(os.environ['LLM_BUDGET'])-s,3))"; }
need_ok() { python3.12 -c "import sys;print(1 if float(sys.argv[1])>=float(sys.argv[2]) else 0)" "$(left)" "$1"; }
run() {   # 世界 段階 組
  for k in 1 2 3; do
    python3.12 llm_trial/fullhist_stages.py "$OUT" "$1" "$2" "$3" >> "$OUT/段階$2_w$1_組$3.log" 2>&1 && return 0
    echo "落ちた（$k 回目） $(date '+%H:%M:%S')" >> "$OUT/段階$2_w$1_組$3.log"
    sleep 30
  done
  return 1
}
summ() { python3.12 -c "import json,sys;d=json.load(open(sys.argv[1]));print(d['通過'], d['最もありそうな答えが正しい（16 問）'])" "$1"; }
batch() {
  local s=0
  for S in "$@"; do s=$(python3.12 -c "print($s+${EST[$S]})"); done
  if [[ $(need_ok $s) != 1 ]]; then echo "費用の残り $(left) ドルが、次のまとまり（$*）の見積もり $s ドルに足りないので止める $(date '+%H:%M')"; echo FH4DONE; exit 0; fi
  echo "まとまり（$*）始め：残り $(left) ドル、見積もり $s ドル $(date '+%H:%M')"
  for S in "$@"; do run 2 $S 1 & done
  wait
  for S in "$@"; do echo "$S 世界 2：$(summ "$OUT/段階${S}_w2_要約.json") $(date '+%H:%M')"; done
}
batch S基準 S完全 S全部ドア
batch S推論 S80 S全部
P=()
for S in S基準 S完全 S全部ドア S推論 S80 S全部; do [[ $(summ "$OUT/段階${S}_w2_要約.json" | cut -d' ' -f1) == True ]] && P+=$S; done
if (( ${#P} == 0 )); then echo "どの段階も通らなかった $(date '+%H:%M')"; echo FH4DONE; exit 0; fi
if (( ${#P} > 1 )); then echo "二つ以上の段階が通った（${P[*]}）：どれを確かめるかは委任書に無いので止まる $(date '+%H:%M')"; echo FH4DONE; exit 0; fi
S=${P[1]}
echo "通った段階：$S（決めた時刻 $(date '+%Y-%m-%d %H:%M:%S')）"
if [[ $(need_ok ${EST[$S]}) != 1 ]]; then echo "費用の残りが組 3 の確かめの見積もりに足りないので止める"; echo FH4DONE; exit 0; fi
run 2 $S 3
P3=$(summ "$OUT/段階${S}_w2_組3_要約.json"); echo "確かめ $S 世界 2 組 3：$P3 $(date '+%H:%M')"
if [[ ${P3%% *} == True ]]; then
  if [[ $(need_ok ${EST[$S]}) != 1 ]]; then echo "費用の残りが世界 1 の確かめの見積もりに足りないので止める"; echo FH4DONE; exit 0; fi
  run 1 $S 3
  echo "確かめ $S 世界 1 組 3：$(summ "$OUT/段階${S}_w1_組3_要約.json") $(date '+%H:%M')"
fi
echo FH4DONE

#!/bin/bash
# 本番の台本（2026-09-26 夕、アストラさんの指示）。デスクトップ（WSL の Ubuntu 24.04、x86、uv の CPython 3.12.13）で、タグ v3.2-main のコードで走らせる。
#
# 並べ方（優先の高い順）。同じ段の中では、種ごとに腕を交互に入れる（途中で止まっても、どの腕も同じ種がそろう）。
#   段 1  hide・NSIM 0.8   ：新しい同化（旗 A・B・C オン、ρ＝0.5）→ ρ だけ 0（B・C オン）→ 今の同化の仕方（A・B・C オフ）
#   段 2  hide・NSIM 0.95  ：同じ三つ
#   段 3  f00・f10・NSIM 0.8：同じ三つ（種ごとに f00 の三つ、f10 の三つ）
# 共通：--nohash --vt 0.3842 --greedy（v3）・取り込みは足さない（--extend-rule none）・罰は d32・直し②（--fix2）・名前の順番の直し（--fix-order）・
#       速くする変更（--fast）・--no-public-history・--dump-slot-history（走行末の slot_history を side に書く。記録だけ）。
#       4 セル（θ′ 2.1・2.3 × 最頻・sample）・20 種（seed001〜020）。
#
# 一つの仕事 ＝（腕・種・セル）の台帳一本。v3_run.py を --seeds・--cells で一本ずつ呼ぶ。
#   ★ 走り終えた台帳（.done がある）は、この台本の側で飛ばす（v3_run.py に渡すと、side の記録を開き直して空にしてしまうため）。
#   ★ 途中で止めても、もう一度この台本を走らせれば、終わっていない台帳から続く（途中の台帳は sweep.run_one が消してから走り直す）。
#
# 使い方（リポジトリの根で）
#   PY=$(uv python find 3.12.13) OUT=~/v32main_runs JOBS=16 bash tools/run_all.sh
#   DRY=1 bash tools/run_all.sh     … 仕事の並びを書き出すだけ（走らせない）
# 変数
#   PY    Python（既定 python3.12）
#   OUT   出力の根（既定 ~/v32main_runs）。腕ごとに $OUT/<腕>/（ledgers・side・manifest.jsonl）
#   JOBS  同時に走らせる台帳の数（既定：コアの数）
#   TIERS 走らせる段（既定 "1 2 3"）
#   SEEDS・EXTRA  試しのときだけ（例 SEEDS="1" EXTRA="--trial-count 30"）。本番では付けない
set -u
cd "$(dirname "$0")/.."
PY=${PY:-python3.12}
OUT=${OUT:-$HOME/v32main_runs}
JOBS=${JOBS:-$(nproc 2>/dev/null || sysctl -n hw.ncpu)}
TIERS=${TIERS:-"1 2 3"}
DRY=${DRY:-0}
SEEDS=${SEEDS:-$(seq 1 20)}
EXTRA=${EXTRA:-}   # 試しのときだけ（例 EXTRA="--trial-count 30"）。本番では空
COMMON="--nohash --vt 0.3842 --greedy --extend-rule none --charge1 d32 --fix2 --fix-order --fast --no-public-history --dump-slot-history"
KINDS="new rho0 cur"
ident() {   # 腕の種類 → 旗（A・B・C）
  case $1 in
    new)  echo "--ident-rho 0.5 --ident-argmax --ident-commons" ;;   # 新しい同化
    rho0) echo "--ident-rho 0 --ident-argmax --ident-commons" ;;     # ρ だけ 0（B・C はオン）
    cur)  echo "" ;;                                                 # 今の同化の仕方（A・B・C オフ）
  esac
}
CELLS="2.1000:first_order 2.1000:first_order_fill-sample 2.3000:first_order 2.3000:first_order_fill-sample"
fval() { case $1 in hide) echo 0.5000;; f00) echo 0.0000;; f10) echo 1.0000;; esac; }
nname() { case $1 in 0.8) echo n80;; 0.95) echo n95;; esac; }

JOBLIST=$(mktemp)
add_jobs() {   # $1=段  $2=f の名前の並び  $3=NSIM
  local tier=$1 fs=$2 nsim=$3 s f k c th tail arm
  for s in $SEEDS; do
    for f in $fs; do
      for k in $KINDS; do
        arm="v32${k}_$(nname "$nsim")_${f}"
        for c in $CELLS; do
          th=${c%%:*}; tail=${c#*:}
          echo "$tier|$arm|$f|$nsim|$k|$s|$th|$tail" >> "$JOBLIST"
        done
      done
    done
  done
}
for t in $TIERS; do
  case $t in
    1) add_jobs 1 "hide" 0.8 ;;
    2) add_jobs 2 "hide" 0.95 ;;
    3) add_jobs 3 "f00 f10" 0.8 ;;
  esac
done

run_job() {   # 一行の仕事を走らせる（xargs から呼ぶ）
  IFS='|' read -r tier arm f nsim k s th tail <<< "$1"
  local fv; fv=$(fval "$f")
  local cfg="config/sweep_b2_${f}_s1_2026-09-22.json"
  local celldir="f${fv}_th${th}_vt0.3842_${tail}"          # 台帳の置き場所の名前（vt が入る）
  local cellarg="f${fv}_th${th}_${tail}"                    # --cells に渡す名前（vt を付けない v2 のセル名）
  local sd; sd=$(printf "seed%03d" "$s")
  local root="$OUT/$arm"
  if [[ -e "$root/ledgers/cells/$celldir/$sd.done" ]]; then
    echo "$(date '+%F %T') 飛ばす（終わっている） 段$tier $arm $celldir $sd" >> "$OUT/run_all.log"; return 0
  fi
  mkdir -p "$root" "$OUT/logs"
  local log="$OUT/logs/${arm}_${celldir}_${sd}.log"
  echo "$(date '+%F %T') 開始 段$tier $arm $celldir $sd" >> "$OUT/run_all.log"
  # shellcheck disable=SC2086
  "$PY" tools/v3_run.py "$cfg" "$root" $COMMON --nsim "$nsim" $(ident "$k") \
      --seeds "$s" --cells "$cellarg" --workers 1 --no-compare $EXTRA > "$log" 2>&1
  local rc=$?
  echo "$(date '+%F %T') 終わり rc=$rc 段$tier $arm $celldir $sd" >> "$OUT/run_all.log"
}
export -f run_job fval ident
export OUT PY COMMON EXTRA

if [[ "$DRY" == "1" ]]; then
  echo "仕事の数 $(wc -l < "$JOBLIST")（段 $TIERS）。先頭と末尾："
  head -8 "$JOBLIST"; echo "…"; tail -4 "$JOBLIST"
  echo "腕ごとの仕事の数："; cut -d'|' -f2 "$JOBLIST" | sort | uniq -c
  rm -f "$JOBLIST"; exit 0
fi

mkdir -p "$OUT"
{
  echo "開始 $(date '+%F %T')  コミット $(git rev-parse --short HEAD) $(git describe --tags --always 2>/dev/null)  未コミット $(git status --short | wc -l)"
  echo "Python $("$PY" -c 'import sys,platform;print(sys.version.split()[0], platform.machine())')  JOBS $JOBS  段 $TIERS  仕事 $(wc -l < "$JOBLIST")"
  echo "共通の旗 $COMMON  EXTRA「$EXTRA」  種 $(echo $SEEDS | tr '\n' ' ')"
} >> "$OUT/run_all.log"
tr '\n' '\0' < "$JOBLIST" | xargs -0 -P "$JOBS" -I{} bash -c 'run_job "$1"' _ {}
echo "ALLDONE $(date '+%F %T')" >> "$OUT/run_all.log"
rm -f "$JOBLIST"

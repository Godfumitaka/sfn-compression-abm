#!/bin/bash
# 本番の流れの台本（2026-09-26 夜、アストラさんの指示）。デスクトップ（WSL の Ubuntu）とマックの両方で使う。
#
# 腕の並び：ARMS の順に、腕ごとに全部（20 種 × 4 セル）を走らせてから次の腕へ。基準は 0.7（2026-09-26 夜の決定）。
#   デスクトップ（並列 14）：ARMS="new:hide rho0:hide cur:hide rho10:hide"（既定）
#   マック（並列 6）：ARMS="new:f00 new:hide new:f10"（マックの hide はデスクトップの主の hide と同じ設定。二台の分布を比べるため）
#   腕の種類：new ＝ 主（旗 A・B・C、ρ＝0.5）／rho0 ＝ ρ だけ 0（B・C オン）／cur ＝ 今の同化（A・B・C オフ）／rho10 ＝ ρ＝1.0（B・C オン）
# 台帳が一本できるたびに（tools/prod_post_one.py）：台帳を読む解析を全部かける → 本体の sha256 を控える → 台帳を消す（seed001・002 は残す）。
# ディスクの空きが MINFREE_GB（既定 20）を切ったら、新しい走行を始めずに待つ（解析と消すのは続ける）。
#   空きを見る場所 DFPATH：既定は /mnt/c があればそこ（デスクトップ：C ドライブ）、無ければ OUT。
# 腕が一つ終わるごとに（tools/prod_arm_done.py）：表と図と README を、結果のブランチ results-2026-09-27 の <機械>/<腕>/ に上げる（台帳本体は上げない）。
# 止めて走らせ直すと、終わった台帳（.done）を飛ばし、解析の済んだ台帳（POSTDONE）も飛ばして、続きから走る。
# ★ 決まりごとの検査の旗（--rename-check・--ident-shadow）は付けない。--dump-slot-history は付ける。
#
# 使い方（リポジトリの根で）
#   NSIM=0.7 JOBS=14 OUT=~/v33prod PY=$(uv python find 3.12.13) bash tools/prod_run.sh                 … デスクトップ
#   NSIM=0.7 JOBS=6 OUT=~/v33prod ARMS="new:f00 new:hide new:f10" bash tools/prod_run.sh                … マック
#   DRY=1 を付けると、仕事の並びを書き出すだけ。
# 変数
#   NSIM（必須）・JOBS（並列の数）・OUT（出力の根）・PY・ARMS・SEEDS（既定 1〜20）・MINFREE_GB（既定 20）・DFPATH・HOST（既定 hostname）
#   FIXES（直しの旗。新しいタグで決まる。既定は下）・EXTRA（試しのときだけ、例 "--trial-count 30"）・NOPUSH=1（結果を上げない）
#   RESULTS（結果のブランチの作業場所。既定 $OUT/results）
set -u
cd "$(dirname "$0")/.."
REPO=$(pwd)
PY=${PY:-python3.12}
: "${NSIM:?NSIM（基準）を渡してください（例 NSIM=0.8）}"
OUT=${OUT:-$HOME/v33prod}
JOBS=${JOBS:-6}
ARMS=${ARMS:-"new:hide rho0:hide cur:hide rho10:hide"}
SEEDS=${SEEDS:-$(seq 1 20)}
MINFREE_GB=${MINFREE_GB:-20}
if [[ -z "${DFPATH:-}" ]]; then if [[ -d /mnt/c ]]; then DFPATH=/mnt/c; else DFPATH=$OUT; fi; fi
HOST=${HOST:-$(hostname -s 2>/dev/null || hostname)}
FIXES=${FIXES:-"--fix2-full --fix-order --proj-first"}   # ★ 直し②（予測と会計にも）・名前の順番の直し・穴埋めの同点で投影を捨てない
EXTRA=${EXTRA:-}
RESULTS=${RESULTS:-$OUT/results}
DRY=${DRY:-0}
BASE="--nohash --vt 0.3842 --greedy --extend-rule none --charge1 d32 --fast --no-public-history --dump-slot-history"
CELLS="2.1000:first_order 2.1000:first_order_fill-sample 2.3000:first_order 2.3000:first_order_fill-sample"
mkdir -p "$OUT/logs"
LOG="$OUT/prod_run.log"
say() { echo "$(date '+%F %T') $*" | tee -a "$LOG"; }

ident() { case $1 in
  new)   echo "--ident-rho 0.5 --ident-argmax --ident-commons" ;;
  rho0)  echo "--ident-rho 0 --ident-argmax --ident-commons" ;;
  rho10) echo "--ident-rho 1.0 --ident-argmax --ident-commons" ;;
  cur)   echo "" ;;
  *) echo "★ 知らない腕の種類 $1" >&2; exit 2 ;;
esac; }
fval() { case $1 in hide) echo 0.5000;; f00) echo 0.0000;; f10) echo 1.0000;; f025) echo 0.2500;; esac; }
nname() { echo "n$(echo "$1" | sed 's/^0\.//; s/^\([0-9]\)$/\10/')"; }   # 0.8 → n80、0.95 → n95、0.7 → n70
freegb() { df -Pk "$DFPATH" | awk 'NR==2 {printf "%d", $4/1048576}'; }

run_job() {   # 一本：空きを待つ → 走る（.done があれば飛ばす）→ 解析・sha・消す（POSTDONE があれば飛ばす）
  IFS='|' read -r arm k f s th tail <<< "$1"
  local cfg="config/sweep_b2_${f}_s1_2026-09-22.json" fv; fv=$(fval "$f")
  local celldir="f${fv}_th${th}_vt0.3842_${tail}" cellarg="f${fv}_th${th}_${tail}" sd; sd=$(printf "seed%03d" "$s")
  local root="$OUT/$arm" log="$OUT/logs/${arm}_${celldir}_${sd}.log"
  if [[ ! -e "$root/ledgers/cells/$celldir/$sd.done" ]]; then
    while (( $(freegb) < MINFREE_GB )); do say "空き $(freegb) GB < $MINFREE_GB GB。待つ（$arm $celldir $sd）"; sleep 120; done
    say "走る $arm $celldir $sd"
    # shellcheck disable=SC2086
    "$PY" tools/v3_run.py "$cfg" "$root" $BASE $FIXES --nsim "$NSIM" $(ident "$k") \
        --seeds "$s" --cells "$cellarg" --workers 1 --no-compare $EXTRA >> "$log" 2>&1
    [[ -e "$root/ledgers/cells/$celldir/$sd.done" ]] || { say "★ 走行が終わらなかった $arm $celldir $sd（$log）"; return 0; }
  fi
  if [[ ! -e "$root/post/$celldir/$sd/POSTDONE" ]]; then
    "$PY" tools/prod_post_one.py "$root" "$arm" "$celldir" "$s" >> "$log" 2>&1 \
      && say "解析・控え・消す 済み $arm $celldir $sd" || say "★ 解析が失敗 $arm $celldir $sd（$log）"
  fi
}
export -f run_job fval ident freegb say
export OUT PY NSIM BASE FIXES EXTRA MINFREE_GB DFPATH LOG

setup_results() {   # 結果のブランチの作業場所（無ければ作る。リモートに無ければ、中身の無い枝として作る）
  [[ -e "$RESULTS/.git" ]] && return 0
  git fetch -q origin 2>/dev/null
  if git ls-remote --exit-code --heads origin results-2026-09-27 >/dev/null 2>&1; then
    git fetch -q origin results-2026-09-27 && git worktree add -q -B results-2026-09-27 "$RESULTS" origin/results-2026-09-27
  else
    git worktree add -q --detach "$RESULTS" HEAD && git -C "$RESULTS" checkout -q --orphan results-2026-09-27 \
      && git -C "$RESULTS" rm -rfq . && git -C "$RESULTS" clean -fdq && printf '# 本番の結果（2026-09-27）\n\n機械ごと・腕ごとに、表と図と README を置く。台帳本体は置かない。\n' > "$RESULTS/README.md" \
      && git -C "$RESULTS" add README.md && git -C "$RESULTS" commit -qm "結果のブランチを作る" \
      && git -C "$RESULTS" push -q origin results-2026-09-27
  fi
}

[[ -d /Users/tatsu-admin/sfn/sfn-compression-abm ]] || { echo "★ /Users/tatsu-admin/sfn/sfn-compression-abm が無い。決め打ちの解析の道具のため、リポジトリへのリンクとして作ってください（例：sudo mkdir -p /Users/tatsu-admin/sfn && sudo ln -s $REPO /Users/tatsu-admin/sfn/sfn-compression-abm）"; exit 2; }
say "開始 $HOST  コード $(git describe --tags --always) 未コミット $(git status --short | wc -l | tr -d ' ')  NSIM $NSIM  JOBS $JOBS  空き $(freegb) GB（$DFPATH、下限 $MINFREE_GB GB）"
say "腕 $ARMS"
say "旗 $BASE $FIXES --nsim $NSIM  EXTRA「$EXTRA」"
[[ "$DRY" == "1" || "${NOPUSH:-0}" == "1" ]] || setup_results
for spec in $ARMS; do
  k=${spec%%:*}; f=${spec#*:}; arm="v33${k}_$(nname "$NSIM")_${f}"
  JL=$(mktemp)
  for s in $SEEDS; do for c in $CELLS; do echo "$arm|$k|$f|$s|${c%%:*}|${c#*:}" >> "$JL"; done; done
  if [[ "$DRY" == "1" ]]; then echo "$arm：仕事 $(wc -l < "$JL" | tr -d ' ')（旗 $(ident "$k")）"; rm -f "$JL"; continue; fi
  say "腕 $arm を始める（仕事 $(wc -l < "$JL" | tr -d ' ')）"
  tr '\n' '\0' < "$JL" | xargs -0 -P "$JOBS" -I{} bash -c 'run_job "$1"' _ {}
  rm -f "$JL"
  nd=$(ls "$OUT/$arm"/post/*/seed*/POSTDONE 2>/dev/null | wc -l | tr -d ' ')
  say "腕 $arm の解析済み $nd 本"
  "$PY" tools/prod_arm_done.py "$OUT/$arm" "$arm" "$RESULTS" "$HOST" "$BASE $FIXES --nsim $NSIM $(ident "$k")" $([[ "${NOPUSH:-0}" == "1" ]] && echo --no-push) >> "$LOG" 2>&1 \
    && say "腕 $arm の表・図・README を作った（上げ先 results-2026-09-27/$HOST/$arm）" || say "★ 腕 $arm のまとめが失敗（$LOG）"
done
say "ALLDONE"

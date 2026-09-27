#!/bin/bash
# v3.6 の走らせ直しの並び（2026-09-27、control/判断_0927_1630.md）。tools/prod_v35.sh の写しで、直しの旗・腕の表・出力の置き場所の既定だけを変えた。
# 腕は v3.4・v3.5 と同じ（名前の頭を v36 にした）。直しの旗は v3.6 一式（v3.5 の --fill-norestate に --fill-pass-visible を足した）。
# 腕の表：tools/prod_v36_arms.tsv（機械ごと。上から優先。腕ごとに全部を走らせてから次の腕へ）。
# 手順は prod_day2.sh と同じ：空きの見張り → 走る（.done があれば飛ばす）→ 台帳ごとに解析・本体の sha256 の控え（POSTDONE があれば飛ばす）
#   → 腕が終わったら表・図・README を results-2026-09-27 の <機械>/<腕>/ に上げる（tools/prod_arm_done.py、上げる段は tools/results_push.py）
#   → さらに、本当に上がったかをリモートと突き合わせ、足りなければ上げ直す（tools/results_push.py を単独で呼ぶ）。
# prod_day2.sh との違い
#   ・直しの旗は v3.6 一式（--fix2-full --fix-order2 --proj-first --fill-norestate --fill-pass-visible）。
#   ・解析は走査の版 8（tools/l2scan_spoke_v8.py）、定義の表は版 8（tools/defs_table_spoke_v8.py）。種ファイルとまたぎの組の表は、腕の設定の世界から決まる。
#   ・台帳を消す決まりは表の列「残す」：all ＝ 全部残す（デスクトップの主の hide の s1・s21、マックの全部の腕）／2 ＝ その腕の最初の二つの種だけ残す。
# 使い方（リポジトリの根で。v3.6-main に固定した作業場所から）
#   MACHINE=desktop JOBS=14 OUT=~/v36prod PY=$(uv python find 3.12.13) HOST=<機械の名前> RESULTS=<結果の作業場所> bash tools/prod_v36.sh
#   MACHINE=mac JOBS=6 OUT=~/v36prod HOST=mac RESULTS=<結果の作業場所> bash tools/prod_v36.sh
#   DRY=1 を付けると、腕と仕事の数を書き出すだけ。ONLY="腕の名前 ..." で腕を絞れる。
# RESULTS（結果のブランチの作業場所）：既定 $OUT/results。results-2026-09-27 を既に別の場所（例 ~/v33prod/results）に取り出しているなら、その場所を渡す。
# 試しのときだけ：SEEDS_LIMIT=1（各腕の最初の種だけ）・CELLS_LIMIT=2（各腕の最初の 2 セルだけ）・TRIALS=25（試行数を置き換える）・NOPUSH=1・RESULTS=<結果の作業場所>
set -u
cd "$(dirname "$0")/.."
REPO=$(pwd)
PY=${PY:-python3.12}
: "${MACHINE:?MACHINE（desktop か mac）を渡してください}"
OUT=${OUT:-$HOME/v36prod}
JOBS=${JOBS:-6}
MINFREE_GB=${MINFREE_GB:-20}
if [[ -z "${DFPATH:-}" ]]; then if [[ -d /mnt/c ]]; then DFPATH=/mnt/c; else DFPATH=$OUT; fi; fi
HOST=${HOST:-$MACHINE}
FIXES=${FIXES:-"--fix2-full --fix-order2 --proj-first --fill-norestate --fill-pass-visible"}   # ★ v3.6 一式
RESULTS=${RESULTS:-$OUT/results}
DRY=${DRY:-0}; ONLY=${ONLY:-}; SEEDS_LIMIT=${SEEDS_LIMIT:-0}; CELLS_LIMIT=${CELLS_LIMIT:-0}; TRIALS=${TRIALS:-}
BASE="--nohash --vt 0.3842 --greedy --extend-rule none --charge1 d32 --fast --no-public-history --dump-slot-history"
ARMSF=${ARMSF:-tools/prod_v36_arms.tsv}
mkdir -p "$OUT/logs"
LOG="$OUT/prod_v36.log"
say() { echo "$(date '+%F %T') $*" | tee -a "$LOG"; }
ident() { case $1 in
  new)    echo "--ident-rho 0.5 --ident-argmax --ident-commons" ;;
  rho025) echo "--ident-rho 0.25 --ident-argmax --ident-commons" ;;
  rho0)   echo "--ident-rho 0 --ident-argmax --ident-commons" ;;
  rho10)  echo "--ident-rho 1.0 --ident-argmax --ident-commons" ;;
  cur)    echo "" ;;
  *) echo "★ 知らない腕の種類 $1" >&2; return 2 ;;
esac; }
freegb() { df -Pk "$DFPATH" | awk 'NR==2 {printf "%d", $4/1048576}'; }

run_job() {   # 一本：arm|cfg|nsim|kind|trials|celldir|cellarg|seed|keep
  IFS='|' read -r arm cfg nsim k trials celldir cellarg s keep <<< "$1"
  local sd; sd=$(printf "seed%03d" "$s")
  local root="$OUT/$arm" log="$OUT/logs/${arm}_${celldir}_${sd}.log" tc=""
  [[ "$trials" != "1740" ]] && tc="--trial-count $trials"
  if [[ ! -e "$root/ledgers/cells/$celldir/$sd.done" ]]; then
    while (( $(freegb) < MINFREE_GB )); do say "空き $(freegb) GB < $MINFREE_GB GB。待つ（$arm $celldir $sd）"; sleep 120; done
    say "走る $arm $celldir $sd"
    # shellcheck disable=SC2086
    "$PY" tools/v3_run.py "$cfg" "$root" $BASE $FIXES --nsim "$nsim" $(ident "$k") $tc \
        --seeds "$s" --cells "$cellarg" --workers 1 --no-compare >> "$log" 2>&1
    [[ -e "$root/ledgers/cells/$celldir/$sd.done" ]] || { say "★ 走行が終わらなかった $arm $celldir $sd（$log）"; return 0; }
  fi
  if [[ ! -e "$root/post/$celldir/$sd/POSTDONE" ]]; then
    PROD_KEEP_SEEDS="$keep" "$PY" tools/prod_post_one.py "$root" "$arm" "$celldir" "$s" >> "$log" 2>&1 \
      && say "解析・控え・消す 済み $arm $celldir $sd" || say "★ 解析が失敗 $arm $celldir $sd（$log）"
  fi
}
export -f run_job ident freegb say
export OUT PY BASE FIXES MINFREE_GB DFPATH LOG

jobs_of() {   # 腕の仕事の並び（種ごとに、セルを並べる）。セルは設定の axes から（sweep.py と同じ名前の作り方）
  "$PY" - "$@" <<'P'
import json, sys
sys.path.insert(0, ".")
import sweep
arm, cfgp, nsim, kind, trials, seeds_limit, cells_limit, keepcol = sys.argv[1:9]
cfg = json.load(open(cfgp))
ax = cfg["axes"]; cells = []
for f in ax["f"]:
    for th in ax["theta_prime"]:
        for sc in ax["repair_scope"]:
            for fill in ax.get("fill_selection", ["most_frequent"]):
                cells.append((sweep.cell_name(f, th, sc, 0.3842, fill), sweep.cell_name(f, th, sc, None, fill)))
if int(cells_limit): cells = cells[:int(cells_limit)]
seeds = list(range(cfg["seeds"]["start"], cfg["seeds"]["start"] + cfg["seeds"]["count"]))
keep = "all" if keepcol == "all" else " ".join(str(x) for x in seeds[:2])   # ★ v3.4：残す列
if int(seeds_limit): seeds = seeds[:int(seeds_limit)]
for s in seeds:
    for cd, ca in cells:
        print(f"{arm}|{cfgp}|{nsim}|{kind}|{trials}|{cd}|{ca}|{s}|{keep}")
P
}

setup_results() {
  [[ -e "$RESULTS/.git" ]] && return 0
  git fetch -q origin results-2026-09-27 && git worktree add -q -B results-2026-09-27 "$RESULTS" origin/results-2026-09-27
}

[[ -d /Users/tatsu-admin/sfn/sfn-compression-abm ]] || { echo "★ /Users/tatsu-admin/sfn/sfn-compression-abm が無い（リポジトリへのリンクとして作ってください）"; exit 2; }
say "開始 $HOST（$MACHINE）  コード $(git describe --tags --always) 未コミット $(git status --short | wc -l | tr -d ' ')  JOBS $JOBS  空き $(freegb) GB（$DFPATH）"
say "旗 $BASE $FIXES  試しの置き換え：種 ${SEEDS_LIMIT}・セル ${CELLS_LIMIT}・試行数「${TRIALS}」"
if [[ "$DRY" != "1" && "${NOPUSH:-0}" != "1" ]]; then
  setup_results || { say "★ 結果の作業場所 $RESULTS を作れなかった。results-2026-09-27 を既に取り出している作業場所があれば RESULTS=<その場所> を渡してください（git worktree list で分かる）"; exit 2; }
fi
while IFS=$'\t' read -r -u 3 mach arm cfg nsim kind trials keepc; do
  [[ -z "$mach" || "$mach" == \#* || "$mach" != "$MACHINE" ]] && continue
  [[ -n "$ONLY" && " $ONLY " != *" $arm "* ]] && continue
  ident "$kind" > /dev/null || exit 2
  [[ -e "$cfg" ]] || { say "★ 設定ファイルが無い $cfg（$arm）"; exit 2; }
  tr_=${TRIALS:-$trials}
  [[ "$keepc" == "all" || "$keepc" == "2" ]] || { say "★ 残す列が all でも 2 でもない「$keepc」（$arm）"; exit 2; }
  JL=$(mktemp); jobs_of "$arm" "$cfg" "$nsim" "$kind" "$tr_" "$SEEDS_LIMIT" "$CELLS_LIMIT" "$keepc" > "$JL"
  if [[ "$DRY" == "1" ]]; then echo "$arm：仕事 $(wc -l < "$JL" | tr -d ' ')（$cfg・基準 $nsim・$kind・試行 $tr_・残す種 $(head -1 "$JL" | cut -d'|' -f9)）"; rm -f "$JL"; continue; fi
  say "腕 $arm を始める（仕事 $(wc -l < "$JL" | tr -d ' ')、$cfg・基準 $nsim・$kind・試行 $tr_）"
  tr '\n' '\0' < "$JL" | xargs -0 -P "$JOBS" -I{} bash -c 'run_job "$1"' _ {}
  rm -f "$JL"
  say "腕 $arm の解析済み $(ls "$OUT/$arm"/post/*/seed*/POSTDONE 2>/dev/null | wc -l | tr -d ' ') 本"
  desc="$BASE $FIXES --nsim $nsim $(ident "$kind")$([[ "$tr_" != 1740 ]] && echo " --trial-count $tr_")（設定 $cfg）"
  if "$PY" tools/prod_arm_done.py "$OUT/$arm" "$arm" "$RESULTS" "$HOST" "$desc" $([[ "${NOPUSH:-0}" == "1" ]] && echo --no-push) >> "$LOG" 2>&1; then
    say "腕 $arm の表・図・README を作った（上げ先 results-2026-09-27/$HOST/$arm）"
  else
    say "★ 腕 $arm のまとめが失敗（$LOG）"
  fi
  if [[ "${NOPUSH:-0}" != "1" ]]; then   # ★ 本当に上がったかを突き合わせ、足りなければ上げ直す
    if "$PY" tools/results_push.py "$RESULTS" "$HOST" "$arm" "結果：$HOST の $arm（確かめと上げ直し）" >> "$LOG" 2>&1; then
      say "腕 $arm が results-2026-09-27 に上がっていることを確かめた"
    else
      say "★ 腕 $arm を results-2026-09-27 に上げられなかった（$LOG）"
    fi
  fi
done 3< "$ARMSF"
say "ALLDONE"

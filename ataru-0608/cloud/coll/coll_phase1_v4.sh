#!/bin/bash
# 集団化の包み（control/集団化_クラウドの包み_2026-10-09/README.md）の前半を、README の命令のとおりに行う（受け箱の指示 29・32）。
#   準備（三つの版の取り出し・check_package）→ 1 小例 → 2 OFF の全バイト比較（off2・off8）→ 3 直列と並列 → 4 の初回 on1_pilot20。
#   on1 の 200 からあとは、pilot の実測を読んで走行の係が予約を決めてから、別の台本で行う（README「空欄のまま受付しない」）。
# README からの違い（機械に GitHub の鍵を置かないため）：checkout_code は GitHub からの clone の代わりに、機械の上の既存の写し（デスクトップから束で送った）から clone する。
#   sparse-checkout の型・detach・baseline の HEAD の照合は README のとおり。JOBS は Ubuntu 版の受付表（~/jobs/jobs.py、マックの jobs.py の写し）。
#   PY は Python 3.12.13 の venv（pytest を入れた）。報告用 clone の代わりに、包みのフォルダをデスクトップから写した。
# どれかが 0 で終わらなければ、そこで止まる。STOP.json があれば以降を始めない。走行中の模型に信号は送らない。
set -euo pipefail
export PATH=$HOME/.local/bin:$PATH
export COLL_BASE=/mnt/coll_gate_20261009_4   # 指示 38：直した compare.py（115cb456…）と check_package.py（ea323cb1…）の包みで、新しい機械 i-0b585df16ce1a4c42 の新しい場所で最初から（_3 は check_package の合成の台帳が古い欄名で止まった。消さずに残した）
export RESULTS=/mnt/results-coll-gate
export JOBS="$HOME/jobs/jobs.py"
export PY=$COLL_BASE/env/bin/python
export PKG="$RESULTS/control/集団化_クラウドの包み_2026-10-09"
export CANDIDATE="$COLL_BASE/source-c4"
export BASELINE="$COLL_BASE/source-c55"
export PREPARATION="$COLL_BASE/source-e9"
export RUN="$COLL_BASE/run-same-host"
export PYTHONDONTWRITEBYTECODE=1
export PYTHONHASHSEED=0
unset LANG LC_ALL LC_CTYPE || true
say() { echo "$(date '+%F %T') $*"; }
test -f "$JOBS"
test ! -e "$RUN"
mkdir -p "$COLL_BASE"
[ -x "$PY" ] || { python3.12 -m venv $COLL_BASE/env && $COLL_BASE/env/bin/python -m pip -q install pytest; }
mkdir "$RUN"
"$PY" -c 'import sys,pytest; assert sys.version_info[:2]==(3,12); print(sys.version,pytest.__version__)'
ST=$("$PY" "$JOBS" status); echo "$ST" | sed -n 1,3p
df -h "$COLL_BASE"
cd "$PKG"
sha256sum -c SHA256SUMS
checkout_code () {
  git clone -q --no-checkout $HOME/sfn/sfn-compression-abm "$1" || return
  git -C "$1" sparse-checkout set --no-cone '/abm/' '/tools/' '/tests/' '/*.py' '/AGENTS.md' '/SPEC.md' '/pyproject.toml' || return
  git -C "$1" checkout -q --detach "$2"
}
checkout_code "$CANDIDATE" c4cfed12a3944071951775b2c9373ca27705fb25
checkout_code "$BASELINE" c55b8c1a62b04002413686b0405bc1960fa8d6b9
test "$(git -C "$BASELINE" rev-parse HEAD)" = c55b8c1a62b04002413686b0405bc1960fa8d6b9
test "$(git -C "$BASELINE" rev-parse HEAD^{tree})" = abfe2c67a4be1908fdcf1f80fd0be9a68e978fed
checkout_code "$PREPARATION" e9ed84ae3ee6c458f392cd58cadf9fc030639900
test "$(git -C "$CANDIDATE" rev-parse HEAD)" = c4cfed12a3944071951775b2c9373ca27705fb25
test "$(git -C "$PREPARATION" rev-parse HEAD)" = e9ed84ae3ee6c458f392cd58cadf9fc030639900
"$PY" "$PKG/check_package.py" --candidate "$CANDIDATE" --baseline "$BASELINE" --preparation "$PREPARATION" --fixtures "$RUN/package-checks"
say "準備が済んだ"
# 受付表の条件 2（スワップの記録が直近 10 分ぶん）がそろうまで待つ（確認の記録は 10 分だけ有効なので、受付の待ちで古くならないように）
until "$PY" -c "import sys;sys.path.insert(0,'$HOME/jobs');import jobs;sys.exit(0 if jobs.swap_ok()[0] else 1)"; do sleep 30; done
export EXISTING_GB=0   # この機械は集団化だけの専用機。受付表の予約が 0 であることを、各本の前に確かめる
run_one () {
  name="$1"; source_dir="$2"; mem_gb="$3"; measured_resource="$4"; memory_note="$5"
  [ -e "$RUN/STOP.json" ] && { say "STOP.json があるので $name を始めない"; return 1; }
  ST=$("$PY" "$JOBS" status); [[ "$ST" == *"見込みの合計 0.0 /"* ]] || { say "受付表に他の予約がある。EXISTING_GB=0 にしない"; return 1; }
  record="$RUN/clearance-$name.json"
  if [ -n "$measured_resource" ]; then
    "$PY" "$PKG/clearance.py" "$name" --root "$RUN" --source "$source_dir" --jobs "$JOBS" --mem "$mem_gb" --existing-gb "$EXISTING_GB" --resource-file "$measured_resource" --memory-note "$memory_note" --no-resource-warning --record "$record" || return
  else
    "$PY" "$PKG/clearance.py" "$name" --root "$RUN" --source "$source_dir" --jobs "$JOBS" --mem "$mem_gb" --existing-gb "$EXISTING_GB" --memory-note "$memory_note" --no-resource-warning --record "$record" || return
  fi
  say "始める $name"
  "$PY" "$PKG/run.py" run "$name" --source "$source_dir" --root "$RUN" --jobs "$JOBS" --mem "$mem_gb" --clearance "$record"
  say "終わった $name"
}
say "1 小例"; "$PY" "$PKG/components.py" run --source "$CANDIDATE" --root "$RUN" --jobs "$JOBS"
say "2 OFF"
run_one off2_baseline200 "$BASELINE" 1 "" "既存の二体OFFの実測と1GB予約"
run_one off2_candidate200 "$CANDIDATE" 1 "" "同じOFF・世界・種・旗、三メタデータ検査"
"$PY" "$PKG/compare.py" "$RUN" off2
run_one off8_baseline200 "$BASELINE" 2 "" "既存の八体OFFの実測と2GB予約"
run_one off8_candidate200 "$CANDIDATE" 2 "" "同じOFF・世界・種・旗、三メタデータ検査"
"$PY" "$PKG/compare.py" "$RUN" off8
say "3 直列と並列"
run_one off8_parallel200 "$CANDIDATE" 2 "" "OFF8の直列との比較。並列のRSS合計は実測で記録"
"$PY" "$PKG/compare.py" "$RUN" off8-parallel
say "4 の初回 on1_pilot20"
export PILOT_MEM=1
run_one on1_pilot20 "$CANDIDATE" "$PILOT_MEM" "" "初回20だけ。上流ON20のRSS約63MBを参考、移植後は未測定・後続予約へ直接流用しない"
cat "$RUN/evidence/on1_pilot20/resource.json"
say "ALLDONE phase1（on1 の 200 からあとは、予約を決めてから）"

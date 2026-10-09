#!/bin/bash
# 集団化の包みの「4 一体 ON と e9 の独立単独」（README の命令のとおり）。前半（coll_phase1_v4.sh）の続きで、同じ機械・同じ RUN。元の説明：前半を、README の命令のとおりに行う（受け箱の指示 29・32）。
#   準備（三つの版の取り出し・check_package）→ 1 小例 → 2 OFF の全バイト比較（off2・off8）→ 3 直列と並列 → 4 の初回 on1_pilot20。
#   on1 の 200 からあとは、pilot の実測を読んで走行の係が予約を決めてから、別の台本で行う（README「空欄のまま受付しない」）。
# README からの違い（機械に GitHub の鍵を置かないため）：checkout_code は GitHub からの clone の代わりに、機械の上の既存の写し（デスクトップから束で送った）から clone する。
#   sparse-checkout の型・detach・baseline の HEAD の照合は README のとおり。JOBS は Ubuntu 版の受付表（~/jobs/jobs.py、マックの jobs.py の写し）。
#   PY は Python 3.12.13 の venv（pytest を入れた）。報告用 clone の代わりに、包みのフォルダをデスクトップから写した。
# どれかが 0 で終わらなければ、そこで止まる。STOP.json があれば以降を始めない。走行中の模型に信号は送らない。
set -euo pipefail
export PATH=$HOME/.local/bin:$PATH
export COLL_BASE=/mnt/coll_gate_gcp
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
mkdir -p "$COLL_BASE"
[ -x "$PY" ] || { python3.12 -m venv $COLL_BASE/env && $COLL_BASE/env/bin/python -m pip -q install pytest; }
test -d "$RUN"
"$PY" -c 'import sys,pytest; assert sys.version_info[:2]==(3,12); print(sys.version,pytest.__version__)'
ST=$("$PY" "$JOBS" status); echo "$ST" | sed -n 1,3p
df -h "$COLL_BASE"
cd "$PKG"
sha256sum -c SHA256SUMS
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
say "4 一体 ON（200）"
# ON1_MEM は走行の係が決めた予約（README「pilot の実測を読んで余裕と条件差を明記し、1.2×観測 RSS 以上・24GB 以内」）。
# pilot20 の RSS の合計の最大は 271,265,792 バイト（0.27GB）。20→200 の成長は未測定なので、約 15 倍の 4GB にした（24GB の 6 分の 1、専用機で他の予約なし）。
export ON1_MEM=4
run_one on1_f0.1_collective200 "$CANDIDATE" "${ON1_MEM:?pilotの実測と条件差から記入}" "$RUN/evidence/on1_pilot20/resource.json" "一体200。pilot20の実測RSS 0.27GBに対し、20→200の成長が未測定のため約15倍の4GB（1.2倍の下限0.33GBより大きく、24GBの6分の1）"
run_one on1_f0.1_independent200 "$PREPARATION" "$ON1_MEM" "$RUN/evidence/on1_f0.1_collective200/resource.json" "同じf0.1・200の一体実測と余裕。e9の独立単独で、集団一体の実測を根拠に同じ4GB"
"$PY" "$PKG/compare.py" "$RUN" on1-f0.1
run_one on1_f0.9_collective200 "$CANDIDATE" "$ON1_MEM" "$RUN/evidence/on1_f0.1_collective200/resource.json" "f0.9の条件差（f0.1の一体200の実測を根拠）と余裕。同じ4GB"
run_one on1_f0.9_independent200 "$PREPARATION" "$ON1_MEM" "$RUN/evidence/on1_f0.9_collective200/resource.json" "同じf0.9・200の一体実測と余裕。同じ4GB"
"$PY" "$PKG/compare.py" "$RUN" on1-f0.9
for n in on1_f0.1_collective200 on1_f0.1_independent200 on1_f0.9_collective200 on1_f0.9_independent200; do cat "$RUN/evidence/$n/resource.json"; done
say "ALLDONE phase2（on2 からあとは、一体 200 の実測を読んで予約を決めてから）"

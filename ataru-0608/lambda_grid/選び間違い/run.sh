#!/bin/bash
# λ を細かく振った 8 腕に、マックの選び間違いの分類（spc-analysis-2026-10-01、0c3646b の tools/sealmem.py・selcands.py）を当てる。記録を読むだけ。
set -u
cd $HOME/sfn/audit/_read/spcana
PY=/home/tatsu/.local/share/uv/python/cpython-3.12.13-linux-x86_64-gnu/bin/python3.12
export TMPDIR=$HOME/lgrid_sel/作業 SM_WORKERS=8 SC_WORKERS=8
L=$HOME/lgrid_sel/run.log
for d in $HOME/lgrid_view/lg_w2_*; do
  a=$(basename $d)
  [ -f $HOME/lgrid_sel/sealmem/$a/checks.json ] || { echo "== sealmem $a $(date +%T)" >> $L; nice -n 10 $PY tools/sealmem.py $HOME/lgrid_sel/sealmem $d >> $L 2>&1; }
  echo "== selcands $a $(date +%T)" >> $L
  nice -n 10 $PY tools/selcands.py $HOME/lgrid_sel/selcands $d $HOME/lgrid_sel/sealmem >> $L 2>&1 || echo "FAILED $a" >> $L
done
echo "== DONE $(date +%T)" >> $L

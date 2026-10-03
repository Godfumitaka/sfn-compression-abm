#!/bin/bash
# D（~/ufprod/full/uf_w2_t0.4）の例外の日のドアの外れの分類。記録を読むだけ。並列 2（走行の邪魔にならないように）。
set -u
A=$HOME/ufprod/full/uf_w2_t0.4; V=$HOME/dsel_view/uf_w2_t0.4; O=$HOME/dsel_out; mkdir -p $V $O/作業
ln -sfn $A/ledgers $V/ledgers; cp $A/flag.json $A/manifest.jsonl $V/
for c in $A/side/*/; do cn=$(basename $c); mkdir -p $V/side/$cn; for f in $c/*; do b=$(basename $f); case $b in *.gz) zcat $f > $V/side/$cn/${b%.gz};; *) ln -sfn $f $V/side/$cn/$b;; esac; done; done
cd $HOME/sfn/audit/_dev/n3sel
PY=/home/tatsu/.local/share/uv/python/cpython-3.12.13-linux-x86_64-gnu/bin/python3.12
export TMPDIR=$O/作業 SM_WORKERS=2 SC_WORKERS=2
echo "== 始め $(date +%T)" >> $O/run.log
nice -n 15 $PY tools/sealmem.py $O/sealmem $V >> $O/run.log 2>&1 || echo "FAILED sealmem" >> $O/run.log
nice -n 15 $PY tools/selcands.py $O/selcands $V $O/sealmem >> $O/run.log 2>&1 || echo "FAILED selcands" >> $O/run.log
echo "== DONE $(date +%T)" >> $O/run.log

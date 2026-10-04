#!/bin/bash
# 受付表の確かめ（2026-10-04、段 2）。試しの表（JOBS_DIR）と作ったスワップの記録（JOBS_SWAP）だけを使う。本物の ~/jobs/registry.tsv は触らない。
# 今動いている表に無い重い処理の「もとの処理」は、条件 4 以外を確かめるため、試しの表にだけ 0 GB で書く（その処理には何もしない）。
S=${1:?試しの場所}; rm -rf "$S"; mkdir -p "$S"; cd "$S"
J="python3 $HOME/jobs/jobs.py"
now=$(date +%s)
for i in $(seq 12 -1 0); do printf "%s\t356.19\tx\tok\tNone\n" $((now-i*60)); done > swap_flat.tsv
for i in $(seq 12 -1 0); do printf "%s\t%s.0\tx\tok\tNone\n" $((now-i*60)) $((356+(12-i)*10)); done > swap_up.tsv
for i in 2 1 0; do printf "%s\t356.19\tx\tok\tNone\n" $((now-i*60)); done > swap_short.tsv
ROOTS=$($J status | grep "もとの処理 PID" | sed 's/.*もとの処理 PID \([0-9]*\)：.*/\1/' | sort -u | tr '\n' ' ')
mkreg() { mkdir -p "$1"; { printf "pid\towner\tmem_gb\tstart\tcmd\n"; for p in $ROOTS; do printf "%s\t既存（試しの表だけ）\t0\tx\tx\n" $p; done; } > "$1/registry.tsv"; }
sleep 900 & SL=$!
echo "既存の重い処理のもと：$ROOTS／試しの sleep：$SL"
echo "== T1 予算超え（表に 20 GB の行、新しい処理 5.2 GB）"; mkreg t1; printf "%s\t試し\t20\tx\tsleep\n" $SL >> t1/registry.tsv
JOBS_DIR=$S/t1 JOBS_SWAP=$S/swap_flat.tsv $J claim --owner 試し --kind sme --pid $$; echo "戻り値 $?"
echo "== T2 表に無い重い処理（200 MB を持つ Python）"; python3 -c "import time; a=bytearray(200*1024*1024); time.sleep(120)" & HP=$!; sleep 3; echo "その PID：$HP"
mkreg t2; JOBS_DIR=$S/t2 JOBS_SWAP=$S/swap_flat.tsv $J claim --owner 試し --mem 1 --pid $SL; echo "戻り値 $?"; kill $HP
echo "== T3 死んだ PID の行（99999、3 GB）"; kill -0 99999 2>/dev/null && echo "★ 99999 は生きている（試しにならない）"; mkreg t3; printf "99999\t死んだ試し\t3\tx\tx\n" >> t3/registry.tsv
JOBS_DIR=$S/t3 JOBS_SWAP=$S/swap_flat.tsv $J status | head -3; echo "status のあとの表："; cut -f1-3 t3/registry.tsv
echo "== T4 スワップが増えた（10 分で 356→476 MB）"; mkreg t4; JOBS_DIR=$S/t4 JOBS_SWAP=$S/swap_up.tsv $J claim --owner 試し --mem 1 --pid $SL; echo "戻り値 $?"
echo "== T5 スワップの記録が 10 分に満たない"; mkreg t5; JOBS_DIR=$S/t5 JOBS_SWAP=$S/swap_short.tsv $J claim --owner 試し --mem 1 --pid $SL; echo "戻り値 $?"
echo "== T6 条件を全部満たす → 受け付け → release で消える"; mkreg t6; JOBS_DIR=$S/t6 JOBS_SWAP=$S/swap_flat.tsv $J claim --owner 試し --mem 1 --pid $SL; echo "戻り値 $?"
echo "表に $SL の行：$(grep -c "^$SL	" t6/registry.tsv)"; JOBS_DIR=$S/t6 JOBS_SWAP=$S/swap_flat.tsv $J release --pid $SL; echo "release 後の $SL の行：$(grep -c "^$SL	" t6/registry.tsv)"
echo "== T7 同じ PID の二重の登録"; mkreg t7; printf "%s\t試し\t1\tx\tsleep\n" $SL >> t7/registry.tsv; JOBS_DIR=$S/t7 JOBS_SWAP=$S/swap_flat.tsv $J claim --owner 試し --mem 1 --pid $SL; echo "戻り値 $?"
echo "== T8 run（claim → 実行 → release）"; mkreg t8; JOBS_DIR=$S/t8 JOBS_SWAP=$S/swap_flat.tsv $J run --owner 試し --kind v3run -- /bin/echo 実行した; echo "戻り値 $?"; echo "終わったあとの表の行（見出しを除く）："; tail -n +2 t8/registry.tsv | cut -f1-3
echo "== T9 見込みが決まらない（--kind も --mem も無い）"; mkreg t9; JOBS_DIR=$S/t9 JOBS_SWAP=$S/swap_flat.tsv $J claim --owner 試し --pid $SL; echo "戻り値 $?"
kill $SL

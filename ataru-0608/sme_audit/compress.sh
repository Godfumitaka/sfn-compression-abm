#!/bin/bash
# 段 0：古い走行の記録を gzip で縮める（2026-10-03 夜の委任書）。縮める前の中身の sha256 と、縮めたものを展開した中身の sha256 が一致することを確かめてから、元を置き換える。
L=$HOME/gz_log/compress.tsv; echo -e "path\tbytes_before\tbytes_after\tsha256_before\tsha256_after_unzip\tok" > $L
while read -r size p; do
  f=$HOME/${p#./}
  [ -f "$f" ] || continue
  h1=$(sha256sum < "$f" | cut -d' ' -f1)
  nice -n 15 gzip -k -n -6 "$f" || { echo -e "$f\t$size\t\t$h1\t\tgzip失敗" >> $L; continue; }
  h2=$(zcat "$f.gz" | sha256sum | cut -d' ' -f1)
  if [ "$h1" == "$h2" ]; then a=$(stat -c %s "$f.gz"); rm "$f"; echo -e "$f\t$size\t$a\t$h1\t$h2\t1" >> $L
  else rm -f "$f.gz"; echo -e "$f\t$size\t\t$h1\t$h2\t0（元を残した）" >> $L; fi
done < /tmp/claude-1000/-home-tatsu-sfn/46945c76-63c2-47d5-81fa-9b12440cb938/scratchpad/gz_cands.txt
echo DONE >> $HOME/gz_log/done

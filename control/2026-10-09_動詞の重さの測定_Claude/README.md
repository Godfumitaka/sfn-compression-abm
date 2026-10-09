# 動詞の重さの測定（Claude、10/9）

- 版：動詞の speed_logfix（81477b5bd56b1a48efcebf43bfb43fd7b6c8d2a9、指示 15 の bundle を検証して取り出した）。旗は #19 の命令の下書き（command_drafts/19_seed001.json）のまま。--match-eps 0、--v39-price 0.00035129738499384776（cmd19.json）。
- 走らせ方：drive.py.txt（v3_run を同じ過程の中で、先頭 N 試行だけ走らせる。模型は変えない）。Linux・4 芯・python3.12。
- py-spy 20 試行（spy20_summary.txt）：98% が出生の仮の問い（stage2 initial）。その約半分が probeworld._snapshot_modules・_restore_modules。
- 写しの中身（snapprobe.py.txt、snap6b.json）：6 試行 247 秒のうち、verbworld.INFO 60 秒・verbworld.IDS 56 秒。
- 試し（fastsnap.py.txt）：INFO・IDS だけを長さで控える。8 試行で 418.8 秒 → 187.6 秒。模型の出力は全バイト一致（第二段は秒の欄を除いて一致）。確かめの形で 4 試行・30,358 回、違い 0。
- 注意：snapprobe の最初の版は、一覧（SNAP_MODULES・SNAP_ATTRS）を読み込み時に固定していて、走行中に足された辞書を写していなかった（その計測は無効）。今の版は毎回読む。

# 動詞の重さの測定（Claude、10/9）

- 版：動詞の speed_logfix（81477b5bd56b1a48efcebf43bfb43fd7b6c8d2a9、指示 15 の bundle を検証して取り出した）。旗は #19 の命令の下書き（command_drafts/19_seed001.json）のまま。--match-eps 0、--v39-price 0.00035129738499384776（cmd19.json）。
- 走らせ方：drive.py.txt（v3_run を同じ過程の中で、先頭 N 試行だけ走らせる。模型は変えない）。Linux・4 芯・python3.12。
- py-spy 20 試行（spy20_summary.txt）：98% が出生の仮の問い（stage2 initial）。その約半分が probeworld._snapshot_modules・_restore_modules。
- 写しの中身（snapprobe.py.txt、snap6b.json）：6 試行 247 秒のうち、verbworld.INFO 60 秒・verbworld.IDS 56 秒。
- 試し（fastsnap.py.txt）：INFO・IDS だけを長さで控える。8 試行で 418.8 秒 → 187.6 秒。模型の出力は全バイト一致（第二段は秒の欄を除いて一致）。確かめの形で 4 試行・30,358 回、違い 0。
- 注意：snapprobe の最初の版は、一覧（SNAP_MODULES・SNAP_ATTRS）を読み込み時に固定していて、走行中に足された辞書を写していなかった（その計測は無効）。今の版は毎回読む。

## 出生の問いを同時に解く試作（10/9 夜、birthpar.py.txt）

- 一回の出生の問い（19〜20 問）を、fork の子の過程 4 つで同時に解き、親が元の順番で足し合わせる。子の中で書かれる rematch の記録は、子で控えて親が同じ順で書き直す。fastsnap（INFO・IDS）と一緒に 8 試行。
- 結果：実時間 418.8 秒 → 54.2 秒（約 7.7 倍、4 芯）。模型の出力（台帳・side 全部・注意・追い出し・試験）は全バイト一致。第二段の主・initial・rematch・二つの summary は秒の欄を除いて一致。
- 違いは manifest の研究者の数え（strictpc.reasons・use_calls・use_dropped、v39.L_unseen_name）だけ。これは isolated() の中から数えが漏れる既知の癖（下調べの 5）で、子に分けると漏れの分が消える。正式版は、子の数えの増えを親で足して再現する必要がある。
- 試作で踏んだ落とし穴：(1) 子の中で元の書き出し口（gzip）への参照を手放すと、子の中で閉じられて親のファイルを壊す。(2) 子の過程は複数の問いを順に解くので、控えは問いごとに新しくする。

# log Pの主の条件（マック、160本）

数と事実を記録する。

## 準備：2026-10-06T12:39:54.300611+09:00

委任書33を受領。使用版はcodex/sme-evict-logp-2026-10-06、1838256b3fa9f81737d8b210e6ccb59c9d638a25。log Pは保持の採点を確率の符号長にする旗で、E（新規か同化かの判断）のlog P旗は入れない。internは同じ不変の実体を共有する旗、evictは前の試行で終わった控えを次の試行で除く旗。

デスクトップの元の160命令（desktop_plan_01）と、resultsのgate200_command.json・intern_gate_jobs.json・本番報告を照合。共通の旗と値は全8条件で一致。世界・λ・C/Dの旗の相違は元の8条件の命令のまま。追加は下表の3旗だけ。命令と旗の全一覧は添付sme.commands.jsonとflags_matrix.json。workerは各本1。種21〜40は読まない・走らせない。

|順|条件|世界|忘れる値段|保持の追加旗|マックで足す旗|
|---:|---|---:|---:|---|---|
|1|w2_A_L50|2|0.01873710622997919|なし|--score-logp --sme-intern-cache --sme-evict-trial-cache|
|2|w1_A_L50|1|0.01873710622997919|なし|--score-logp --sme-intern-cache --sme-evict-trial-cache|
|3|w2_D_tau04|2|0.01873710622997919|--use-forget 0.4|--score-logp --sme-intern-cache --sme-evict-trial-cache|
|4|w1_D_tau04|1|0.01873710622997919|--use-forget 0.4|--score-logp --sme-intern-cache --sme-evict-trial-cache|
|5|w2_A_zero|2|0|なし|--score-logp --sme-intern-cache --sme-evict-trial-cache|
|6|w1_A_zero|1|0|なし|--score-logp --sme-intern-cache --sme-evict-trial-cache|
|7|w2_C_L50|2|0.01873710622997919|--cf-learn|--score-logp --sme-intern-cache --sme-evict-trial-cache|
|8|w1_C_L50|1|0.01873710622997919|--cf-learn|--score-logp --sme-intern-cache --sme-evict-trial-cache|

各条件1740試行×種1〜20。条件をこの順に完了させる。L50は0.01873710622997919。--e-priceは全部この値、--horizonは1740、--score-logp-e・reuse・prune・墓石の検査旗は本番に入れない。全条件をマックで走らせる。

結果を見る前の予想P-06f〜iを、origin/results-2026-09-27のdf028e4cから読み取り、参照のコミット・sha256をreference_files.jsonへ記録。予想の判定や結果の良し悪しは書かない。

マックは10コア、全体の上限8コア。12:37 JSTの受付は別作業8GB（4体の処理）、スワップ188MB・直近10分増加なし、熱警告なし、空き314.4GiB。jobs.py run --wait --mem --disk-pathで受付し、CPUの空きも別に確認。開始の空き20GiB以上、走行中18.5GiB未満・熱警告・スワップ増加で自分の処理だけ止める。

完了済み1838256のvanilla_01/Lは、w2_A_L50・種1の全旗・値と一致した。二重走行をせず、この記録をL_B_s01と直接比較する。関門通過まで残り159本を始めない。全台帳・side・保存状態を残す。

25番の旧intern計測を自分の処理だけ停止し、途中記録を保持。33番の後、10cd8bdで新しい計測を行う。


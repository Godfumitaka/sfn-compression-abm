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


## 関門：2026-10-06T12:40:39.075659+09:00

w2_A_L50・種1（1838256、完了済みvanilla_01/L）を、旧L_B_s01（da3521bf）と直接比較。全1740試行、台帳本体・全side・保存状態の7ファイルが全バイト一致。控えを捨てた鍵のevictions記録は別の追加記録として保持。台帳の見出し1行と許可済みの実測sec_trialの数値だけを比較から除外する。実際にはこのAの記録にsec_trialの相違は無い。

|ファイル|一致|比較したsha256|
|---|---|---|
|ledgers/cells/f0.5000_th2.1000_vt0.3842_first_order/seed001.jsonl.gz|一致|b49614183ada8c37565101d5d3c84fd7749e38cfcfc87fac30664702a68a46ef|
|side/f0.5000_th2.1000_vt0.3842_first_order/seed001.answers.csv|一致|9009b2e7356b28dd241d5c28875b63b561e3cf4aa8bdfe0e612c030d5336f30c|
|side/f0.5000_th2.1000_vt0.3842_first_order/seed001.jsonl|一致|5a7d45e610d860a884385c73e4d090aaae158a2c429cdef8e7cc134a17740fcf|
|side/f0.5000_th2.1000_vt0.3842_first_order/seed001.routing.jsonl|一致|fe0dc596bef520a62b4f4865b75e146551ae19dd57a92efc2ede9ed138e47cc8|
|side/f0.5000_th2.1000_vt0.3842_first_order/seed001.shop.jsonl|一致|f0a56545bffe6cdc0dd757bec073b32d2a385c10ef5925ecd7116d9ac3dfcf0d|
|side/f0.5000_th2.1000_vt0.3842_first_order/seed001.sme.jsonl.gz|一致|a886083b5b9f2e02355b68793ee9ee83a1e099fdd4b2d444a1d415598ad781e4|
|side/f0.5000_th2.1000_vt0.3842_first_order/seed001.sme.states.jsonl.gz|一致|b9301bc7a6a7c602fbdd7ef5cf4db89d913fe0c09d4ed9245429e1f524d3bfa2|

種1の既存のselcands_sme再解析も、入力の台帳・全side・保存状態が一致したため利用し、同じ表を作る。残りの種は1838256で走行し、その保存状態をselcands_sme.pyで再解析する。再生の不一致があれば後続へ進まずに報告。


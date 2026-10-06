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


## 開始：2026-10-06T12:47:12.347589+09:00

関門通過後、12:46 JSTにw2_A_L50の種2・種3を受付に通して開始。種の番号の順に開始し、条件順を保持。受付の見込みは各本2GB（控え削除の既存実測349.7MBに余裕を付けた値）。進行台本は自分の場所で動き、全体8コアの空き、熱、スワップ、ディスク、受付を監視する。最大3本を自分の台本で並べるが、他の処理によって減らす。既存の他の処理は停止しない。

種1の集計は、全1740試行の予測と候補の再生の不一致0。誕生の席と記憶量を含む表は以下。

全課題を分母とした数。ドア課題の数は続く別表に示す。

|日|全課題数|正解|外れ|黙り|選び間違い|区別の喪失|
|---|---:|---:|---:|---:|---:|---:|
|例外|324|196|1|127|1|0|
|通常|1416|966|1|449|1|0|

|日|ドア課題数|正解|外れ|黙り|選び間違い|区別の喪失|
|---|---:|---:|---:|---:|---:|---:|
|例外|33|28|1|4|1|0|
|通常|124|122|1|1|1|0|

|基の材料の日|今の材料の日|誕生数|シール席あり定義数|登録直後F/H/U|同試行の忘却後F/H/U|同試行に退役|
|---|---|---:|---:|---|---|---:|
|e|e|14|14|14/0/0|14/0/0|0|
|n|e|1|0|0/0/0|0/0/0|0|
|n|n|13|13|13/0/0|13/0/0|0|

材料の日のeは例外、nは通常。登録直後はregistration_event、忘却後は同じ試行のsme.statesのpostを使用。
全1740試行の記憶総ビット（v39のbits_after）の平均7838.979310、最後6873。定義数の平均15.189655、最後11。

種1の走行の実時間480.879435秒、模型の秒478.81、最大常駐349.7MB。いずれも既存の1838256の観測なしの走行。CPUの空き待ちを含む今回の集計時間とは別。

試行表は元の0起点のprediction_orderをtrial列に保持し、trial_numberに1起点の番号を別記。追加CSVの初回に1起点で結合してKeyErrorとなったので、元の番号で結合するように作業用の集計台本を修正。模型・記録・分類の定義は変更していない。最初の読み取り集計のCPU一時停止・再開をbootstrap_cpu_pause.jsonとbootstrap_cpu_events.jsonlに記録。

台帳・side・保存状態は元の出力先をそのまま保持。再利用の理由と実際の命令はreused_record.json・actual_command.jsonに記録。残りの159本はこの出力場所の各種のoutputに保存。各本が完了したら、試行表・全出力のsha256・分類・誕生のシールの席・記憶量を作る。条件が全部そろった時点で20種の表を追記し通常push。


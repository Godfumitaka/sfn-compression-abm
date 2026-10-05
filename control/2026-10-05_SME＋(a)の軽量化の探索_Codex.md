# SME＋(a)の軽量化の探索

数と事実だけを記録する。

## receipt：2026-10-05T18:51:20.549234+09:00

受領。既存の(a) C_off/C_on、log Pの残りと比較の種、段2のkey/combinedは継続し、本番は走らせない。作業場所codex_sme_amemory_2026-10-05に自分の二つの複製と別の枝を作成。土台は858f708とda3521bf。abm/・f・式・値・世界は変更しない。

常駐量は、その処理がメモリに置いている量。最大常駐はその走行中の最大値。log Pは保持の採点を−log₂Pのビットの費用にする旗。同点規則(a)は同じ点の候補を呼び出しごとの種で一様に選ぶ旗。

|記録|実時間 秒|模型の記録 秒|最大常駐 MB|測定の条件|
|---|---:|---:|---:|---|
|A_on・種1・1740試行|6707.392128|6341.65|7697.8|外部observe.pyで毎試行の控えの種の印と終わりの照合の状態も保存|
|log P・種1・1740試行|6088.593148|6075.18|4918.0|外部の追加観測なし|

A_onの100試行ごとの推移は既存performance.jsonlから取れる。log Pの既存記録にはその推移が無いため追加で測る。上の二本は観測条件が違い、この二値だけから軽量化の倍率を出さない。200試行からのlog Pの7.1GBの見込みは受付に使った見込みであり、全走行の最大常駐の実測は4918.0MB。

前のreuse/pruneの1740試行の一致の範囲は台帳本体。省いた呼び出しをsideに別記することが許可されていた。今回の台帳本体・side・保存状態・同点の乱数の全バイト一致は新しい関門として扱う。除外は見出し一行と実測sec_trialだけ。不一致の変更を採用しない。大きい状態は自分の出力に保持し、結果枝にはsha256と小さい表だけを写す。


## stage1_initial：2026-10-05T19:00:27.418115+09:00

既存A_onの100試行ごとの時間・最大常駐と、照合の実行回数を18区間で書き出した。試行の番号は元の記録どおり0から1739。log Pの同じ推移は未記録のため空欄とし、二つの土台を変更せず外部の観測を付けた200試行の受付を待っている。200試行の既存最大は523MB、区分別の走査の補助領域を含め予約2GB。受付表が拒んだため開始していない。

追加観測は、控え→自己の点→控えの乱数→RESULTS→GRAPHS→CHOICES→STATS→逐語の記憶→定義→残るエージェント状態の順に、同じ実体を二重に数えずPythonの保持領域を数える。これはRSSの全量ではなく、同じ物をどの区分に割り当てたかを明示した内訳。測定用のseen表自身の領域と、測定前後の常駐も別に記録する。書き出しの待ちのPythonのIOオブジェクトを数えるが、OSの書き出し用の領域はこの内訳の外。

追加計測と、計測なしの既存の記録を、台帳本体・side・保存状態で照合する。照合そのものの時間はcProfileなしで使い道別に外から測る。自己照合はN3の分母を作る別の使い道として出す。元の呼び出し元のスタックも保存し、分類の重なりを確認できるようにする。

結果を変えない軽量化の候補として、不変のHypothesis/Candidateの内容が型・順・浮動小数の8バイトまで同じ場合だけ実体を共有する包みを、別の探索枝に用意した。本来の照合と乱数は全て実行する。論理的な控えの項目は削除しない。型・逆順・±0の検査とF/H/Uの小例で、記録と乱数を比べた部品検査151件は通過。200試行と1740試行の関門はまだ未確認。

reuse/pruneの移植も同じ枝に用意。元の省略のside記録は隠さず残す。今回の厳しい一致条件の下では、最初の不一致を記録してその案を外す。式、係数、確率、世界、選び、同点規則は変更しない。


## diag200：2026-10-05T19:12:27.204854+09:00

模型の土台と旗を変えず外部で内訳を観測。二条件とも元のnative記録と全バイト一致。cProfileなし。

内訳はPythonの実体を順に重複なく割り当てたsys.getsizeofの合計。測定のための住所の表とdataclassの辞書の実体化で常駐が増える。その最大は模型そのものの最大と同一視しない。速さの比較にはこの内訳を測った時間を使わない。

|条件|試行|内訳測定直前の常駐 MB|数えた保持領域 MB|うち照合結果の控え MB|うちRESULTS MB|測定用の住所表 MB|内訳測定後の常駐 MB|
|---|---:|---:|---:|---:|---:|---:|---:|
|A_diag200|99|232.194|156.218|103.947|46.873|137.546|431.161|
|A_diag200|199|538.558|397.992|270.365|116.082|448.253|1183.236|
|L_diag200|99|222.052|139.412|91.714|42.547|129.957|415.531|
|L_diag200|199|426.918|326.824|216.900|99.397|281.085|777.339|

自己の点、控えの乱数、図、同点の選択、統計、逐語の記憶、定義、残る記憶、書き出しのPythonのオブジェクトも別の列に記録。全区間の時間・常駐・各用途の照合器の実行回数と秒は添付の表。用途別は実行した照合器の時間で、キャッシュの検索やI/Oの時間を含めない。Aの二条件にはCの反実仮想の旗は無く、その使い道は0。routingの記録のための呼び出しは別。

この表は序盤200試行。終盤の内訳は未計測。全1740試行の外部観測を受付待ちで準備。古い控えを削除した案は0。


## prune_A_rejected：2026-10-05T19:22:51.385541+09:00

今の採点・世界2・種1・200試行のpruneは不通。台帳本体は全バイト一致、sideの答えと照合の記録、毎試行の控えの印、終わりの控えの保存は不一致。

最初の答えの記録の差：{"trial": "10", "different_fields": {"cand_n": {"baseline": "7", "prune": "4"}, "cand_other_ratios": {"baseline": "1.0000;1.0000;0.9167;0.4545;0.4375", "prune": "1.0000;1.0000;0.9167"}, "cand_tri": {"baseline": "1.0000:4/0/0/4;1.0000:6/1/0/6;0.9167:10/1/1/10;0.4545:4/1/6/4;0.4375:6/1/9/6", "prune": "1.0000:4/0/0/4;1.0000:6/1/0/6;0.9167:10/1/1/10"}}}

候補を照合せずに省くと、答えを選ぶための数が同じでも、調べた候補の一覧と控えの内容・記録の順が変わる。今回の関門ではこの差を除外しない。Aのpruneを全1740試行と採用候補から外した。式を変えて一致させない。枝と最初の差の証拠は残す。reuseは200試行の全バイト一致、実体の共有とlog P側は確認中。既存の走行は停止していない。


## compact_candidate_discarded：2026-10-05T19:35:17.148109+09:00

保存の形を属性の領域（slots）だけにする追加案を小例で検査した。slotsは、実体ごとの辞書を持たず、決まった属性だけを置くPythonの保存の形。

Pythonのmake_dataclassで作ったHypothesisの所属名がsme2017ではなくsmecompactになり、型名の保存の条件を満たさなかった。この追加案を取り下げた。コードと失敗した検査は自分の別枝に保持し、この案の200試行・全1740試行は0本。模型の式で直さず、この候補の検査はここで終了。

不変な実体の共有はAの200試行で全バイト一致。reuseもAの200試行で全バイト一致。pruneは既報のsideの不一致で外した。log P側と全長の確認を続け、既存の走行は停止していない。


## gates200：2026-10-05T19:36:43.915577+09:00

200試行の各案を全side・保存状態・同点の乱数と控えの保存も含めて比較。除外は台帳見出し一行と実測sec_trialだけ。cProfileなし。

|条件|案|全バイト一致|実時間 秒|最大常駐 MB|違った記録|
|---|---|---|---:|---:|---|
|A|off|True|226.720458|525.7||
|A|reuse|True|268.851907|523.9||
|A|prune|False|212.708067|479.4|side/f0.5000_th2.1000_vt0.3842_first_order/seed001.answers.csv, side/f0.5000_th2.1000_vt0.3842_first_order/seed001.sme.jsonl.gz, tie_state.jsonl, saved_matcher.jsonl.gz|

最初の不一致（A_prune）：{"file": "side/f0.5000_th2.1000_vt0.3842_first_order/seed001.answers.csv", "equal": false, "left_sha256": "f9dccc458eaa8a53880df67f2d3d59e1bab90cf946a28de80860bf75413b3b79", "right_sha256": "97940e27a0da0043428468f48d6d82254fbfcd24f22420de691d493f8f4f8227", "left_bytes": 41266, "right_bytes": 40041, "first_byte_difference": 620, "first_content_difference": {"line": 2, "left": "10,1,R_9d6e4b5f291af53c,4,R_9d6e4b5f291af53c@4,H_fill,12,hold_b,1,0,H,2,2,1.0,1,0.0,0,15,1,2,6,15,15,1.0,0.0,0.0,1.7449043451144322,0.2908173908524054,0.014705882352941176,7,1.0,1.0000;1.0000;0.9167;0.4545;0.4375,M2,M2,M2,1,M2:1,1,0,hold_b,cause#0,1,0,14,1,0,14,1.0000:4/0/0/4;1.0000:6/1/0/6;0.9167:10/1/1/10;0.4545:4/1/6/4;0.4375:6/1/9/6\n", "right": "10,1,R_9d6e4b5f291af53c,4,R_9d6e4b5f291af53c@4,H_fill,12,hold_b,1,0,H,2,2,1.0,1,0.0,0,15,1,2,6,15,15,1.0,0.0,0.0,1.7449043451144322,0.2908173908524054,0.014705882352941176,4,1.0,1.0000;1.0000;0.9167,M2,M2,M2,1,M2:1,1,0,hold_b,cause#0,1,0,14,1,0,14,1.0000:4/0/0/4;1.0000:6/1/0/6;0.9167:10/1/1/10\n"}}

|A|intern|True|224.717040|448.3||
|L|off|True|216.693968|412.0||
|L|reuse|True|238.679474|426.8||
|L|prune|False|170.560425|384.5|side/f0.5000_th2.1000_vt0.3842_first_order/seed001.answers.csv, side/f0.5000_th2.1000_vt0.3842_first_order/seed001.sme.jsonl.gz, tie_state.jsonl, saved_matcher.jsonl.gz|

最初の不一致（L_prune）：{"file": "side/f0.5000_th2.1000_vt0.3842_first_order/seed001.answers.csv", "equal": false, "left_sha256": "64a190a9dbb353b6c84e95227157b2e4c5a050b4698596ae0035195e2dff9b9f", "right_sha256": "f46c30e3ebcbe9ea46e8a601bf30c22c0bf3822b80a191a3e675f4d7dc4be3f4", "left_bytes": 43579, "right_bytes": 40566, "first_byte_difference": 641, "first_content_difference": {"line": 2, "left": "10,1,R_9d6e4b5f291af53c,4,R_9d6e4b5f291af53c@4,F_proj,12,hold_b,1,0,F,,,,,,16,0,0,2,6,16,16,1.0,0.2809449163560598,1.5681796835404858,1.5681796835404858,0.2908173908524054,0.014705882352941176,7,1.0,1.0000;1.0000;0.9167;0.4706;0.4545,M2,M2,M2,1,M2:1,1,0,hold_b,cause#0,1,0,15,1,0,15,1.0000:4/0/0/4;1.0000:6/1/0/6;0.9167:10/1/1/10;0.4706:7/1/9/7;0.4545:4/1/6/4\n", "right": "10,1,R_9d6e4b5f291af53c,4,R_9d6e4b5f291af53c@4,F_proj,12,hold_b,1,0,F,,,,,,16,0,0,2,6,16,16,1.0,0.2809449163560598,1.5681796835404858,1.5681796835404858,0.2908173908524054,0.014705882352941176,4,1.0,1.0000;1.0000;0.9167,M2,M2,M2,1,M2:1,1,0,hold_b,cause#0,1,0,15,1,0,15,1.0000:4/0/0/4;1.0000:6/1/0/6;0.9167:10/1/1/10\n"}}

|L|intern|True|152.526704|357.6||

不一致の案は後続の全1740試行と採用候補から外す。各探索のコードは証拠として別枝に残し、模型の式を変更して一致させない。通過した案の1740試行はまだ未確認。控えの項目を削除した案は0。


## continuation：2026-10-05T19:43:59.970077+09:00

200試行の全関門は完了。不変の実体の共有とreuseは、今の採点とlog Pの両方で全バイト一致。pruneは両方のside・控えが不一致で外した。

|条件|旗なしの最大常駐 MB|不変の実体を共有した最大常駐 MB|
|---|---:|---:|
|今の採点|525.7|448.3|
|log P|412.0|357.6|

この数は200試行の実測。全1740試行の内訳と一致は受付待ちで、採用可と扱わない。論理的な控えの項目の削除は0。元の資料と大きな状態は全て自分の出力に保持。探索用の二枝374e352/ca80f61は通常push済みで、本番の枝は変更していない。

全長の内訳、通った案の全長の一致、観測なしの時間と常駐、見込みは独立の制御で順に受付し、段末に追記・通常pushする。30分ごとの進み具合の記録も継続。重い処理は受付と空き・熱・スワップの条件を満たすまで開始しない。既存のC二本、log P残りと比較、key/combinedを停止していない。

報告用のfetchをsandbox内で呼んだ一時的な名前解決失敗で、全長の開始待ちの親二つだけが退出した。模型の停止は0本。失敗と旧PIDの記録を保持し、ネットワーク権限で通常のfetch/rebase/pushが成功後に、待機の親だけ再起動した。元の記録を消していない。


## progress_20261005_195019：2026-10-05T19:50:20.479061+09:00

SME＋(a)軽量化の30分の進行。完成した記録を二重に走らせず、既存のC・log P・key/combinedは停止していない。

[
  {
    "folder": "diagnostic_01/A_diag200",
    "completed": true,
    "last_recorded_trial": 199,
    "gate_passed": null
  },
  {
    "folder": "diagnostic_01/L_diag200",
    "completed": true,
    "last_recorded_trial": 199,
    "gate_passed": null
  },
  {
    "folder": "gates200_01/A_prune",
    "completed": true,
    "last_recorded_trial": 199,
    "gate_passed": false
  },
  {
    "folder": "gates200_01/L_off",
    "completed": true,
    "last_recorded_trial": 199,
    "gate_passed": true
  },
  {
    "folder": "gates200_01/L_intern",
    "completed": true,
    "last_recorded_trial": 199,
    "gate_passed": true
  },
  {
    "folder": "gates200_01/L_reuse",
    "completed": true,
    "last_recorded_trial": 199,
    "gate_passed": true
  },
  {
    "folder": "gates200_01/A_off",
    "completed": true,
    "last_recorded_trial": 199,
    "gate_passed": true
  },
  {
    "folder": "gates200_01/L_prune",
    "completed": true,
    "last_recorded_trial": 199,
    "gate_passed": false
  },
  {
    "folder": "gates200_01/A_intern",
    "completed": true,
    "last_recorded_trial": 199,
    "gate_passed": true
  },
  {
    "folder": "gates200_01/A_reuse",
    "completed": true,
    "last_recorded_trial": 199,
    "gate_passed": true
  },
  {
    "folder": "full_diagnostic_01/A",
    "completed": false,
    "last_recorded_trial": null,
    "gate_passed": null
  },
  {
    "folder": "full_diagnostic_01/L",
    "completed": false,
    "last_recorded_trial": null,
    "gate_passed": null
  }
]

停止の記録：[]


## progress_20261005_202022：2026-10-05T20:20:23.713137+09:00

SME＋(a)軽量化の30分の進行。完成した記録を二重に走らせず、既存のC・log P・key/combinedは停止していない。

[
  {
    "folder": "diagnostic_01/A_diag200",
    "completed": true,
    "last_recorded_trial": 199,
    "gate_passed": null
  },
  {
    "folder": "diagnostic_01/L_diag200",
    "completed": true,
    "last_recorded_trial": 199,
    "gate_passed": null
  },
  {
    "folder": "gates200_01/A_prune",
    "completed": true,
    "last_recorded_trial": 199,
    "gate_passed": false
  },
  {
    "folder": "gates200_01/L_off",
    "completed": true,
    "last_recorded_trial": 199,
    "gate_passed": true
  },
  {
    "folder": "gates200_01/L_intern",
    "completed": true,
    "last_recorded_trial": 199,
    "gate_passed": true
  },
  {
    "folder": "gates200_01/L_reuse",
    "completed": true,
    "last_recorded_trial": 199,
    "gate_passed": true
  },
  {
    "folder": "gates200_01/A_off",
    "completed": true,
    "last_recorded_trial": 199,
    "gate_passed": true
  },
  {
    "folder": "gates200_01/L_prune",
    "completed": true,
    "last_recorded_trial": 199,
    "gate_passed": false
  },
  {
    "folder": "gates200_01/A_intern",
    "completed": true,
    "last_recorded_trial": 199,
    "gate_passed": true
  },
  {
    "folder": "gates200_01/A_reuse",
    "completed": true,
    "last_recorded_trial": 199,
    "gate_passed": true
  },
  {
    "folder": "full_diagnostic_01/A",
    "completed": false,
    "last_recorded_trial": null,
    "gate_passed": null
  },
  {
    "folder": "full_diagnostic_01/L",
    "completed": false,
    "last_recorded_trial": null,
    "gate_passed": null
  }
]

停止の記録：[]


## progress_20261005_205026：2026-10-05T20:50:27.427760+09:00

SME＋(a)軽量化の30分の進行。完成した記録を二重に走らせず、既存のC・log P・key/combinedは停止していない。

[
  {
    "folder": "diagnostic_01/A_diag200",
    "completed": true,
    "last_recorded_trial": 199,
    "gate_passed": null
  },
  {
    "folder": "diagnostic_01/L_diag200",
    "completed": true,
    "last_recorded_trial": 199,
    "gate_passed": null
  },
  {
    "folder": "gates200_01/A_prune",
    "completed": true,
    "last_recorded_trial": 199,
    "gate_passed": false
  },
  {
    "folder": "gates200_01/L_off",
    "completed": true,
    "last_recorded_trial": 199,
    "gate_passed": true
  },
  {
    "folder": "gates200_01/L_intern",
    "completed": true,
    "last_recorded_trial": 199,
    "gate_passed": true
  },
  {
    "folder": "gates200_01/L_reuse",
    "completed": true,
    "last_recorded_trial": 199,
    "gate_passed": true
  },
  {
    "folder": "gates200_01/A_off",
    "completed": true,
    "last_recorded_trial": 199,
    "gate_passed": true
  },
  {
    "folder": "gates200_01/L_prune",
    "completed": true,
    "last_recorded_trial": 199,
    "gate_passed": false
  },
  {
    "folder": "gates200_01/A_intern",
    "completed": true,
    "last_recorded_trial": 199,
    "gate_passed": true
  },
  {
    "folder": "gates200_01/A_reuse",
    "completed": true,
    "last_recorded_trial": 199,
    "gate_passed": true
  },
  {
    "folder": "full_diagnostic_01/A",
    "completed": false,
    "last_recorded_trial": null,
    "gate_passed": null
  },
  {
    "folder": "full_diagnostic_01/L",
    "completed": false,
    "last_recorded_trial": null,
    "gate_passed": null
  }
]

停止の記録：[]


## progress_20261005_212029：2026-10-05T21:20:30.494026+09:00

SME＋(a)軽量化の30分の進行。完成した記録を二重に走らせず、既存のC・log P・key/combinedは停止していない。

[
  {
    "folder": "diagnostic_01/A_diag200",
    "completed": true,
    "last_recorded_trial": 199,
    "gate_passed": null
  },
  {
    "folder": "diagnostic_01/L_diag200",
    "completed": true,
    "last_recorded_trial": 199,
    "gate_passed": null
  },
  {
    "folder": "gates200_01/A_prune",
    "completed": true,
    "last_recorded_trial": 199,
    "gate_passed": false
  },
  {
    "folder": "gates200_01/L_off",
    "completed": true,
    "last_recorded_trial": 199,
    "gate_passed": true
  },
  {
    "folder": "gates200_01/L_intern",
    "completed": true,
    "last_recorded_trial": 199,
    "gate_passed": true
  },
  {
    "folder": "gates200_01/L_reuse",
    "completed": true,
    "last_recorded_trial": 199,
    "gate_passed": true
  },
  {
    "folder": "gates200_01/A_off",
    "completed": true,
    "last_recorded_trial": 199,
    "gate_passed": true
  },
  {
    "folder": "gates200_01/L_prune",
    "completed": true,
    "last_recorded_trial": 199,
    "gate_passed": false
  },
  {
    "folder": "gates200_01/A_intern",
    "completed": true,
    "last_recorded_trial": 199,
    "gate_passed": true
  },
  {
    "folder": "gates200_01/A_reuse",
    "completed": true,
    "last_recorded_trial": 199,
    "gate_passed": true
  },
  {
    "folder": "full_diagnostic_01/A",
    "completed": false,
    "last_recorded_trial": null,
    "gate_passed": null
  },
  {
    "folder": "full_diagnostic_01/L",
    "completed": false,
    "last_recorded_trial": null,
    "gate_passed": null
  }
]

停止の記録：[]


## progress_20261005_215033：2026-10-05T21:50:33.905710+09:00

SME＋(a)軽量化の30分の進行。完成した記録を二重に走らせず、既存のC・log P・key/combinedは停止していない。

[
  {
    "folder": "diagnostic_01/A_diag200",
    "completed": true,
    "last_recorded_trial": 199,
    "gate_passed": null
  },
  {
    "folder": "diagnostic_01/L_diag200",
    "completed": true,
    "last_recorded_trial": 199,
    "gate_passed": null
  },
  {
    "folder": "gates200_01/A_prune",
    "completed": true,
    "last_recorded_trial": 199,
    "gate_passed": false
  },
  {
    "folder": "gates200_01/L_off",
    "completed": true,
    "last_recorded_trial": 199,
    "gate_passed": true
  },
  {
    "folder": "gates200_01/L_intern",
    "completed": true,
    "last_recorded_trial": 199,
    "gate_passed": true
  },
  {
    "folder": "gates200_01/L_reuse",
    "completed": true,
    "last_recorded_trial": 199,
    "gate_passed": true
  },
  {
    "folder": "gates200_01/A_off",
    "completed": true,
    "last_recorded_trial": 199,
    "gate_passed": true
  },
  {
    "folder": "gates200_01/L_prune",
    "completed": true,
    "last_recorded_trial": 199,
    "gate_passed": false
  },
  {
    "folder": "gates200_01/A_intern",
    "completed": true,
    "last_recorded_trial": 199,
    "gate_passed": true
  },
  {
    "folder": "gates200_01/A_reuse",
    "completed": true,
    "last_recorded_trial": 199,
    "gate_passed": true
  },
  {
    "folder": "full_diagnostic_01/A",
    "completed": false,
    "last_recorded_trial": null,
    "gate_passed": null
  },
  {
    "folder": "full_diagnostic_01/L",
    "completed": false,
    "last_recorded_trial": null,
    "gate_passed": null
  }
]

停止の記録：[]


## progress_20261005_222036：2026-10-05T22:20:37.902731+09:00

SME＋(a)軽量化の30分の進行。完成した記録を二重に走らせず、既存のC・log P・key/combinedは停止していない。

[
  {
    "folder": "diagnostic_01/A_diag200",
    "completed": true,
    "last_recorded_trial": 199,
    "gate_passed": null
  },
  {
    "folder": "diagnostic_01/L_diag200",
    "completed": true,
    "last_recorded_trial": 199,
    "gate_passed": null
  },
  {
    "folder": "gates200_01/A_prune",
    "completed": true,
    "last_recorded_trial": 199,
    "gate_passed": false
  },
  {
    "folder": "gates200_01/L_off",
    "completed": true,
    "last_recorded_trial": 199,
    "gate_passed": true
  },
  {
    "folder": "gates200_01/L_intern",
    "completed": true,
    "last_recorded_trial": 199,
    "gate_passed": true
  },
  {
    "folder": "gates200_01/L_reuse",
    "completed": true,
    "last_recorded_trial": 199,
    "gate_passed": true
  },
  {
    "folder": "gates200_01/A_off",
    "completed": true,
    "last_recorded_trial": 199,
    "gate_passed": true
  },
  {
    "folder": "gates200_01/L_prune",
    "completed": true,
    "last_recorded_trial": 199,
    "gate_passed": false
  },
  {
    "folder": "gates200_01/A_intern",
    "completed": true,
    "last_recorded_trial": 199,
    "gate_passed": true
  },
  {
    "folder": "gates200_01/A_reuse",
    "completed": true,
    "last_recorded_trial": 199,
    "gate_passed": true
  },
  {
    "folder": "full_diagnostic_01/A",
    "completed": false,
    "last_recorded_trial": null,
    "gate_passed": null
  },
  {
    "folder": "full_diagnostic_01/L",
    "completed": false,
    "last_recorded_trial": null,
    "gate_passed": null
  }
]

停止の記録：[]


## progress_20261005_225040：2026-10-05T22:50:41.548935+09:00

SME＋(a)軽量化の30分の進行。完成した記録を二重に走らせず、既存のC・log P・key/combinedは停止していない。

[
  {
    "folder": "diagnostic_01/A_diag200",
    "completed": true,
    "last_recorded_trial": 199,
    "gate_passed": null
  },
  {
    "folder": "diagnostic_01/L_diag200",
    "completed": true,
    "last_recorded_trial": 199,
    "gate_passed": null
  },
  {
    "folder": "gates200_01/A_prune",
    "completed": true,
    "last_recorded_trial": 199,
    "gate_passed": false
  },
  {
    "folder": "gates200_01/L_off",
    "completed": true,
    "last_recorded_trial": 199,
    "gate_passed": true
  },
  {
    "folder": "gates200_01/L_intern",
    "completed": true,
    "last_recorded_trial": 199,
    "gate_passed": true
  },
  {
    "folder": "gates200_01/L_reuse",
    "completed": true,
    "last_recorded_trial": 199,
    "gate_passed": true
  },
  {
    "folder": "gates200_01/A_off",
    "completed": true,
    "last_recorded_trial": 199,
    "gate_passed": true
  },
  {
    "folder": "gates200_01/L_prune",
    "completed": true,
    "last_recorded_trial": 199,
    "gate_passed": false
  },
  {
    "folder": "gates200_01/A_intern",
    "completed": true,
    "last_recorded_trial": 199,
    "gate_passed": true
  },
  {
    "folder": "gates200_01/A_reuse",
    "completed": true,
    "last_recorded_trial": 199,
    "gate_passed": true
  },
  {
    "folder": "full_diagnostic_01/A",
    "completed": false,
    "last_recorded_trial": null,
    "gate_passed": null
  },
  {
    "folder": "full_diagnostic_01/L",
    "completed": false,
    "last_recorded_trial": null,
    "gate_passed": null
  }
]

停止の記録：[]


## progress_20261005_232044：2026-10-05T23:20:45.190431+09:00

SME＋(a)軽量化の30分の進行。完成した記録を二重に走らせず、既存のC・log P・key/combinedは停止していない。

[
  {
    "folder": "diagnostic_01/A_diag200",
    "completed": true,
    "last_recorded_trial": 199,
    "gate_passed": null
  },
  {
    "folder": "diagnostic_01/L_diag200",
    "completed": true,
    "last_recorded_trial": 199,
    "gate_passed": null
  },
  {
    "folder": "gates200_01/A_prune",
    "completed": true,
    "last_recorded_trial": 199,
    "gate_passed": false
  },
  {
    "folder": "gates200_01/L_off",
    "completed": true,
    "last_recorded_trial": 199,
    "gate_passed": true
  },
  {
    "folder": "gates200_01/L_intern",
    "completed": true,
    "last_recorded_trial": 199,
    "gate_passed": true
  },
  {
    "folder": "gates200_01/L_reuse",
    "completed": true,
    "last_recorded_trial": 199,
    "gate_passed": true
  },
  {
    "folder": "gates200_01/A_off",
    "completed": true,
    "last_recorded_trial": 199,
    "gate_passed": true
  },
  {
    "folder": "gates200_01/L_prune",
    "completed": true,
    "last_recorded_trial": 199,
    "gate_passed": false
  },
  {
    "folder": "gates200_01/A_intern",
    "completed": true,
    "last_recorded_trial": 199,
    "gate_passed": true
  },
  {
    "folder": "gates200_01/A_reuse",
    "completed": true,
    "last_recorded_trial": 199,
    "gate_passed": true
  },
  {
    "folder": "full_diagnostic_01/A",
    "completed": false,
    "last_recorded_trial": 747,
    "gate_passed": null
  },
  {
    "folder": "full_diagnostic_01/L",
    "completed": false,
    "last_recorded_trial": null,
    "gate_passed": null
  }
]

停止の記録：[]


## progress_20261005_235048：2026-10-05T23:50:49.464649+09:00

SME＋(a)軽量化の30分の進行。完成した記録を二重に走らせず、既存のC・log P・key/combinedは停止していない。

[
  {
    "folder": "diagnostic_01/A_diag200",
    "completed": true,
    "last_recorded_trial": 199,
    "gate_passed": null
  },
  {
    "folder": "diagnostic_01/L_diag200",
    "completed": true,
    "last_recorded_trial": 199,
    "gate_passed": null
  },
  {
    "folder": "gates200_01/A_prune",
    "completed": true,
    "last_recorded_trial": 199,
    "gate_passed": false
  },
  {
    "folder": "gates200_01/L_off",
    "completed": true,
    "last_recorded_trial": 199,
    "gate_passed": true
  },
  {
    "folder": "gates200_01/L_intern",
    "completed": true,
    "last_recorded_trial": 199,
    "gate_passed": true
  },
  {
    "folder": "gates200_01/L_reuse",
    "completed": true,
    "last_recorded_trial": 199,
    "gate_passed": true
  },
  {
    "folder": "gates200_01/A_off",
    "completed": true,
    "last_recorded_trial": 199,
    "gate_passed": true
  },
  {
    "folder": "gates200_01/L_prune",
    "completed": true,
    "last_recorded_trial": 199,
    "gate_passed": false
  },
  {
    "folder": "gates200_01/A_intern",
    "completed": true,
    "last_recorded_trial": 199,
    "gate_passed": true
  },
  {
    "folder": "gates200_01/A_reuse",
    "completed": true,
    "last_recorded_trial": 199,
    "gate_passed": true
  },
  {
    "folder": "full_diagnostic_01/A",
    "completed": false,
    "last_recorded_trial": 1227,
    "gate_passed": null
  },
  {
    "folder": "full_diagnostic_01/L",
    "completed": false,
    "last_recorded_trial": null,
    "gate_passed": null
  }
]

停止の記録：[]


## progress_20261006_002052：2026-10-06T00:20:52.839388+09:00

SME＋(a)軽量化の30分の進行。完成した記録を二重に走らせず、既存のC・log P・key/combinedは停止していない。

[
  {
    "folder": "diagnostic_01/A_diag200",
    "completed": true,
    "last_recorded_trial": 199,
    "gate_passed": null
  },
  {
    "folder": "diagnostic_01/L_diag200",
    "completed": true,
    "last_recorded_trial": 199,
    "gate_passed": null
  },
  {
    "folder": "gates200_01/A_prune",
    "completed": true,
    "last_recorded_trial": 199,
    "gate_passed": false
  },
  {
    "folder": "gates200_01/L_off",
    "completed": true,
    "last_recorded_trial": 199,
    "gate_passed": true
  },
  {
    "folder": "gates200_01/L_intern",
    "completed": true,
    "last_recorded_trial": 199,
    "gate_passed": true
  },
  {
    "folder": "gates200_01/L_reuse",
    "completed": true,
    "last_recorded_trial": 199,
    "gate_passed": true
  },
  {
    "folder": "gates200_01/A_off",
    "completed": true,
    "last_recorded_trial": 199,
    "gate_passed": true
  },
  {
    "folder": "gates200_01/L_prune",
    "completed": true,
    "last_recorded_trial": 199,
    "gate_passed": false
  },
  {
    "folder": "gates200_01/A_intern",
    "completed": true,
    "last_recorded_trial": 199,
    "gate_passed": true
  },
  {
    "folder": "gates200_01/A_reuse",
    "completed": true,
    "last_recorded_trial": 199,
    "gate_passed": true
  },
  {
    "folder": "full_diagnostic_01/A",
    "completed": false,
    "last_recorded_trial": 1588,
    "gate_passed": null
  },
  {
    "folder": "full_diagnostic_01/L",
    "completed": false,
    "last_recorded_trial": null,
    "gate_passed": null
  }
]

停止の記録：[]


## progress_20261006_005055：2026-10-06T00:50:56.287011+09:00

SME＋(a)軽量化の30分の進行。完成した記録を二重に走らせず、既存のC・log P・key/combinedは停止していない。

[
  {
    "folder": "diagnostic_01/A_diag200",
    "completed": true,
    "last_recorded_trial": 199,
    "gate_passed": null
  },
  {
    "folder": "diagnostic_01/L_diag200",
    "completed": true,
    "last_recorded_trial": 199,
    "gate_passed": null
  },
  {
    "folder": "gates200_01/A_prune",
    "completed": true,
    "last_recorded_trial": 199,
    "gate_passed": false
  },
  {
    "folder": "gates200_01/L_off",
    "completed": true,
    "last_recorded_trial": 199,
    "gate_passed": true
  },
  {
    "folder": "gates200_01/L_intern",
    "completed": true,
    "last_recorded_trial": 199,
    "gate_passed": true
  },
  {
    "folder": "gates200_01/L_reuse",
    "completed": true,
    "last_recorded_trial": 199,
    "gate_passed": true
  },
  {
    "folder": "gates200_01/A_off",
    "completed": true,
    "last_recorded_trial": 199,
    "gate_passed": true
  },
  {
    "folder": "gates200_01/L_prune",
    "completed": true,
    "last_recorded_trial": 199,
    "gate_passed": false
  },
  {
    "folder": "gates200_01/A_intern",
    "completed": true,
    "last_recorded_trial": 199,
    "gate_passed": true
  },
  {
    "folder": "gates200_01/A_reuse",
    "completed": true,
    "last_recorded_trial": 199,
    "gate_passed": true
  },
  {
    "folder": "full_diagnostic_01/A",
    "completed": false,
    "last_recorded_trial": 1739,
    "gate_passed": null
  },
  {
    "folder": "full_diagnostic_01/L",
    "completed": false,
    "last_recorded_trial": null,
    "gate_passed": null
  }
]

停止の記録：[]


最新の構造検査と実100は未確認。模型 ddb119f5eb7e78c2bd39de2a932390688914a664（指示35の小さい二旗は既定off）、指示36指定のGoogle Cloud d3向け。旧fe89準備と旧直列受付終了2は履歴として保持する。

# 指示33：速度二旗の6e4上への移植・実関門待ち

模型は fe89c0128fc6a26589460745563e2716ae2d33f0、tree c86dd84acdce0716fe405d93fbf166f2309a3897。親6e4bcba94874a4f49c5a1bae11d385534504e2e5。専用ローカル枝 codex/verb-speed-allin-2026-10-10 だけに保持し、新枝はpushしない。port.patchとspeed_allin.bundleで渡す。両速度旗は既定off。V1・出生fork・試験・JSON互換ログは保持。bundleは11,188B、復元HEAD/tree/clean確認済み。

これは準備の報告で、構造検査全体や実100関門の合格ではない。serial_existing_status.jsonと私有の既存runtimeを先に読む。直列構造検査の監督45403/jobs45405を一度だけ受付し、10分swap増加の既存判定で待機している。未生成のresultをpassedと補わず、同じ受付・検査を再投入しない。tests.log/result/statusを原本で確認し、終了後に必要なら別extra、birthを一度ずつ実施する。

前回99件のXMLの11クラスを previous99_coverage.jsonに保存。serialの関連116件とV1/JSON互換検査に加え、extraの4ファイルで前回99件の全ファイルを覆う。birthは16件の問いのfork検査。test_commands.jsonは元の受付0.5GiB、直列/extra CPU1枠・出生CPU5枠、模型起動0。共有模型8/CPU8/未知0/記憶/10分swap/熱/空き20GiBを保ち、足りない枠を推測で減らさない。別機械はClaudeが正式に指定するまで開始しない。

## 固定100命令と比較

prepare_gate100.py BASE_SOURCE NEW_SOURCE NEW_CASE_ROOT で baseline6e4/speed_off/speed_on の三specを新規に用意する。設定/len/horizon5000・種1・正確B/E・match-eps0・score-logp-e無し・V1on・出生4・PROBEonを保つ。新sourceのoff/on二旗だけの差。全てready_to_start=falseで、模型・受付は起動しない。新観察器は既存の学習入口を一度呼んだ後の100時点のSTATE/RNG/全cacheを記録するだけ。原模型の出力行を変更せず、稼働中の観察器を替えない。

本当のserial/extra/birth終了0と全ファイルの記録を structural_checks.template.json の別完成記録へ埋め、SHAと通常pushの40桁を確認する。指定Mac以外はClaudeの機械指定とその通常送信確認も要る。gate_claim.template.jsonは未承認の空欄であり使えない。開始前にspecのreadyと現在の測定に合わせた予約を固定し、spec SHA付きの関門開始記録を通常pushする。既存の同じ出力や完了済み100を再利用しない。

`$PYTHON ~/jobs/jobs.py run --wait --mem 10 --disk-path NEW_CASE -- $PYTHON -B PACKAGE/run_gate100.py NEW_CASE` を必要枠5模型・6CPUと全資源条件が実際に通るときだけ一度実行。Linuxはその既存受付のfresh --clearanceも必須。Macで枠が無ければ必要枠をClaudeへ報告して指定を待つ。三本を同時に開始しない。aの6e4/新offが正常100で一致するまでbのonを新しく始めない。開始済みの模型に信号を送る監督は導入しない。

`$PYTHON ~/jobs/jobs.py run --wait --mem 0.3 --disk-path RESULTS -- $PYTHON -B PACKAGE/run_compare100.py LEFT_CASE RIGHT_CASE RESULTS/speed100_a.json --mode a`、次に同じ入口でspeed100_b.json/--mode b。CPU1/同boot/全資源条件を再確認。結果フォルダへ進行/受付/psの札を混ぜない。比較は全模型名集合・台帳/全side/注意/evictions/試験回答/STATE/RNG/SME控えと全manifest研究者辞書の原字節を要求。bのC*原控えはoff側のP10と同じ事後廃棄の控えとon実控えを比較し、両側の禁止参照0・onのguard0を要求。既定第二段TIMEと非模型観察時間だけ元の定義で扱う。試験行/模型ファイルの除外0。test_compare100.pyの人工記録6検査もextraで実施し、実模型の合格とは分ける。

一件の不一致又は例外は原本を保持して件数/欄/例を報告し、模型を直して一致を作らない。後の一致で先行失敗を上書きしない。100を5000合格とせず、旗は全長まで仮、λは動詞較正まで仮。100のreal/CPU比と1000での利得は実測未確認。旧クラウドの1.22倍をこの並列出生版の値へ代入しない。正式本番への二旗の適用はClaudeの指示待ち。

原slow19二本とSME19pは元の版・旗・観察・出力・PID・予約で続行。別300取消、種21〜40禁止、AWSの同じ質問/ログイン/期限切れアクセス無し。期限2026-10-13 09:00 JST以降、新規開始と継続確認を止め、期限だけで開始済みを止めない。


## 指示35・36の追加（2026-10-10T18:23:26.551759+09:00）

最新模型は ddb119f5eb7e78c2bd39de2a932390688914a664、tree a1be6fb59738f78dcdf08a79f6b091d1a6053e17。旧fe89の準備は履歴として私有package_before_smallに保持。P10は含む。小さい二旗 --stage2-birth-observation-view と --stage2-birth-gc-freeze は別々に既定off、三本の指示33関門ではoffのまま。読取窓は元観測の全欄hashを前後で確認し、書込みと未知の可変型を止める。GCは出生forkの前だけ固定し、親の元の有効状態へfinallyで戻す。既存GC固定には重ねない。V1/試験/元の出生計算とJSON互換ログを保持する。両小さい旗onの実関門は未確認で、本番に使わない。

機械はClaudeの指示36で Google Cloud d3（c2d-standard-16）に確定。machine_assignment36.json の受領通常push40桁を固定した。構造全検査が実合格し、その証拠と通常pushが届くまで三本100を開始しない。このチャットからクラウド模型0。指示34新入口の実100はデスクトップの各D機械が担当し、包み作成済みと実合格を分ける。

旧直列受付は17:52:41に分類9/外側CPU8で条件不成立、終了2、tests_started=false、result/tests.log未生成。serial_initial_admission_ended.json と私有原本を読む。同じ終了済み受付を再投入しない。記録済み出生子とB6本人の不在という実変化後にだけ、新しい三部分runtimeで元の条件を再確認する一回待機を用意する。足りない枠を推測で減らさず、資源不成立なら自動再試行しない。

後の速度測定はlater_timing_proposal.jsonの未実行案。元本番の状態や観測を途中へ差し込まず、別の新出力で先頭600まで自然終了し、原500/600時間行の501〜600区間を比較する。実100関門・正式機械・費用/受付/全資源条件の後にだけ始める。1000で同じ比とは仮定しない。35の既存SME19pの表と大きい手の設計は33の後に続ける。大きい手の実装はClaudeの判断待ち。

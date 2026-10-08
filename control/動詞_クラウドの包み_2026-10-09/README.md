# 指示9〜13：動詞のクラウド用の包みと比較の準備

最新の指示15：試験行の固定鍵による96行の除外がアストラ承認済み。Mac先行on100を別比較で合格と判定、原不合格・原出力を保持。記録書き出し修正の新しいbundleと未完了100/20関門は[instruction15/README.md](instruction15/README.md)。クラウドの新しい同方法比較は未確認。speed200は試験行を除かず全体を比べる。300取消と稼働中の旧版・旗・観察入口を維持。

最新の指示14（2026-10-09T07:23:28+09:00）：300は未開始のまま取りやめる。Macの保存状態は既存rng欄で試験の96行を識別し別診断の残り300行が全バイト一致したが、原比較・関門は不合格のまま。クラウドのon100原比較も同じ1ファイル不一致。実終了時刻でMacが先行と確認済み。speed200の原完了と100試行ごとの実測は未着、関門の扱いはClaude・アストラの決定を待つ。旧包みや稼働中の版・旗・観察入口を変更しない。以降の300実行手順は準備時の履歴で、指示14により実行しない。

最新の関門状態（2026-10-09T06:20:53+09:00）：Macのon100 retry2は保存状態1ファイルに全バイト不一致、passed=false。300未開始。クラウド側の原完了と先行組判断は未確認のため合格又はwaitingと推測せず、Macの不一致を後の組で上書きしない。模型・包み・観察driverを直さず原本を保持して報告した。[原報告](../2026-10-07_動詞の世界_新しい版の移植_Codex.md)。

2026-10-09に準備。学習走行はこの包みの作成時点では未実行。Macの監督77418・retry2を止めず、計算用40e87b2・全旗・測定λ・観察driverも変えていない。継続確認と新規開始の期限は2026-10-11 09:00 JST。開始済みの処理を期限で止めない。

## 固定した版

| 用途 | 専用ローカル枝 | 包みのコミット | 模型の出所・観察入口 |
|---|---|---|---|
| on100二本と300 | codex/verb-cloud-package-2026-10-09 | bee30db3c2a41f00248913a57987bb54aa79aecb | 模型40e87b2e1fbd8348141dd447ac49c3aaadd7d914。観察SHA6ca7af8f64dbc9599ac256f84d15930d37d102aeff56bf2e1f29b861c49217f4 |
| 速度off/on200の準備 | codex/verb-stage2-speed-2026-10-09 | 977dcffea04c2f23c5472eab5bf760362e9fd25a | 40eへ4ceadf63の二旗を移植。観察SHA235a580d6f43bfffb88bc332a8eb4dcba85b7971e1617ee364570fb41435816d |

指示10（2026-10-09 01:51）により、新しい枝はoriginへpushしない。差分とGit bundleを承認済みresults-2026-09-27へ置き、クラウドへ渡す。指示9の1の新枝pushの要求はこの方式へ替わり、追加の直接承認を求めない。bundleの土台は承認済みoriginの`e9ed84ae3ee6c458f392cd58cadf9fc030639900`。旧作業枝や他の係のcheckoutへ適用しない。

送信用の枝はCodexの公開用作者情報で作り、模型・観察・包みのファイルの木が、検査した専用ローカル版と全く同じであることを確認した。Macの40eの履歴や稼働中のcheckoutを書き換えていない。`source_manifest.json`が模型の全ファイルのGit blobとmodeを照合し、包みの付加ファイルだけを別にする。RunHeaderの出所タグ4dc6a05はMacと同じ。実際の包みのHEADと模型の出所40eはruntime・完了記録へ別々に残す。

`versions.json`、各フォルダの`files.json`にSHA256・サイズ・固定コミットを置いた。`source.patch`は同じ版の差分、`source.bundle`は復元可能なGitの包み。鍵・合い言葉は含めない。



| bundle | 取り出し後のHEAD | tree hash | bundle SHA256 | バイト |
|---|---|---|---|---|
| cloud | `bee30db3c2a41f00248913a57987bb54aa79aecb` | `d1db06b3bf932a6a3cab487848696fa1e05dcd76` | `4ccb77290324df02d30920540cea537a4146765ae75e121f09829205b967853d` | 78987 |
| speed200 | `977dcffea04c2f23c5472eab5bf760362e9fd25a` | `df3a71e96a75352012123371c9875c31a7a96146` | `672200a5c9f0a3ed4fe2c99c31d4f843012f90ca50b6671cd45efbf2ae88f565` | 114560 |

両bundleとも50MB以下。50MBを超える新しいbundleは送らず報告して待つ。取り出し後、HEADとtree hashの両方を上表と照合してから走行する。

今回の更新は包みと比較・観察の道具だけ。既に旧包みで走行を始めた機械は、その版・旗・観察入口を途中で替えない。今回の比較器を使うときは、最新bundleを別の専用checkoutへ復元して、完了した同版・同機械の二本の原出力を読む。新旧の片側を混ぜない。固定試験は同じ48問で、100・200・300時点の累積回答行数は48・96・144。問題数と回答行数を区別して完了を確認する。

## Ubuntu・Python3.12での準備

走行係が用意済みのUbuntu機械で行う。下の`/srv/verb`は、この係専用の書き込み可能な場所にする。報告用checkoutは最新をfetch・mergeした`results-2026-09-27`とする。出力先にはユーザー名や鍵を含めず、time.logを原本で共有できる場所を使う。

```sh
VERB_PACKAGE=/srv/verb/report-results/control/動詞_クラウドの包み_2026-10-09
VERB_SOURCE=/srv/verb/source
VERB_OUTPUT_ROOT=/srv/verb/measurements_20261009
VERB_JOBS=/srv/jobs/jobs.py
VERB_CLEARANCE_ROOT=/srv/verb/resource_clearance

git clone --no-checkout https://github.com/Godfumitaka/sfn-compression-abm.git "$VERB_SOURCE"
git -C "$VERB_SOURCE" checkout --detach e9ed84ae3ee6c458f392cd58cadf9fc030639900
test "$(sha256sum "$VERB_PACKAGE/cloud/source.bundle" | cut -d " " -f 1)" = 4ccb77290324df02d30920540cea537a4146765ae75e121f09829205b967853d
git -C "$VERB_SOURCE" bundle verify "$VERB_PACKAGE/cloud/source.bundle"
git -C "$VERB_SOURCE" fetch --no-tags "$VERB_PACKAGE/cloud/source.bundle" refs/heads/codex/verb-cloud-package-2026-10-09
git -C "$VERB_SOURCE" checkout -b codex/verb-cloud-package-2026-10-09 bee30db3c2a41f00248913a57987bb54aa79aecb
test "$(git -C "$VERB_SOURCE" rev-parse HEAD)" = bee30db3c2a41f00248913a57987bb54aa79aecb
test "$(git -C "$VERB_SOURCE" rev-parse "HEAD^{tree}")" = d1db06b3bf932a6a3cab487848696fa1e05dcd76
python3.12 -m venv /srv/verb/env
VERB_PY=/srv/verb/env/bin/python
VERB_TOOLS="$VERB_SOURCE/tools/verb_measurement"
"$VERB_PY" "$VERB_TOOLS/cloud_run.py" prepare --source "$VERB_SOURCE" --commit bee30db3c2a41f00248913a57987bb54aa79aecb --root "$VERB_OUTPUT_ROOT"
```

`prepare`は三本のruntimeを作るだけで、模型を始めない。出力済みの根や走行済みの同じ場所への再投入は拒否する。OSがLinux、Pythonが3.12、HEADが固定、作業木がclean、模型の木と観察SHAが一致しなければ走行しない。

三本とも個体worker1本、親を含む開始CPU枠2、受付メモリ見込み2.0GB。Macのspecの全旗を`cloud/plan.json`へ転記した。種1、設定trial-count5000、horizon5000、実行は先頭100／100／300だけ。全部入り・出生HU on・速度旗既定off、測定λはe-priceとv39-priceとも0.01873710622997919。300には固定非学習試験が含まれる。本番のλへ代用しない。

## 受付と資源の確認

`VERB_JOBS`は、走行係が使っているUbuntu対応の既存jobs受付を指定する。Mac専用のpmset/sysctl版をそのままUbuntuへ持ち込まない。受付表・規則を外す代替の直起動はしない。

既存の受付・資源監督が、各本の`runtime.json`のSHAに結び付けた確認を`VERB_CLEARANCE_ROOT/<label>.json`へ作り、監督中も60秒以内の間隔で原子的に更新する。確認が用意できない場合は、開始前の条件が揃っていないので待つ。値を推測で真にしない。

必要な欄は`runtime_sha256`、`machine_sha256`（/etc/machine-idのSHA256）、`memory_reservation_gb=2.0`、`checked_epoch`、`warning`、`memory_admission_ok`、`swap_stable_10min`、`thermal_ok`、`physical_cpu_count`、`cpu_budget`。CPU予算は既存規則どおり物理芯数から2を引いた値。受付メモリ、直近10分のswap、熱について既存監督が確認する。

入口は実際の個体workerを数えて同時8本までを保ち、親・監督・time・resource_tracker・T/Zを模型の稼働数に足さない。Macの既存の数え方を変更せず複製した。未分類spawn、CPU枠超過、熱・受付確認の欠落や古さ、空き容量の警告では自分の測定群だけを既存方式で一時停止し、条件が戻れば自動再開する。他の係・本番を操作しない。開始時の空き20GiB、監督時の18.5GiBの境界も維持する。常駐が2.0GB予約を超えた場合は原記録を残して次の開始を待ち、新しい実測に合わせて次の予約を判断する。

## 同じ機械の100二本と比較

この二本の全旗の差は`--probe-world`だけ。別の機械や別の版の片側と混ぜない。指示13により、各本の受付と資源確認が揃えば同じ機械で並行してよい。直列であることは関門の条件に入らない。下の二本のrunは各専用ターミナルへ出せる。Macの既存監督の順番は変えない。両本が正常に終わってから比較する。

```sh
"$VERB_PY" "$VERB_TOOLS/cloud_run.py" run "$VERB_OUTPUT_ROOT/on100_without_probe" --jobs "$VERB_JOBS" --clearance "$VERB_CLEARANCE_ROOT/on100_without_probe.json"
"$VERB_PY" "$VERB_TOOLS/cloud_run.py" run "$VERB_OUTPUT_ROOT/on100_with_probe" --jobs "$VERB_JOBS" --clearance "$VERB_CLEARANCE_ROOT/on100_with_probe.json"
"$VERB_PY" "$VERB_JOBS" run --wait --mem .2 --disk-path "$VERB_OUTPUT_ROOT" -- "$VERB_PY" "$VERB_TOOLS/cloud_compare.py" "$VERB_OUTPUT_ROOT/on100_without_probe" "$VERB_OUTPUT_ROOT/on100_with_probe" "$VERB_OUTPUT_ROOT/on100_comparison.json"
```

300の資源確認には`first_pair_decision`も必要。`model_commit`と`observer_sha256`、`selected_pair`（Mac又はcloud）、`pairs.Mac`と`pairs.cloud`を含む。各組には`checked_epoch`、`state`（waiting又はcompleted）、完了なら`finished_epoch`と原本`comparison`を入れる。両方の確認時刻はクラウド組の完了時刻以降とし、早く完了した組を選ぶ。原比較の全ファイルのSHAと不一致0を再確認する。未確認の機械をwaitingと推測して記入しない。先行不一致は300を開始できず、後の組で上書きできない。

正常終了・manifest・partial_doneが100、設定とhorizonが5000、全5000完了ではないことを確認する。試験ありは48問・fingerprint1回、注意と問い回数の前後一致を確認する。本体・乱数の保存復元の検査は固定した非学習試験の接続に含まれる。資源警告付きの結果を無条件に合格へしない。

比べ方はMacのon100_retry2_compare.pyと同じ。`ledgers`・`side`・`evictions`・`attention`にある全ファイルの集合を比べ、gzipは内容の全バイトを比較する。欄を削除・丸め・再配列しない。固定試験だけの`.probe.jsonl`と`.done`は比較から除いて原本保存する。台帳、全side、順付き保存状態、evictions、注意は含む。必須の入口の一覧は次のとおりで、実際の出力で加わったsummaryや診断も同じ対象フォルダ内ならすべて比較する。完了後の正確な全一覧はcomparisonの`files`とSHA表になる。

| 対象 | cell以下の種1のファイル |
|---|---|
| 台帳 | ledgers/cells/<cell>/seed001.jsonl.gz |
| side | seed001.jsonl、seed001.ambig.csv、seed001.answers.csv、seed001.routing.jsonl |
| SMEと保存状態 | side/<cell>/seed001.sme.jsonl.gz、seed001.sme.states.jsonl.gz、付随する診断 |
| evictions | evictions/<cell>/seed001.keys.jsonl.gzとsummary |
| 注意 | attention/<cell>/seed001.jsonl.gzとsummary |

cellは`f0.5000_th2.1000_vt0.3842_first_order`。比較では件数・各欄のファイル・最初のバイト位置・例を記録する。一件でも不一致なら模型を直さず止まりとして報告し、300を始めない。第二段の秒を含む`stage2`、`timing`、gzip容器、time、manifest、flagは原本を別保存する。非模型の時間を一致させるために模型の出力を書き換えない。

Macの組とクラウドの組のうち、二本とも先に正常完了した同機械の組で関門を判定する。`finished_epoch`を保存する。両機械の結果が届いたら、先に完了した組を最新の報告で確認してから300の新規開始を決める。先に完了した組が不一致なら、後の組で上書きして合格にしない。先にMacが通った場合も、クラウドの二本が終わる前にこの包みの300は始めない。Macの既存処理は止めない。

## 300の一本測定

同機械の100二本が通り、先に完了した組の判断も記録された後に行う。版・旗・λは変えない。

```sh
"$VERB_PY" "$VERB_TOOLS/cloud_run.py" run "$VERB_OUTPUT_ROOT/allin_s01_300" --jobs "$VERB_JOBS" --clearance "$VERB_CLEARANCE_ROOT/allin_s01_300.json" --gate "$VERB_OUTPUT_ROOT/on100_comparison.json"
```

完了数300を全5000完了と書かない。上の入口は比較passed、同じ機械、同じ版・観察SHA、両側の完了と固定試験をもう一度確認する。Mac側の300は別の未起動監督であり、この命令で二重起動しない。Macの監督もinstruction9_first_pair_decision.jsonを先に確認する。Macの比較へ時刻を付けるときは、二本の原resultのfinished_epochの最大をcomparisonのfinished_epochとして添える。内容比較のfilesを変更しない。先行組の判断が未生成なら300を始めない。

## 終了後に報告枝へ同梱するもの

各本について、time.log原本、result、版・全旗の出所、100ごとの実時間とCPU秒・常駐の表、全出力のraw/content SHA表、第二段・誕生・再照合の時間内訳を作る。比較結果も同梱する。全出力原本は機械に保持し、100MB超の台帳や秘密をGitへ上げない。

```sh
"$VERB_PY" "$VERB_JOBS" run --wait --mem .5 --disk-path "$VERB_OUTPUT_ROOT" -- "$VERB_PY" "$VERB_TOOLS/export_tables.py" "$VERB_OUTPUT_ROOT/on100_without_probe" "$VERB_OUTPUT_ROOT/report_on100_without_probe"
"$VERB_PY" "$VERB_JOBS" run --wait --mem .5 --disk-path "$VERB_OUTPUT_ROOT" -- "$VERB_PY" "$VERB_TOOLS/export_tables.py" "$VERB_OUTPUT_ROOT/on100_with_probe" "$VERB_OUTPUT_ROOT/report_on100_with_probe"
"$VERB_PY" "$VERB_JOBS" run --wait --mem .5 --disk-path "$VERB_OUTPUT_ROOT" -- "$VERB_PY" "$VERB_TOOLS/export_tables.py" "$VERB_OUTPUT_ROOT/allin_s01_300" "$VERB_OUTPUT_ROOT/report_allin_s01_300"
```

第二段のJSONLと整形済みJSON summaryを形式別に読む。クラウド用15件、指示11〜13を加えた速度の包み27件の非模型検査が通った。以前の模型構造99件・先頭200観察20件は模型と観察入口が変わらないため再投入していない。

報告表は`checkpoints.tsv`、`sha256.tsv`、`timing_breakdown.tsv`、`provenance.json`、`result.json`、`time.log`。300では`conditional_5000_estimate.json`も作る。100・200・300の累積と各区間の実時間、user/sys・合計CPU秒を区別する。Linuxのru_maxrssはKiB、MacはBなので、観察driverの原記録を変更せずLinux報告表で1024倍し、原値と単位も残す。GNU time -v原本も保持する。

5000見積りは、実測三つの100区間の最小〜最大と同じ負荷が残り4700で続く場合の条件付き幅。重さの増大や資源待ちの上限を保証しない。第二段のwrapper・本体・再照合には包含があるので時間を無条件に足さない。結果の良し悪しは書かない。

走行係は小さい報告物をこの包みの下の機械別の新しいフォルダへコピーし、comparisonのローカルパスは匿名の出力根へ置き換えて共有する。原本は機械に残す。秘密・個人情報・100MB超、送るlogとdiff --statを確認し、報告枝を最新へfetch・mergeして通常pushする。rebase・force-pushは禁止。種21〜40の読み取りや走行、削除、本番の停止、受付・関門の規則外しは行わない。


## 速度と較正の先頭200の組

新しい専用checkoutを土台e9から作り、speed200のbundleをverify・fetchする。最新のHEADは 977dcffea04c2f23c5472eab5bf760362e9fd25a、tree df3a71e96a75352012123371c9875c31a7a96146、bundle SHA256 672200a5c9f0a3ed4fe2c99c31d4f843012f90ca50b6671cd45efbf2ae88f565。通常の二本と較正の二本の計四本をprepareで作るだけでは、模型を始めない。

~~~sh
VERB_SPEED_SOURCE=/srv/verb/speed_source_instruction11
VERB_SPEED_ROOT=/srv/verb/speed200_instruction11
VERB_SPEED_TOOLS="$VERB_SPEED_SOURCE/tools/verb_measurement"
git clone --no-checkout https://github.com/Godfumitaka/sfn-compression-abm.git "$VERB_SPEED_SOURCE"
git -C "$VERB_SPEED_SOURCE" checkout --detach e9ed84ae3ee6c458f392cd58cadf9fc030639900
test "$(sha256sum "$VERB_PACKAGE/speed200/source.bundle" | cut -d " " -f 1)" = 672200a5c9f0a3ed4fe2c99c31d4f843012f90ca50b6671cd45efbf2ae88f565
git -C "$VERB_SPEED_SOURCE" bundle verify "$VERB_PACKAGE/speed200/source.bundle"
git -C "$VERB_SPEED_SOURCE" fetch --no-tags "$VERB_PACKAGE/speed200/source.bundle" refs/heads/codex/verb-stage2-speed-2026-10-09
git -C "$VERB_SPEED_SOURCE" checkout -b codex/verb-stage2-speed-2026-10-09 977dcffea04c2f23c5472eab5bf760362e9fd25a
test "$(git -C "$VERB_SPEED_SOURCE" rev-parse HEAD)" = 977dcffea04c2f23c5472eab5bf760362e9fd25a
test "$(git -C "$VERB_SPEED_SOURCE" rev-parse "HEAD^{tree}")" = df3a71e96a75352012123371c9875c31a7a96146
"$VERB_PY" "$VERB_SPEED_TOOLS/cloud_run.py" prepare --source "$VERB_SPEED_SOURCE" --commit 977dcffea04c2f23c5472eab5bf760362e9fd25a --root "$VERB_SPEED_ROOT"
~~~

speed200_offとspeed200_onは通常の全部入り、calibration200_offとcalibration200_onは同じ全部入りに --no-forget-exec を加えた#19c用の仕組みの関門。種1・設定5000・horizon5000・先頭200・出生HU on・測定λ0.01873710622997919を保つ。較正本番の種41〜48、各5000とは区別する。各組の差は --stage2-speed と --stage2-cache-prune のoff/onだけ。固定48問を二時点で問うので回答は96行、fingerprintと注意の保存復元確認は2回。

各本は既存jobsと継続資源確認へ通す。下の命令は各専用ターミナルから並行してよいが、模型8本・CPU・メモリ・swap・熱・容量の枠を先に満たす。

~~~sh
"$VERB_PY" "$VERB_SPEED_TOOLS/cloud_run.py" run "$VERB_SPEED_ROOT/speed200_off" --jobs "$VERB_JOBS" --clearance "$VERB_CLEARANCE_ROOT/speed200_off.json"
"$VERB_PY" "$VERB_SPEED_TOOLS/cloud_run.py" run "$VERB_SPEED_ROOT/speed200_on" --jobs "$VERB_JOBS" --clearance "$VERB_CLEARANCE_ROOT/speed200_on.json"
"$VERB_PY" "$VERB_SPEED_TOOLS/cloud_run.py" run "$VERB_SPEED_ROOT/calibration200_off" --jobs "$VERB_JOBS" --clearance "$VERB_CLEARANCE_ROOT/calibration200_off.json"
"$VERB_PY" "$VERB_SPEED_TOOLS/cloud_run.py" run "$VERB_SPEED_ROOT/calibration200_on" --jobs "$VERB_JOBS" --clearance "$VERB_CLEARANCE_ROOT/calibration200_on.json"
~~~

指示13により、speed200の開始はon100の判定を待たない。**判定の記録はon100を先にし、その通常pushの40桁コミットと実際の先行組判断を確認してからspeed200と較正200を判定する。** 未確認の片側をwaiting又はpassedと推測して作らない。原本の二本が完了する前に比較しない。

~~~sh
VERB_ON100_DECISION=/srv/verb/confirmed/instruction9_first_pair_decision.json
VERB_ON100_REPORT_COMMIT=on100の判定を通常pushした40桁コミット
"$VERB_PY" "$VERB_JOBS" run --wait --mem .5 --disk-path "$VERB_SPEED_ROOT" -- "$VERB_PY" "$VERB_SPEED_TOOLS/speed_gate.py" "$VERB_SPEED_ROOT/speed200_off" "$VERB_SPEED_ROOT/speed200_on" "$VERB_SPEED_ROOT/speed200_judgement" --on100-decision "$VERB_ON100_DECISION" --on100-report-commit "$VERB_ON100_REPORT_COMMIT"
"$VERB_PY" "$VERB_JOBS" run --wait --mem .5 --disk-path "$VERB_SPEED_ROOT" -- "$VERB_PY" "$VERB_SPEED_TOOLS/speed_gate.py" "$VERB_SPEED_ROOT/calibration200_off" "$VERB_SPEED_ROOT/calibration200_on" "$VERB_SPEED_ROOT/calibration200_judgement" --on100-decision "$VERB_ON100_DECISION" --on100-report-commit "$VERB_ON100_REPORT_COMMIT"
~~~

比較器は今回のspeed_gate.pyを入口とし、依存する今回のcloud_compare.py・cloud_run.py・instruction11_io.py・planも同じ最新checkoutから読む。instruction11/SHA256SUMSはレビュー用の同梱コピーと命令草稿のSHA一覧であり、単独のrunnerとして既存の稼働checkoutへ上書きしない。

| 比較の道具 | SHA256 |
|---|---|
| speed_gate.py | dbeaa0b51b14a062f14488b96c332eecb682f7c48ceb0f755ac793dcd8b2187f |
| cloud_compare.py | f19c3ebede9f306f63792438bb9ecd0dfb23353e3a42150daa8af58bab85e7f8 |
| cloud_run.py | d22265e6c4ca1ab29983b4468b9aebecd13b527ff82a47411a3e6526da95611d |
| instruction11_io.py | 2db2c8bb0ede284e7071979dda3b1189fe6db2745a31f3e288f153c75ab8871e |
| checkpoint_compare.py | 2a4c7c97ca487ca2e163ad3c76fe25962608abfefea5aef6ef6731c00a28c96a |
| checkpoint_observer.py | f3c1f8fe52c6bc7b781a00990434f22d7e6355c5fb092a64f40c76162a325429 |

試験の.probe.jsonlを含め、台帳・全side・順付き保存状態・evictions・注意・試験後の100〜199の学習を内容の全バイトで比べる。stage2・研究者較正記録も含める。D-07αυで認められた第二段TIME値だけを比較用に扱い、原本・欄・行や鍵の順序・空白・配列順を保持する。対象TIME値は seconds、wrapper_seconds、engine_seconds、rematch_fraction_of_stage2_seconds の数値又はnullだけ。模型の記録を削除・丸め・並べ替えない。gzip容器・time・manifestは原本保存する。

content_comparison.json・all_outputs_comparison.jsonに件数・ファイル・最初のバイト位置・例・原内容SHAを残す。mechanisms_off.jsonとmechanisms_on.jsonは実際の誕生（同化と区別）、FH/HUの忘却・定義削除、P10の控え/乱数控えの廃棄数、禁止参照、試験回答96行・fingerprint/注意/問い回数の保存復元を記録する。未発生は「関門では未検証」。較正の忘却は命令上実行停止で、実変換0を確認する。summaryと境の廃棄数を二重に足さない。

内容の一致と仕組みの実発生を別欄にする。gate.json.passedだけで旗を採用せず、通常200・較正200の一致と必要な実発生を確認する。200一致を全5000一致としない。このチャットから新しい200の学習模型は起動していない。

## 本番四腕と並べる一本の命令草稿

instruction11/production_templates.jsonとinstruction11/command_drafts/へ、#19・#21・#22各種1〜10、#19c種41〜48、並べる#19種1旗なしの命令草稿を置いた。λ・正式なsource_commitはnullで、ready_to_start=false。本番λにはClaudeがお店の確定L50_refを記入する。測定λで代用しない。版・全旗・出力先・機械・未着手の列を取得し、通常pushが成功するまで本番を開始しない。実測に合わせた受付予約と、既存の本番用資源監督も必要。今回の草稿は新しい本番停止・再開監督を導入しない。

| 腕 | 旗の適用と未記入の条件 |
|---|---|
| #19 全部入り | 第二段・C*を使うため二旗onの候補。通常200と較正200の関門を先に通す。λ・正式版・列はClaudeの確定待ち |
| #21 D＋注意 τ=0.4 | お店2aと同じ第二段offの対象外。二旗off、出生HU off。現模型に共通D＋注意の --use-forget-attn が無く、共通版と関門を待つ。本人側へ推定で実装しない |
| #22 基準 | お店5aと同じC*offの対象外。二旗off、第二段off、出生HU off。Hのdirichlet1と順を保つ。正式な基準の全旗・版・列は確定待ち |
| #19c 較正 | 二旗onの候補、--no-forget-exec、種41〜48各5000。測定用の種1先頭200と混同しない |
| 並べる#19種1 | #19と同じ版・全旗・本番λで二旗だけoff。500ごとの全バイト比較を行う |

この草稿だけでは#21の共通実装や#22の正式旗の合格を補わない。#19・#19cも本番の利用条件は未成立。指示11の準備を進めており、学習の関門・本番採用・全長一致は未完了。

## 500ごとの並行比較とM1

#19種1・2と並べる旗なし#19種1の観察入口は tools/verb_measurement/production/measurement_driver.py。模型を5000まで通常どおり走らせ、最終appendを一度呼んだ後、既存の記録をflushして観察する。模型の規則・予測・問いの回数・学習状態・乱数を更新しない。既存の模型の数え方で認識されるファイル名を保つ。

完了数500・1000…5000ごとに、確定した原記録（開いているgzipは確定済み行の内容）、学習と忘却後のSTATE、学習用RNG・SME/C* RNG、順付き生の控え、観察した出所キーと廃棄/禁止参照の数を保存する。控えは模型から削除せず、offの控えを同じP10の条件で事後に取り出した比較用の控えも別保存する。

~~~sh
"$VERB_PY" "$VERB_JOBS" run --wait --mem .5 --disk-path "$VERB_PROD_OUT" -- "$VERB_PY" "$VERB_SPEED_TOOLS/checkpoint_compare.py" /srv/verb/production/19_parallel_off_seed001 /srv/verb/production/19_seed001 500 /srv/verb/production/comparison_seed001/checkpoint_0500.json
"$VERB_PY" "$VERB_SPEED_TOOLS/m1_at500.py" /srv/verb/production/19_seed001 /srv/verb/production/19_seed002 /srv/verb/production/m1_0500.json --through 500
"$VERB_PY" "$VERB_SPEED_TOOLS/m1_at500.py" /srv/verb/production/19_seed001 /srv/verb/production/19_seed002 /srv/verb/production/m1_1000.json --through 1000
~~~

比較のaは試験回答と試験後の学習を含む確定記録・STATE・RNG、bはoffの控えを同じP10条件で事後に取り出したものとonの控え、およびSME控え、cは捨てたキーの参照0。一つでも異なれば旗つきの結果は使わず、件数・欄・例を報告する。先行不一致を後の一致で上書きしない。全長の判定は最後のappendだけでは成立せず、両側の正常終了、原本の完了印と閉じた全出力を要求する。全5000で一致するまで旗の結果は「仮」、動詞較正の確認までλについても「仮」。

試行番号は既存模型の0始まり。完了数500の境は番号499の後である。M1の指定200〜500は両端込み301試行で、番号500が確定した完了数501で取り出す。未記録の500を補わない。忘却後の定義数1以下が301試行の9割以上かを整数で判定する。1000・2000・3000・4000も同じ0始まりの指定番号まで取り出し、設定5000の最後は4999までを記す。

**指示12の順番が最新**：#19・#21・#22とも種1・2を先にする。#19種1・2の200〜500のM1が基準に当たらないとClaudeが確認し、他の関門と列の条件が揃えば種3〜10を始める。動詞較正の1000判定を開始条件として待たない。取り出し器はClaudeの確認を代行しない。

較正8本が全て1000を終えたら、先頭1000の正のVのL25・L90を種の同じ重み、お店の同じ道具・定義で求める。お店L50_refが範囲外、又はM1の1000・2000以降が基準に当たれば、走っている本は止めず報告し、Claudeがアストラに諮る。関門の道具・お店の確定L50_refを推測で作らない。最終較正の1/2未満・2倍より大きいときだけ走らせ直す決定は変えず、境界込みの1/2〜2倍では走らせ直さない。

[準備の非模型検査](instruction11/preparation_checks.json)と[復元確認](restore_checks.json)が証拠。新しい本番・較正・速度200・クラウドon100・300はこのチャットから始めていない。指示3・6・7・8・9・11は実施中。指示12・13の決定を準備へ反映済み。

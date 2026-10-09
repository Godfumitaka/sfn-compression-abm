# 指示12B5(b)・14の八体20の専用受付入口

これは指定した候補92913206の本番価格の先頭20試行だけの診断入口です。列#20の本番を開始する入口ではありません。模型・全argv・設定・観察器は04:11の依頼と同じ原字節です。旧cloud_run.pyは変更せず、元のN7 run.pyの受付・固定版・機械・容量・重複・停止・実測の検査を残した別の入口です。構造の小例8件のみ通過。B5(a/b)の実関門は未完了で、候補は未受け入れです。

## 元の関門の名前の対応

五つの旧requiresは変更しません。gate_mapping.jsonで、元のN7の実記録を直接読んで対応を確認します。合格札の別名を作らず、不足を合格として補いません。

| 旧N5の要求 | 元N7の実ファイル（gates/） |
| --- | --- |
| gate-off8-serial-parallel.json | gate-off8.json と gate-off8-parallel.json |
| gate-on1-independent.json | gate-on1-f0.1.json と gate-on1-f0.9.json |
| gate-state-isolation.json | gate-components.json |
| gate-receive-replay.json | gate-receive-replay.json |
| gate-on8-measurement.json | gate-measure.json |

元N7の前提gate-off2.jsonも必要です。計8ファイルのpassed=true、candidate=c4cfed12a3944071951775b2c9373ca27705fb25、hostが現在の同じ機械・同じ起動の識別指紋であることを読みます。元の小例・単独二条件・直列と並列・受信再生・八体300の条件を減らしません。元のroot/STOP.jsonがあれば開始しません。根拠はreference_README.md、reference_components.py、reference_compare.py、reference_measurement.pyです。対応は名前の照合で、元の関門を新しく合格と宣言するものではありません。

04:47の回答では、同じ機械にon1・受信再生・八体300がまだ揃っていません。全ての実記録が揃うまで待ってください。別の機械の合格を混ぜたり、元の包みの関門を省いたりしません。

## 実行の準備と命令

Linux、Python3.12、8芯以上の専用機械、空き20GiB以上、通常のjobs.py、永続の実出力先が必要です。元c4の全関門が同じ機械で揃った後、候補の差分bundle又はGitHubの実コミットから別の自分のcheckoutを作り、HEADを92913206f5d3b4b4cfbcd1015e0aebf5351bf567へ固定してください。c4を前提とする差分はtools/smeshared.py一ファイルだけです。元の模型、関門のrootと出力を変更しません。

包みの全SHA256SUMSを照合してから、planで固定した全argv・設定を読みます。planは模型を開始しません。

```sh
sha256sum -c SHA256SUMS
python3.12 run_B5.py plan instruction12_B5_prod8_f01_seed1_20
```

実行用のパスと予約を実値で埋めます。B5_ROOTは保存済みoutput/evidenceの無い新しい永続作業先、B5_GATESは同じ機械の元c4の関門のrootです。B5_RESOURCEは元の八体実測のresource.json。B5_MEMはその実RSSと本番価格・20試行への条件差を説明した予約GB、B5_EXISTINGは開始直前の受付表の実予約合計です。実測を1.2倍以上し、既存予約＋今回の予約が24GBを超える場合は待ちます。マックの一体20のRSSを八倍した値を実測として代用しません。

```sh
python3.12 clearance_B5.py instruction12_B5_prod8_f01_seed1_20 \
  --root "$B5_ROOT" --source "$B5_SOURCE" --jobs "$B5_JOBS" \
  --mem "$B5_MEM" --existing-gb "$B5_EXISTING" \
  --resource-file "$B5_RESOURCE" --memory-note "$B5_MEMORY_NOTE" \
  --no-resource-warning --record "$B5_CLEARANCE"
python3.12 run_B5.py run instruction12_B5_prod8_f01_seed1_20 \
  --root "$B5_ROOT" --source "$B5_SOURCE" --jobs "$B5_JOBS" \
  --mem "$B5_MEM" --gate-root "$B5_GATES" --clearance "$B5_CLEARANCE"
```

clearanceの保存先の親は事前に作り、既存札を上書きしません。係が熱・swap・警告と受付表を実際に確認した直前の札だけを使います。入口はjobs.py run --wait --owner明示 --mem実値 --disk-path実出力先へ一本だけ通します。受付後にも同じ版・全関門のSHA・CPU・容量・直前の資源札を再検査します。受付待ちで札が10分より古くなった場合は開始検査で拒否し、停止と旧出力を残します。予約を下げたり、札の時刻や警告を補ったりして回避しません。

期限は指示11の2026-10-13 09:00 JST。入口の前と模型を開始する直前に確かめ、期限以後は新規模型を開始しません。走行中の本番へ停止信号を送りません。資源警告は保存して後続を禁止します。

## 終了確認と保存物

自然終了後、同じ受付内で全8体の台帳20件・原順・完了札と実版/物理サイズ、manifest全8辞書、通信各agentのerrorなし、辞書外0と点検40回、個体ごとのside/attention/stage2/evictions、最終SME/C*と模型/Python乱数各20件・大域乱数不変・性能全20件・元資料不変を点検します。外側終了0だけで通しません。実出力と証拠を全SHAで保存し、受付待ち・CPU枠確認・模型時間を分けます。CPU欄は受付後から固定版・関門・CPU・容量の確認終了までの秒数であることを明記します。

最初の例外又は不足はverification_01.jsonのfirst_errorへ保存し、その後を開始しません。修正・並べ替え・許容差追加をしません。B5(a)の一体ON200の全出力一致と、このB5(b)の20試行が実際に揃ってから受け入れます。B6・人間的な集団化・正式3b材料・本番は待機のままです。

## この入口の構造検査の範囲

通常受付59021（0.3GB）の旧入口01は8件中7件が通過し、既存rowsの依存linesを取り出していなかったため、合成台帳の読取でNameErrorとなりました。旧入口・旧停止・全合成資料を保持しました。別入口02へ同じ原字節のlinesを加え、条件・記録を減らさず、通常受付59320（0.3GB）で8件全てが通過しました。test_entry_02.logとstructural_tests_02.jsonを同梱します。実模型・クラウドの関門・本番は走らせていません。合成fixtureは作業場所へ残し、実関門札として同梱していません。コードと材料に変更がなければ、同じ8件を再実行しません。

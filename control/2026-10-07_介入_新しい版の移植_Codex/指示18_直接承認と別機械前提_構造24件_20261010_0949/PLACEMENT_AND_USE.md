# 指示18：登録した同じ種類の機械の前段証拠を使う別入口

アストラは2026-10-10T09:40:03 JSTのこのチャットで、指示17・18を直接承認した。元run.py・observe_independent.py・SHA256SUMS・STOP・全停止出力は残す。元の索引のUUは別問題として未解決であり、この包みで片側を選ぶ処理は作っていない。実機で動かすのはデスクトップ。

原の包みの台本の隣へ、指示17の同じspawn15二本に加えて、run_cohort18.py・cohort18.py・measurement_cohort18.pyを別名で置く。原のcompare.py・processes.py・runtime_capture.py・v311c_fingerprint.py・configs/・specs/・clearance.pyは保持する。原run.pyと原SHA256SUMSを置き換えない。新しい入口の受付後の再入口もrun_cohort18.py。独立の観察器は同じspawn15のまま。

変更範囲はreceive/replay（on2）とmeasure（on8_measure300）が読む、gate-on1-f0.1・gate-on1-f0.9・gate-receive-replay・gate-off8-parallelの前段証拠だけ。同じhost以外の証拠は、同じ機械型/CPU型/OS像/Python/包みSHA/固定候補版SHAを持つ登録機械の証拠に限る。on1の二本、受信と再生の二本の比較には原compare.pyをそのまま使い、同じhostを求める。on2の受信と再生も同じ機械Cで行う。列の本番とB5(b)の別入口の前提をこの変更へ含めない。

各機械A/B/C/Dはその機械でcomponents・off2・off8・off8-parallel・pilot20を実際に通してから、新入口でon1/on2/measureを開始する。新入口は原compare.completeでpilot20の版・20件の原順・実完了札と物理サイズ・通信・誕生/消去の必要記録・自然終了/警告なしを同じまま点検する。pilotに新しいpassed札は作らない。前の段が無い/失敗した場合は拒否する。

## 指紋と一覧の用意

まず正式な原SHA256SUMSの出所/SHAを確定する。原索引の衝突を含む控えを正規索引に代用しない。元の索引に衝突マーカーがあればcohort18.pyも拒否する。

PACKAGE_MANIFEST_instruction18.json（schema=1, files={相対ファイル名:SHA256}）へ、原索引の全行のファイル、原SHA256SUMS自体、新spawn15二本、新18三本を含む同じ包みの全ファイルSHAを固定する。一覧の自己参照を避け、このmanifest自体はfilesへ含めない。同じ原字節のmanifestを各機械へ配る。各機械は原索引の全SHAとmanifestの全SHAを実ファイルから照合する。包みの指紋はこのmanifestの原字節SHA。模型の固定候補版はc4cfed12a3944071951775b2c9373ca27705fb25、旧/独立の版と全旗は原runの固定値とvalidate/source HEADの検査を保持する。

各機械の通常受付内で、実際の包みと新しい保存先を指定して次の指紋を一度保存する（原模型は開始しない）。CPU型は/proc/cpuinfo、機械型とOS像はGoogleの実メタデータ、Pythonは実version/実装/実行ファイルSHA、machine-idとboot_idはそれぞれのSHAと元runと同じ連結host指紋を使う。生のIDは公開しない。メタデータの読取は[Google公式の手順](https://docs.cloud.google.com/compute/docs/metadata/querying-metadata)、キーは[公式一覧](https://docs.cloud.google.com/compute/docs/metadata/predefined-metadata-keys)に従う。

```text
python3.12 cohort18.py <当該機械の原包みのディレクトリ> <新しい永続保存先>/machine-fingerprint.json
```

各fingerprint.jsonを各実行rootのfingerprints/へ原字節で複製し、machine_registry_instruction18.jsonを次の形式で固定する。全機械のCOMMON六欄が一つでも異なれば入口は拒否する。machineの各項目は実fingerprintの全六欄＋host/machine_id_sha256/boot_id_sha256＋fingerprint_file（root内の相対名）＋fingerprint_sha256（原字節）。架空値・合成fixtureを実一覧へ入れない。

```json
{
  "schema": 1,
  "direct_instruction18_authorization": true,
  "cohort": {
    "machine_type": "実型", "cpu_type": "実CPU型", "os_image": "実像の完全名",
    "python": {"version": "実version", "implementation": "実装", "executable_sha256": "実SHA"},
    "package_sha256": "同じmanifestの実SHA", "version_sha": "c4cfed12a3944071951775b2c9373ca27705fb25"
  },
  "machines": ["上記の実fingerprintと原字節の所在/SHAを持つ各機械の辞書"],
  "imports": {
    "gate-on1-f0.1.json": {"host": "機械Aの実host", "path": "foreign/A/gate-on1-f0.1.json", "sha256": "原合格証拠の実SHA"},
    "gate-on1-f0.9.json": {"host": "機械Bの実host", "path": "foreign/B/gate-on1-f0.9.json", "sha256": "原合格証拠の実SHA"}
  }
}
```

この形式例は入力に使える実一覧ではない。importsには必要な元の実合格証拠だけを、原順・原字節・SHAを保持して載せる。元gates/のその機械の前関門は上書きせず、他機械の証拠はforeign/へ保存する。gate-receive-replayは同じ機械Cで比較してからDのimportsへ原字節で加える。一覧にないhost、証拠SHAやcandidateの不一致、未合格、同じ種類でない指紋、現在の機械の実指紋と違う一覧は拒否する。原passedの別名を作らない。

現在の機械の指紋は開始時に実読取し、host/Python/包みも一覧と照合する。機械が再起動したらhostが変わるため、原関門をその起動で通してから一覧へ新しい指紋を固定する。元の証拠を新しいhostに書き換えない。

## 受付からの開始と比較

新しい入口のrunの引数は元run_spawn15.pyと同じ。登録一覧は--rootのmachine_registry_instruction18.jsonから読む。例のすべてのパスと予約はその機械の正式な実値で埋める。原STOPのあるrootは元どおり拒否し、STOPの解除/無視/削除の手順は含めない。既存出力を再開・上書きしない。正式な再開rootが未確定なら始めない。

```text
python3.12 run_cohort18.py run on2_receive200 --source <元c4の実作業場所> --root <正式root-C> --jobs <実jobs.py> --mem <実測予約GB> --clearance <直前の正式資源札>
python3.12 run_cohort18.py run on2_replay200 --source <同じ元c4> --root <同じ正式root-C> --jobs <実jobs.py> --mem <実測予約GB> --clearance <新しい直前の正式資源札>
python3.12 compare.py <同じ正式root-C> receive-replay
python3.12 run_cohort18.py run on8_measure300 --source <元c4の実作業場所> --root <正式root-D> --jobs <実jobs.py> --mem <実測予約GB> --clearance <直前の正式資源札>
python3.12 measurement_cohort18.py <同じ正式root-D>
```

原のrunは通常受付のowner/--wait/実測mem/実出力disk-pathへ渡す。比較・指紋・測定点検も通常受付内で行う。CPU8・空き20GiB・予約合計24GB・同じ機械に他模型がない条件・直前資源札・元期限2026-10-11 00:00 UTC・版/全旗/STOP/重複/受付後再検査は保持。予約や期限を変える別指示はこの台本へ取り込まない。

runtime.jsonへ一覧原SHA、現在の実指紋、全要求関門と当地の前関門/20試行の原SHAをgate_inputs_instruction18として保存する。受付後にも読み直し、保存値から一つでも変われば模型を始めず拒否する。measurement_cohort18.pyでも同じ保存値を点検し、complete・実RSS・8体/並列/試験条件・原合格形式を保ったまま前段の同じhostの要求だけを新しい読み手へ渡す。元measurement.pyは残す。

終了後、原比較の全模型行・全名前集合・原順/字節・研究者辞書・全控え/乱数・試験行・必須メタデータと指示16のコード根拠付き時計欄を減らさない。一件でも違えば最初のファイル/行を保存して停止し、修正・並べ替え・許容差追加をしない。全機械の原出力/命令/版/起動/資源/比較/一覧/指紋/全SHAを永続先へ残す。後日の一台での鎖の再走行との照合はClaudeの別依頼を待つ。

## 準備の検査と限界

2026-10-10T09:49:30 JST、通常受付93628（0.3GB、owner明示、実出力disk-path）の合成構造24件が通過し、自然終了0。最大RSS34242560B、検査時間0.155833秒。元の関門条件のうち段をまたぐhost以外と、模型全引数・STOP/資源/期限/受付の原AST、同じ機械の原比較の拒否、未知機械/型差/Python差/起動差/原SHA差/原前関門/20試行の拒否を検査した。旧候補01を含む原21ファイルの前後SHA不変。これは実関門や実機の同一型の合格ではなく、合成fixtureは実証拠へ代用しない。実機使用・実一覧作成はデスクトップ担当で、原索引のUUと正式再開先の確定待ち。

旧候補01の23件通過と全fixtureは残す。原索引が空でも拒否する一条件を別候補02へ追加したため、別fixture02で24件を点検した。失敗の修正や原模型の再走行ではない。

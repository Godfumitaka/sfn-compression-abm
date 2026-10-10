# 指示22 デスクトップからの記録（版 94dbebc、D＋注意、#21 τ0.4）

受け箱の指示 84 の 2 に応じて、デスクトップの走行の係がまとめた。介入の組が、版 94dbebc（D＋注意）の中身の無い AssertionError を調べるための記録。
元は、D: に取ってあるケースのアーカイブ（tar.gz）だけ。走っている処理・クラウドの機械には触れていない。作業用の展開先は /mnt/d/sfn_runs/scratch_i22/（残してある）。

## 中身

- 完了した #21（τ0.4）の種 2・3・5・6・9：`21_seed002/` `21_seed003/` `21_seed005/` `21_seed006/` `21_seed009/`
- 止まった種 4（failed_rc3、AssertionError）：`21_seed004/`
- `SHA256SUMS`：このフォルダの全ファイル（このファイル自身は除く）の sha256。`sha256sum -c SHA256SUMS` で確かめられる。

各ケースのフォルダ：

- `spec.json`（元の命令。`command` が実際の argv、`observer_files` が観察器の sha256）、`run.log`、`result.json`、`status.json`、`time.log`
- `output/flag.json`、`output/manifest.jsonl`、`output/timing100.jsonl`、`output/timing/seedNNN.jsonl`
- `output/ledgers/cells/<cell>/`：台帳と完了の印 `seedNNN.done`（完了した種のみ）
- `output/side/<cell>/`：side の記録（jsonl・routing・sme・sme.states・answers.csv・useforget・probe.jsonl・useforget.evaluation_checks.json）
- `output/attention/<cell>/`、`output/retention/<cell>/`（`*.probe_checks.json` を含む）、`output/evictions/<cell>/`（`*.summary.json` を含む）
- `output/comparison_checkpoints/m1_at_trial{500,1000,2000,3000,4000,4999}.json`：M1 の確認の記録（完了した種のみ。種 4 のアーカイブには無い）

<cell> は `f0.5000_th2.1000_vt0.3842_first_order`。

入れなかったもの（元のアーカイブには入っている）：comparison_checkpoints の completed_* フォルダ（state・cache 類）、resources.jsonl、resource_warnings.jsonl、machine_before_start.json、queue_claim_published.json、admission_command.draft.json、pid.json。また、種 3・5・6・9 の `seedNNN.sme.states.jsonl.gz` は入れていない（大きさの決めごと。下の表）。

## 元のアーカイブ

sha256 は ~/cloud/ops/verb_fetched.tsv の値。使う前にこちらで計算し直し、6 個とも一致した。全量の記録は次の場所にある。

| ケース | 機械 | 状態 | D: | S3 | sha256 |
|---|---|---|---|---|---|
| 21_seed002 | sfn-verb-d | completed | `/mnt/d/sfn_runs/cloud/verb/sfn-verb-d/production_instruction30_p32/21_seed002.tar.gz` | `cloud_runs/verb/sfn-verb-d/production_instruction30_p32/21_seed002.tar.gz` | `e4433c4c1700a30843744ac367ca972f7f65754f535e7e437c8a5a11aac9f145` |
| 21_seed003 | sfn-verb-d | completed | `/mnt/d/sfn_runs/cloud/verb/sfn-verb-d/production_instruction30_p32/21_seed003.tar.gz` | `cloud_runs/verb/sfn-verb-d/production_instruction30_p32/21_seed003.tar.gz` | `9c6b3e1f509d9b4cc555ce8d64f3e5094284e207e147dfa9e7c1f29e0560a7c3` |
| 21_seed005 | sfn-verb-d2 | completed | `/mnt/d/sfn_runs/cloud/verb/sfn-verb-d2/production_instruction30_p32/21_seed005.tar.gz` | `cloud_runs/verb/sfn-verb-d2/production_instruction30_p32/21_seed005.tar.gz` | `e8af215a6b04dae60c64e89ff82dd350b338515ff01991a76577afa5790a49ca` |
| 21_seed006 | sfn-verb-d2 | completed | `/mnt/d/sfn_runs/cloud/verb/sfn-verb-d2/production_instruction30_p32/21_seed006.tar.gz` | `cloud_runs/verb/sfn-verb-d2/production_instruction30_p32/21_seed006.tar.gz` | `cbfaf214d4b20fb02d67f0dbc12354d4e7104a489dd2abcb3ef4658fc65b4b22` |
| 21_seed009 | sfn-verb-d3 | completed | `/mnt/d/sfn_runs/cloud/verb/sfn-verb-d3/production_instruction30_p32/21_seed009.tar.gz` | `cloud_runs/verb/sfn-verb-d3/production_instruction30_p32/21_seed009.tar.gz` | `dd83e5904db03c04975c16e0218d722b3f9bbb61e9f53e875a4b342070aa33f9` |
| 21_seed004 | sfn-verb-d2 | failed_rc3 | `/mnt/d/sfn_runs/cloud/verb/sfn-verb-d2/production_instruction30_p32/21_seed004.tar.gz` | `cloud_runs/verb/sfn-verb-d2/production_instruction30_p32/21_seed004.tar.gz` | `6f4c6951b76ac1fa0bc54a80246fefc9f6caaba88b62c94bc34bc8211805dc43` |

## 命令・config・観察器

- 6 ケースの spec.json は、種の番号（`--seeds` と出力先）以外は同じ。source_commit `94dbebc259981eec86efab1864f61df86ec68dd3`、source_tree `af6bc3da01a1dc4ed1096e68990bb603e73e2586`、runner_sha256 `ac6a8628d9a397aa8e5d579ff25844fb89eefb427a0e3666a84f04735b5e0fd0`。
- config は `/srv/verb/source_instruction30/config/sweep_verb_hide1_s1_2026-10-04.json`。**この config の中身はアーカイブに入っておらず、その sha256 もアーカイブのどこにも記録されていない。**このため config の sha256 は出せない（中身は source_commit／source_tree で決まるはず）。
- **flag.json の `commit` と台帳の `code_commit` は `4dc6a05d88ba10dbc22fd14ec77ec5c720e1c9a2`。spec の source_commit は `94dbebc259981eec86efab1864f61df86ec68dd3`。**二つが違う理由は、この記録からは分からない。
- observer_files（spec.json の値。6 ケースで同じ）：

  - `/srv/verb/report-results/control/動詞_クラウドの包み_2026-10-09/instruction27/tools/confirmed_hash.py`: `d340b030c3a1906bdaefa443b4b1fdc492473913d7c59344e467fad177f5b77e`
  - `/srv/verb/report-results/control/動詞_クラウドの包み_2026-10-09/instruction27/tools/checkpoint_observer.py`: `f789566f0846375cf7bb5f6e92d16875737483813f103080cf590d82535c6abb`
  - `/srv/verb/report-results/control/動詞_クラウドの包み_2026-10-09/instruction27/tools/instruction11_io.py`: `2db2c8bb0ede284e7071979dda3b1189fe6db2745a31f3e288f153c75ab8871e`
  - `/srv/verb/report-results/control/動詞_クラウドの包み_2026-10-09/instruction27/tools/timing100_observer.py`: `635916dbde8cca3dc2ac085e53cdf385a1fd1a18d77b5561633e382e481c866a`
  - `/srv/verb/report-results/control/動詞_クラウドの包み_2026-10-09/instruction27/tools/production/measurement_driver.py`: `b3f6222fd3d01dfcfebfe46bcd199af5cbadfb3a94962a3c404e4730125397ad`
  - `/srv/verb/report-results/control/動詞_クラウドの包み_2026-10-09/instruction27/gate/measurement_driver.py`: `6ca7af8f64dbc9599ac256f84d15930d37d102aeff56bf2e1f29b861c49217f4`

## 種 4 について（記録から読める事実）

- run.log：2026-10-10 05:11:09 に `err=AssertionError()` で止まり、`★★ エラーまたは不一致。止める`。そのあと concurrent.futures の TypeError（`object of type 'NoneType' has no len()`）が出ている。result.json の exit_code は 3、wall_seconds は約 330。
- manifest.jsonl は `{"cell": ..., "seed": 4, "error": "AssertionError()"}` の 1 行。
- retention と useforget は試行 0〜499、attention は試行 0〜498、台帳の試行の行は 0〜498（prediction_order）。timing100.jsonl は試行 400 まで。`output/timing/seed004.jsonl` は 0 バイト。
- `seed004.sme.jsonl.gz` は gzip が途中で切れている（展開すると unexpected end of file）。元のまま入れた。
- 種 4 の output は sme.states 以外を全部そのまま入れた（attention・台帳・evictions も含む。どれも 50 MB 以下）。

## 切り出しの規則

- 50 MB 以下のファイルは元のまま入れた。
- 50 MB を超えるファイルと、合計を小さくするために切った完了した種の attention・evictions は、**試行 0〜199（200 試行分）の頭だけ**を入れた。ファイル名に `head200` を付けてある。
- 規則：元のファイルを行の順に読み、各行の最上位の `trial` 欄（台帳は `record_type` が `trial` の行の `prediction_order`）が 200 以上になった最初の行で止める。その行から後ろは入れない。試行の欄の無い行（台帳の 1 行目の run_header）は、止める前なら残す。
- 切った後の残りも全部読み、試行が 200 未満の行が後ろに無いこと、頭の中で試行の番号が減っていないこと、元の gzip が途中で切れていないことを確かめた（37 件とも問題なし）。
- gzip のファイルは gzip のまま。頭は `gzip -n -9` で作り直したので、元のファイルの先頭のバイトとは一致しない（展開した中身の行は元と同じ）。
- 道具は /mnt/d/sfn_runs/scratch_i22/cut_head200.py。

### 切ったファイル（37 件）

| 入れたファイル | 元のファイル | 元の大きさ（バイト） | 元の sha256 | 残した行／元の行 | 試行の欄 |
|---|---|---|---|---|---|
| `21_seed002/output/attention/f0.5000_th2.1000_vt0.3842_first_order/seed002.head200.jsonl.gz` | `seed002.jsonl.gz` | 33021623 | `ab3aae3493fcec067a8b2cb6456f18c3402a92a2e7bbb0adce03051b0cd11692` | 200／5000 | trial |
| `21_seed002/output/evictions/f0.5000_th2.1000_vt0.3842_first_order/seed002.keys.head200.jsonl.gz` | `seed002.keys.jsonl.gz` | 24379240 | `6ebc14ba4402998ff28da0a090ec013a3afb483ac1b06dbf4ca40150d014f730` | 5566／145129 | trial |
| `21_seed002/output/ledgers/cells/f0.5000_th2.1000_vt0.3842_first_order/seed002.head200.jsonl.gz` | `seed002.jsonl.gz` | 75127882 | `871a5bbcf5fa8650080e4a087bb5ece337763d745d96ffde99709c117317cdcd` | 201／5001 | prediction_order |
| `21_seed002/output/retention/f0.5000_th2.1000_vt0.3842_first_order/seed002.head200.jsonl` | `seed002.jsonl` | 68486368 | `72415c0a9e749fa27d994d1de3dd70c2b78781c1eb0d6754583135a3eddf4e1d` | 200／5000 | trial |
| `21_seed002/output/side/f0.5000_th2.1000_vt0.3842_first_order/seed002.head200.jsonl` | `seed002.jsonl` | 68408719 | `d1bf98017313f332d67477746220fc6df64086e44de3e925d7f5e9ef0c15ca69` | 797／20027 | trial |
| `21_seed002/output/side/f0.5000_th2.1000_vt0.3842_first_order/seed002.routing.head200.jsonl` | `seed002.routing.jsonl` | 54596821 | `dc56a5beae95bea8340510125406ee01cde80a50dec9f6baf892eec7e50c16d8` | 313／7498 | trial |
| `21_seed002/output/side/f0.5000_th2.1000_vt0.3842_first_order/seed002.sme.head200.jsonl.gz` | `seed002.sme.jsonl.gz` | 117635102 | `7b2c344a93b27521e71e752cccf652319b09ce586346ade8c7bedb5a90222446` | 6959／181564 | trial |
| `21_seed002/output/side/f0.5000_th2.1000_vt0.3842_first_order/seed002.sme.states.head200.jsonl.gz` | `seed002.sme.states.jsonl.gz` | 1243689637 | `f4d575de5d6a9ee3562f3d35766c4fc31800c8a341628143a0a7dec1ee7f42ed` | 792／19800 | trial |
| `21_seed003/output/attention/f0.5000_th2.1000_vt0.3842_first_order/seed003.head200.jsonl.gz` | `seed003.jsonl.gz` | 38054570 | `b4f078b6c3df79587edf1b410a68b5ca186d218125c674d4a3d7de798633b45b` | 200／5000 | trial |
| `21_seed003/output/evictions/f0.5000_th2.1000_vt0.3842_first_order/seed003.keys.head200.jsonl.gz` | `seed003.keys.jsonl.gz` | 65723041 | `004b3117a39317685fc962f57fc7ff871d896b605420bbf260518c8ed09e0434` | 7036／190204 | trial |
| `21_seed003/output/ledgers/cells/f0.5000_th2.1000_vt0.3842_first_order/seed003.head200.jsonl.gz` | `seed003.jsonl.gz` | 87802650 | `4fc0c1f214548b5222136e45ab61706df98d25157a96cd891b2fe537e9364808` | 201／5001 | prediction_order |
| `21_seed003/output/retention/f0.5000_th2.1000_vt0.3842_first_order/seed003.head200.jsonl` | `seed003.jsonl` | 77587500 | `1620f392ad26eeb6bfcd43483010660dffd39dbc9bdbbc2785d53d93bd8f2c57` | 200／5000 | trial |
| `21_seed003/output/side/f0.5000_th2.1000_vt0.3842_first_order/seed003.head200.jsonl` | `seed003.jsonl` | 80783544 | `ef2a51236aa657a0fbd525d3b005fd23b07e3b366e64b1d835e846803fd57c9f` | 850／21235 | trial |
| `21_seed003/output/side/f0.5000_th2.1000_vt0.3842_first_order/seed003.routing.head200.jsonl` | `seed003.routing.jsonl` | 58085227 | `48fe1ac573ad7e5ddd8c9a690b1fc46f62bcd8c9ae623c067e76ee5eebd45bb6` | 295／7545 | trial |
| `21_seed003/output/side/f0.5000_th2.1000_vt0.3842_first_order/seed003.sme.head200.jsonl.gz` | `seed003.sme.jsonl.gz` | 191991718 | `459bacd913882f8ccf18a3ea1506782c2361dc57450c7bf4f0ed7a7d9f9bb440` | 8263／231781 | trial |
| `21_seed004/output/side/f0.5000_th2.1000_vt0.3842_first_order/seed004.sme.states.head200.jsonl.gz` | `seed004.sme.states.jsonl.gz` | 94063658 | `b9f1acbb0003f7233e028d2d0c3e242eac44ca68b4ab2df5ed6dbf7bee7d6dfc` | 792／1884 | trial |
| `21_seed005/output/attention/f0.5000_th2.1000_vt0.3842_first_order/seed005.head200.jsonl.gz` | `seed005.jsonl.gz` | 33199810 | `c19fe0c17444be541e4e6517de9c5d85fd4e9d440970bd5e7ccff695879cc221` | 200／5000 | trial |
| `21_seed005/output/evictions/f0.5000_th2.1000_vt0.3842_first_order/seed005.keys.head200.jsonl.gz` | `seed005.keys.jsonl.gz` | 37317823 | `0dcb07ea2d04fd408287c31a5ae9435bb8298babb0dccdee75131470edac8e69` | 5020／168221 | trial |
| `21_seed005/output/ledgers/cells/f0.5000_th2.1000_vt0.3842_first_order/seed005.head200.jsonl.gz` | `seed005.jsonl.gz` | 85717537 | `5a97c7438782a398cad3663c3e25a0ed9537fc254eee180d31c17877b2e24e93` | 201／5001 | prediction_order |
| `21_seed005/output/retention/f0.5000_th2.1000_vt0.3842_first_order/seed005.head200.jsonl` | `seed005.jsonl` | 70264323 | `000f28b50a7d33ed6d05cac958f3c7cdd356339bd74d4d775faaa659fbab1dc6` | 200／5000 | trial |
| `21_seed005/output/side/f0.5000_th2.1000_vt0.3842_first_order/seed005.head200.jsonl` | `seed005.jsonl` | 77647660 | `5ca43c8ba62bc8f796c404a0874509b1a4294eb8deb40e5917aff53a4acf63d7` | 799／20296 | trial |
| `21_seed005/output/side/f0.5000_th2.1000_vt0.3842_first_order/seed005.routing.head200.jsonl` | `seed005.routing.jsonl` | 56371863 | `c819f0d94e9790686e91bd79c22aabf2f2835395edb4c0100d4b0629aeee49b3` | 293／7485 | trial |
| `21_seed005/output/side/f0.5000_th2.1000_vt0.3842_first_order/seed005.sme.head200.jsonl.gz` | `seed005.sme.jsonl.gz` | 144418432 | `0701bacc0fac59816939566351eae68772f155292578b7322a0b92fa3f2b290f` | 6241／203668 | trial |
| `21_seed006/output/attention/f0.5000_th2.1000_vt0.3842_first_order/seed006.head200.jsonl.gz` | `seed006.jsonl.gz` | 32579108 | `bdeda86f73a07f4fe10a16e4feb928d155657d60225f1e32cf7bb040243c9b49` | 200／5000 | trial |
| `21_seed006/output/evictions/f0.5000_th2.1000_vt0.3842_first_order/seed006.keys.head200.jsonl.gz` | `seed006.keys.jsonl.gz` | 34106848 | `148b62c163a7b20efc05c644476227a84f2420f2751dbf5dda09dfcf7c8237ed` | 5303／164540 | trial |
| `21_seed006/output/ledgers/cells/f0.5000_th2.1000_vt0.3842_first_order/seed006.head200.jsonl.gz` | `seed006.jsonl.gz` | 83640384 | `ad5cd54b9e84cdcbd9cd74476604e91712624459154b34c3daed98624c18fe1b` | 201／5001 | prediction_order |
| `21_seed006/output/retention/f0.5000_th2.1000_vt0.3842_first_order/seed006.head200.jsonl` | `seed006.jsonl` | 69944556 | `97ea7938b06d8b12922bf5304cf13a939afe13defccd7e378eb76f7ab1ec664b` | 200／5000 | trial |
| `21_seed006/output/side/f0.5000_th2.1000_vt0.3842_first_order/seed006.head200.jsonl` | `seed006.jsonl` | 89392640 | `cb970ee4c0f0dbee369e259234d26c0059df1bc4dac4e092d3f638f7c349a7aa` | 797／20202 | trial |
| `21_seed006/output/side/f0.5000_th2.1000_vt0.3842_first_order/seed006.routing.head200.jsonl` | `seed006.routing.jsonl` | 56227548 | `290999d628ad404df831560163192b7fe1a75ba1dc773388e0fe95d487b55286` | 297／7507 | trial |
| `21_seed006/output/side/f0.5000_th2.1000_vt0.3842_first_order/seed006.sme.head200.jsonl.gz` | `seed006.sme.jsonl.gz` | 137252606 | `6eb8a8c8daefd912102b67ae119b12f8680b71ed6cd1a9a958d35e77594775f6` | 6511／200467 | trial |
| `21_seed009/output/attention/f0.5000_th2.1000_vt0.3842_first_order/seed009.head200.jsonl.gz` | `seed009.jsonl.gz` | 35360265 | `59601de0bb44e1b12fe5d20465f90b4c94bf97742f117c587f571b14b4dd9240` | 200／5000 | trial |
| `21_seed009/output/evictions/f0.5000_th2.1000_vt0.3842_first_order/seed009.keys.head200.jsonl.gz` | `seed009.keys.jsonl.gz` | 37820172 | `8c0c412c4bb789a00d29923e136d43b814f67de525f5ed3098fd008eba386868` | 5872／171194 | trial |
| `21_seed009/output/ledgers/cells/f0.5000_th2.1000_vt0.3842_first_order/seed009.head200.jsonl.gz` | `seed009.jsonl.gz` | 84971241 | `2e8adc87233a5b8ee9ac2ac90c219f56384ab79ce8f4ba8d8bc40dab05817579` | 201／5001 | prediction_order |
| `21_seed009/output/retention/f0.5000_th2.1000_vt0.3842_first_order/seed009.head200.jsonl` | `seed009.jsonl` | 71047028 | `530a1af8f7c47508e975c1b26070445b91e9fda76ef0253a3f8d41babcf6aa20` | 200／5000 | trial |
| `21_seed009/output/side/f0.5000_th2.1000_vt0.3842_first_order/seed009.head200.jsonl` | `seed009.jsonl` | 82152322 | `7cdcf3453bd20df764960cd45b3e66085a0054de6f9362757b29558f1ad2635d` | 804／20255 | trial |
| `21_seed009/output/side/f0.5000_th2.1000_vt0.3842_first_order/seed009.routing.head200.jsonl` | `seed009.routing.jsonl` | 54818465 | `ff599e1b649b8cff58c957bcd6324617afd7d4a7816640b814aaa47eb2d58e26` | 291／7449 | trial |
| `21_seed009/output/side/f0.5000_th2.1000_vt0.3842_first_order/seed009.sme.head200.jsonl.gz` | `seed009.sme.jsonl.gz` | 143909998 | `0219c63e63ee6dd38beb593d421d0d49e9c23cbc4516b2793983a671ed8bdeb7` | 7075／207191 | trial |

### 入れなかったファイル（4 件）

大きさの決めごと（sme.states の頭は種 4 と種 2 だけ）により、次は入れていない。全量は上の元のアーカイブにある。

| 元のファイル | 大きさ（バイト） | sha256 |
|---|---|---|
| `21_seed003/output/side/f0.5000_th2.1000_vt0.3842_first_order/seed003.sme.states.jsonl.gz` | 1599507976 | `cea51cdcc2381112c6b5f830731e09658d9b4e8d698cce7bd1b22095b7a9b51d` |
| `21_seed005/output/side/f0.5000_th2.1000_vt0.3842_first_order/seed005.sme.states.jsonl.gz` | 1424605786 | `d746b35e2f1bd50e8216a99b14a0aa3dc2fa8390c5e211eb53f8c3dbc5c39a5c` |
| `21_seed006/output/side/f0.5000_th2.1000_vt0.3842_first_order/seed006.sme.states.jsonl.gz` | 1378890334 | `7842fdf990694d0833e7646dc05f895b9baf1adbd9ebefa6cfc02e2551fdc765` |
| `21_seed009/output/side/f0.5000_th2.1000_vt0.3842_first_order/seed009.sme.states.jsonl.gz` | 1440893979 | `68606ddeb24c1a53c7faa7bd8058636bc8c557a34e1f406b848726517fd2889a` |


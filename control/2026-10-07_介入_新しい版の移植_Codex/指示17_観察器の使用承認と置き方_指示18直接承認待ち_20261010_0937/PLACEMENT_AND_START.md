# 指示17：別名観察器の置き方と開始手順（索引・正式再開先の確定待ち）

指示17でGoogle Cloudの関門機械での候補使用を承認済み。実機の操作はデスクトップが担当する。この係は原模型・原包み・原STOP・停止出力を変更していない。

原包みのrun.py・observe_independent.pyの隣へ、同梱のobserve_independent_spawn15.pyとrun_spawn15.pyを別名のまま置く。processes.py・runtime_capture.py・v311c_fingerprint.py・configs/・specs/・clearance.pyは原包みの同じものを使う。模型のargv・乱数・記録の取り付け順・版・試行数は変えない。

- observe_independent_spawn15.py：ae22f197a58289435387bbfb109084fabd26af15e3b5d0193d395b3f300faa5c
- run_spawn15.py：d38b21f7e0e1f6033a545319d379e8a9ecf79c70ff1ceb125b6797c76486fea3

同梱SHA256SUMS_instruction15とSHA256SUMS.originalは原索引の衝突を含む控えであり、正規索引として使用しない。原索引の元のGitにはUUの三段が残る。この係では片側を選ばず、修正・解決をしない。正式な原索引の出所とSHAを番号付き回答又はアストラ直接文面で確定してから、二本を追加した索引を仕上げる。

鎖は元のon1_f0.1_independent200から、Linux/Python3.12・同じ機械/同じ起動・原関門が有効な正式再開先で続ける。機械が再起動して証拠が無効なら、前の関門を同じ機械で通す。原STOPのあるrootでは入口が拒否する。STOPを解除・削除・書換え・無視する手順や、元の失敗をpassedへ変える手順は含めない。正式再開先が未指定のため、次の形の命令は未実行。

```text
python3.12 run_spawn15.py run on1_f0.1_independent200 --source <原e9の実作業場所> --root <STOP・重複・全原関門条件を満たす正式再開先> --jobs <当該機械のjobs.py> --mem <実測と条件差に基づく予約GB> --clearance <直前の正式資源札>
```

別入口は通常受付のowner・--wait・実測mem・実出力disk-pathを通し、受付後に版・全旗・同じhost・関門・予約合計24GB・CPU8・空き20GiB・重複をもう一度確かめる。元の入口期限2026-10-11 00:00 UTCを維持する。継続確認の10/13 09:00 JSTとは別の期限である。

構造5件と保存済み旧/新の先頭3試行の25項目一致は指示15・16の証拠を使い、変更がないため再実行しない。新候補の実模型spawn3・実機適用・関門の再走行はこの係では未開始。終了後の比較は指示16の指定時計だけを、コード根拠と両側のファイル・行・欄名・値を保存して扱い、全模型欄・試験行・原順・控え・乱数と必須メタデータは残す。

指示18の段をまたぐhost条件の緩和は、別機械の型・CPU・OS像・Python・包み/版SHAを一覧へ固定する案を受領したが、このチャットでのアストラ直接承認待ち。現行の同じhostの関門条件を維持し、新台本の実装・適用は未開始。

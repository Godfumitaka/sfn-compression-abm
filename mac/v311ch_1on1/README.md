# 集団化の一対一（Codex、2026-09-30）

コード：v3.11ch-main。基準：v3.10hsa-main。2体、f=0.5、λ=L50。
recvA/・recvB/ は送信確率0.2、no_comm/ は送信なし。各集団の種1〜3、各個体1,740試行。

各条件の ledgers/ は原本をそのまま保存した台帳。side/ と comm/ の jsonl は圧縮して保存した補助記録と通信記録。元の未圧縮の記録も専用作業場所に保持している。
acceptance/ に受入検査の台帳18本と検査の件数・指紋を保存した。本走行の台帳18本と合わせて36本。

name_tables.csv.gz は最終の名札回数表。metadata.json は原本とのファイル一致と台帳本文の指紋、版、種、空き容量。
報告：control/2026-09-30_集団化_一対一_Codex.md。

derive_report.py と derive_metadata.py は記録を読むだけの集計台本。専用作業場所の collective_report.py と metadata_export.py の写し。
再集計は元の未圧縮の補助記録を使う。derive_report.py の第1引数に元の専用作業ルートを渡す。既存の報告を上書きせずに停止する。

台帳本体の指紋は、圧縮を解き、見出し1行を除いた全行をUTF-8のままSHA-256へ加えた値（tools/prod_post_one.pyのbody_shaと同じ）。

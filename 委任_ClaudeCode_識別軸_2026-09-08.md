委任 — 識別軸の実装と本走行の起動（確定版）
宛先 Claude Code（ローカル）／ 依頼 Claude（Opus 5）／ 承認 アストラさん 作成 2026-09-08

```
作業ディレクトリ  /Users/tatsu-admin/sfn/sfn-compression-abm
リポジトリ        GODfumitaka/sfn-compression-abm
基点              f88b3c1faa57d3b20b79956a3633bfc18c0cbb01 が HEAD の祖先であること
種の sha256       73f17e28c463172fab3c585f8c593b43124b5485fa2eb34e9bdbbcd91fc4a073
                  （U-011 seed v2a.json）

```

★ 最初に読むこと
この委任の性質
★ これは実装の委任である。探索の委任ではない。 ★ 原因の特定は済んでいる。指定された変更だけを行うこと。
★ **設計を改善しない。**手順に無い変更を加えない。気づいた点は報告に書き、実装はしない。
停止条件（★ 当たったら何も作らずに止まり、報告する）

```
1  基点 f88b3c1 が HEAD の祖先でない
2  U-011 seed v2a.json の sha256 が上記と一致しない
3  手順1の照合で、土台となる4本が特定できない
4  手順6（pytest）が落ちる
5  ★ 手順7（決定論確認）で試行行が一致しない
6  手順に書かれていないファイルを変更する必要が生じた

```

★ **代わりのファイルを作らない。**必要なものが無ければ、作らずに止まって報告する。 ★ 2026-08-30 に、見えないファイルの代わりに79行の別物を新規作成した事故がある。
触ってよいファイル

```
変更してよい  abm/domains.py
              abm/abstraction.py
              sweep.py
              tests/ 配下（★ 欄数の期待値のみ）
新規作成      config/ 配下に8本のみ

★ 触らない  runs/ 配下すべて
            analysis_* 配下すべて
            config/sweep_v2a_*.json（★ 既存8本は読むだけ）
            U-011 seed v2a.json ／ gen v2a.py
            abm/agent_runtime.py ／ abm/loop.py ／ abm/filling.py ／ abm/sme.py

```

★ `gen v2a.py` を実行しない。★ 種を作り直さない。
コマンドの書き方
★ **1行1コマンド。**同じ行に注釈やコメントを書かない。 ★ zsh は対話シェルで `#` を解釈しない。過去に二度同じ事故がある。
手順0 — 基点の確認

```
git rev-parse HEAD

```


```
git merge-base --is-ancestor f88b3c1faa57d3b20b79956a3633bfc18c0cbb01 HEAD

```


```
git status --porcelain=v1 --untracked-files=normal

```


```
shasum -a 256 "U-011 seed v2a.json"

```

★ 種の sha256 が一致しなければ停止。★ `git status` の出力は報告に含めること。
手順1 — 土台となる設定ファイルの照合
`config/` には `sweep_v2a_*` が 8本 ある。うち4本を土台にする。
★ ファイル名で選ばない。中身で選ぶこと。

```
選ぶ条件  axes.theta_prime が [0.1, 0.9, 1.2] であるもの
除くもの  axes.theta_prime が [0.1, 0.4, 0.9] であるもの（★ 2026-09-07 の旧版）

```

★ `"_v2" in name` という判定を絶対に書かないこと。 ★ 文字列 `sweep_v2a` は `_v2` を含むため、8本すべてに誤マッチする。 ★ 除外条件を名前で書く必要がある場合のみ `endswith("_v2.json")` を使う。
土台の4本は次のはずである。★ 中身の照合で確認すること。

```
config/sweep_v2a_t067_w00_v2.json     tau_acc 0.67 ／ w 0.0
config/sweep_v2a_t067_w10_v2.json     tau_acc 0.67 ／ w 1.0
config/sweep_v2a_t200_w00_v2.json     tau_acc 2.0  ／ w 0.0
config/sweep_v2a_t200_w10_v2.json     tau_acc 2.0  ／ w 1.0

```

各ファイルが次を満たすことを確認し、満たさない場合は停止して報告する。

```
trial_count          1740
seeds.start          1
seeds.count          20
axes.f               [0.5]
axes.theta_prime     [0.1, 0.9, 1.2]
axes.fill_selection  ["most_frequent", "sample"]
axes.repair_scope    1点であること（★ 値は問わない）
output.dir           runs/v2a_t***_w**_2026-09-08

```

★ 4本すべての sha256 を計算し、報告に記録すること。

```
shasum -a 256 config/sweep_v2a_t067_w00_v2.json config/sweep_v2a_t067_w10_v2.json config/sweep_v2a_t200_w00_v2.json config/sweep_v2a_t200_w10_v2.json

```

手順2 — AgentConfig にフラグを二つ足す
`abm/domains.py` の `AgentConfig`（159行付近）に、既定値つきで追加する。

```python
    identification_graph: str = "all"    # "all" | "live"
    self_score_cache: str = "legacy"     # "legacy" | "off"

```

★ **既定値は現行挙動と同一であること。**既存走行と bit 一致させるための条件である。 ★ 同じクラスの `pending_claims` が同型の追加をしている。それに倣う。 ★ 想定外の値は `ValueError` を送出すること。
手順3 — 識別グラフと履歴観測グラフを分ける
`abm/abstraction.py` の `_definition_graph`（224行）は、28行（識別）と107行（履歴観測）から 呼ばれている。
★ **107行（履歴観測）は変えない。**墓石込みのまま据え置く。 ★ 28行（識別）だけが `identification_graph` を見る。
`identification_graph == "live"` のときのグラフ構築規則を、次に固定する。

```
relations      row.alive が真の行だけ
relation_ids   ★ 全構成素（墓石を含む）から作る
entities       ★ 全構成素（墓石を含む）の引数から作る

```

★ 死んだ行を物理的に取り除いてからグラフを組む方式にしない。 ★ 理由：`relation_ids` を生存行だけから作ると、死んだ関係のIDが実体として宣言され、 ★ 意図しない意味変更が乗る。`agent_runtime._definition_graph`（229行）と同じ規則にすること。
★ 実装は引数追加でも関数分割でもよい。 ★ ただし 107行の呼び出しが `"all"` 相当のままであることを、コード上で明示すること。
★ `abm/agent_runtime.py` と `abm/loop.py` は変更しない。両者は元から生存のみである。
手順4 — 自己点数キャッシュを切れるようにする
`abm/abstraction.py` の33行付近。

```
self_score_cache == "legacy"   現行どおり（★ 生存署名をキーにする）
self_score_cache == "off"      ★ キャッシュを読まず書かず、毎回 map_graphs で計算する

```

★ **キーの設計を直そうとしない。**今回は「使う／使わない」の二択だけを作る。 ★ 理由：キーを直す案は、キー一致なら自己点数も一致するという条件の設計が別に要る。範囲外。
手順5 — 走行ヘッダに2欄を足す
`sweep.py` の126〜140行付近の arm descriptor に追加する。

```
arm_identification_graph
arm_self_score_cache

```

値は設定ファイルの `fixed` から取る。★ `axes` にはしない。
★ 欄数を数える試験が複数ファイルに散っている。必ず grep で全部洗い出すこと。

```
grep -rn "ARM_DESCRIPTOR" .

```

★ 既知の所在は次の3ファイル。★ ただし grep の結果に従うこと。

```
abm/ledger.py
tests/test_ledger_b0b2.py
tests/test_b1_acceptance.py

```

★ 2026-08-30 に、3ファイルのうち2つだけ更新して pytest が1件落ちた事故がある。
★ `SPEC_B1_impl_2026-08-28.md` と `試験59箇所の一覧 2026-09-03.md` にも記述がある。 ★ **これらの文書は変更しない。**差分が生じたことを報告に書く。
手順6 — 試験

```
python3.12 -m pytest -q

```

★ 落ちたら停止して報告する。★ 期待値を書き換えて通そうとしない。 ★ ただし手順5で正しく更新すべき欄数の試験は、この限りではない。
手順7 — ★ 決定論の確認（★ 最重要）
★ 目的：既存の480走行を条件(a)「旧cached全行」として再利用できるかを判定する。
既存走行から θ′=0.90 のセルを一つ選び、同じ設定・同じ seed で1走行だけ再実行する。

```
python3.12 sweep.py --config config/sweep_v2a_t067_w00_v2.json --dry-run

```

★ まず `--dry-run` でセル名の一覧を得る。★ θ′=0.90・most_frequent のセル名を特定する。

```
python3.12 sweep.py --config config/sweep_v2a_t067_w00_v2.json --cells <セル名> --limit 1 --no-resume --workers 1

```

★ 既存の台帳を上書きしないこと。`output.dir` を一時ディレクトリへ変えた複製 config を作るか、 ★ 既存台帳を退避してから走らせる。★ どちらを採ったか報告に書く。 ★ 所要は約206秒（T=1740）。
★ 比較の仕方に注意すること。

```
★ ヘッダは必ず異なる。手順5で欄を2つ増やしたため
→ ★ ヘッダを除いた全試行行の sha256 を比較する
→ ★ 台帳の形式は abm/ledger.py を読んで確認すること

```

判定を報告する。

```
一致した    → ★ 手順8へ進む
一致しない  → ★ 停止して報告する。走行を起動しない

```

★ 一致しない場合、手順2〜4のどこかが既定値の挙動を変えている。原因を推測で直さない。
手順8 — 新しい設定ファイル 8本
土台の4本から、変更するのは次の3点だけ。

```
fixed に追加   identification_graph ／ self_score_cache
axes を縮小    theta_prime を [0.9, 1.2] にする（★ 0.1 を外す）
output.dir     新しいディレクトリへ

```

★ **それ以外は一切変えない。**seed、fill_selection、tau_acc、w、f、trial_count、 repair_scope、snapshot の設定はすべて土台のまま。

```
条件(b) fresh 全行   identification_graph="all"    self_score_cache="off"
条件(c) fresh live   identification_graph="live"   self_score_cache="off"

```

ファイル名は次とする。★ `v2a` を名前に含めないこと（glob の誤マッチを避けるため）。

```
config/sweep_ident_b_t067_w00.json      output.dir runs/ident_2026-09-08/b_t067_w00
config/sweep_ident_b_t067_w10.json      output.dir runs/ident_2026-09-08/b_t067_w10
config/sweep_ident_b_t200_w00.json      output.dir runs/ident_2026-09-08/b_t200_w00
config/sweep_ident_b_t200_w10.json      output.dir runs/ident_2026-09-08/b_t200_w10
config/sweep_ident_c_t067_w00.json      output.dir runs/ident_2026-09-08/c_t067_w00
config/sweep_ident_c_t067_w10.json      output.dir runs/ident_2026-09-08/c_t067_w10
config/sweep_ident_c_t200_w00.json      output.dir runs/ident_2026-09-08/c_t200_w00
config/sweep_ident_c_t200_w10.json      output.dir runs/ident_2026-09-08/c_t200_w10

```

★ 8本すべてに `--dry-run` を当て、展開される走行数を検算すること。

```
1本あたり  2 theta × 2 fill × 20 seed = 80走行
8本合計    ★ 640走行

```

★ 640 にならなければ停止して報告する。
手順9 — θ′=0.10 で削除が0であることの確認
既存480走行のうち θ′=0.10 のセル（160走行）で、構成素の削除イベントが0件であることを 確認する。★ `reg_del_events` の削除にあたる種別を数える。
★ 0件でない場合は報告する。その場合、手順8の config に θ′=0.10 を戻す必要があり、 ★ 走行数は 640 → 960 になる。
★ 走行中の台帳に `gzip -t` を当てない。書き込み中のファイルを必ず「壊れている」と報告する。
手順10 — commit
★ **アストラさんの承認を得てから commit すること。**変更内容を先に見せる。

```
git status

```

★ `runs/` `analysis_*` 種ファイルに変更が出ていたら停止する。
★ 既存の `config/sweep_v2a_*.json` 8本が未追跡なら、同じ commit に含めること。 ★ 理由：480走行の設定が git に無く、再現できない状態になっている。
commit メッセージ

```
識別グラフと自己点数キャッシュを軸として切り出す

```

手順11 — 走行の起動
★ 手順7が一致した場合のみ実行する。

```
caffeinate -is python3.12 sweep.py --config config/sweep_ident_b_t067_w00.json --workers 6

```

★ 8本を順に流す。★ `&&` で連結すると、前が失敗したとき後ろが走らない。 ★ 2026-08-31 に同じ形で片方が走らなかった事例がある。★ 各本の完了を確認して次へ進む形にすること。
★ **`--trial-count` を使わないこと。**T は減衰の梯子にも入るため、T を変えた走行は ★ 別T の走行と同じ軌跡の延長として読めない。
★ 中断しても `.done` のあるものは飛ばして再開する。同じコマンドで再開できる。
★ 起動したら、最初の2走行が正常終了することを確認してから離れること。

```
find runs/ident_2026-09-08 -name '*.done' | wc -l

```

★ 背景実行にする場合は `nohup` と `setsid` を使い、`< /dev/null` を付ける。 ★ 通常この委任では `nohup` を禁じているが、8.9時間の走行は完了を待てないため例外とする。 ★ 代わりに、最初の2走行の正常終了を確認する義務を課す。
★ 完走時の期待値は 640。
報告に含めること

```
1  手順0の git rev-parse HEAD と git status の出力
2  手順1で照合した4本のファイル名と sha256、想定との差分
3  手順5で grep が見つけた ARM_DESCRIPTOR の全所在（★ ファイルと行）
4  手順6の pytest の結果
5  ★ 手順7の判定（一致／不一致）と、比較に使った sha256、既存台帳の退避方法
6  手順8の --dry-run による走行数（★ 期待 640）
7  手順9の削除イベント数
8  手順11の起動時刻・PID・ログのパス・完走確認コマンド
9  ★ 手順に無い変更を加えたくなった箇所（★ 実装せず、記述だけ）

```

★ 数値を報告し、解釈は書かないこと。

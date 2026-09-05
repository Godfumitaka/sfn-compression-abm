# ルート直下スクリプト調査票

## 調査条件

- 対象は指定された 22 ファイルに限定した。
- 「他ファイルからの import」は、リポジトリ内の Python ファイルによるモジュール import を指す。文字列としてのファイル名言及やコマンド実行は含めない。
- 入出力パスはスクリプトから直接読み書きするものを記載した。`標準出力のみ` はファイルを作らず、集計結果を端末へ表示することを示す。
- 最終コミット日は `git log -1 --format=%cs -- <file>` で取得したコミッター日である。

## 一覧

| file | 最終コミット日 | 他ファイルからのimport有無 | 読み込む入力パス | 書き出す出力パス | 冒頭docstring1行 |
|---|---|---|---|---|---|
| `analyze_rev3.py` | 2026-09-02 | 無 | `--runs/cells/**/seed*.jsonl` または `seed*.jsonl.gz` | `--out/per_run.jsonl`、`--out/per_def.jsonl`（`--out` 既定値: `analysis`） | `analyze.py — 本走行の一次解析（rev2・2026-08-29）` |
| `analyze_rev4.py` | 2026-09-02 | 無 | `--runs/cells/**/seed*.jsonl` または `seed*.jsonl.gz` | `--out/per_run.jsonl`、`--out/per_def.jsonl`（`--out` 既定値: `analysis`） | `analyze.py — 本走行の一次解析（rev4・2026-08-30）` |
| `analyze_rev5.py` | 2026-09-02 | 無 | `--runs/cells/**/seed*.jsonl` または `seed*.jsonl.gz` | `--out/per_run.jsonl`、`--out/per_def.jsonl`（`--out` 既定値: `analysis`） | `analyze.py — 本走行の一次解析（rev5・2026-08-30）` |
| `analyze_rev6.py` | 2026-09-02 | 無 | `--runs/cells/**/seed*.jsonl` または `seed*.jsonl.gz` | `--out/per_run.jsonl`、`--out/per_def.jsonl`（`--out` 既定値: `analysis`） | `analyze.py — 本走行の一次解析（rev6・2026-08-30）` |
| `probe.py` | 2026-09-02 | 無 | `[走行ディレクトリ]/cells/*/*.jsonl.gz`（既定: `runs/arm0ext_2026-08-31`） | 標準出力のみ | `probe.py — 台帳を直接読み、三つを一度に出す（読むだけ・書き込みなし）` |
| `probe2.py` | 2026-09-02 | 無 | `[走行ディレクトリ]/cells/*/*.jsonl.gz`（既定: `runs/main_2026-08-31`） | 標準出力のみ | `probe2.py — 判断1 と U-09h の材料を台帳から出す（読むだけ）` |
| `probe3.py` | 2026-09-02 | 無 | `<走行ディレクトリ>/cells/*/*.jsonl.gz` | 標準出力のみ | `probe3.py v2 — 賭けC の機構形（登録II）を台帳から直読する。` |
| `probe4.py` | 2026-09-02 | 無 | `<走行ディレクトリ>/cells/*/*.jsonl.gz` | 標準出力のみ | `probe4.py — 神話の「反証到着率 × 寿命」を def 単位で直接数える。` |
| `probe5.py` | 2026-09-02 | 無 | `<走行ディレクトリ>/cells/*/*.jsonl.gz` | 標準出力のみ | `probe5.py — 時間的回収の探針。` |
| `probe6.py` | 2026-09-02 | 無 | `<走行ディレクトリ>/cells/*/*.jsonl.gz` | 標準出力のみ | `probe6.py — 「修復が完了しない」を打ち切りの交絡を除いて測る。` |
| `probe7.py` | 2026-09-02 | 無 | `<走行ディレクトリ>/cells/*/*.jsonl.gz` | 標準出力のみ | `probe7.py — 未回収の ② が「削除」なのか「未修復」なのかを分ける。` |
| `probe8.py` | 2026-09-02 | 無 | `<走行ディレクトリ>/cells/*/*.jsonl.gz` | 標準出力のみ | `probe8.py — (B2)「スロットが照合に載らない」の実体を分ける。` |
| `probe9.py` | 2026-09-02 | 無 | `<走行ディレクトリ>/cells/*/*.jsonl.gz` | 標準出力のみ | `probe9.py — (B2)「照合に載らなくなる」に 対照 を取る。` |
| `checks.py` | 2026-09-02 | 無 | `--per-def` で指定する `per_def.jsonl` | 標準出力のみ | `checks.py — 走行後の検算 3 件（追加走行なし。per_def.jsonl だけを読む）` |
| `checks2.py` | 2026-09-02 | 無 | `--per-def` で指定する `per_def.jsonl` | 標準出力のみ | `checks2.py — rev5 の新欄を使った検算（analysis3/per_def.jsonl を読む）` |
| `checks3.py` | 2026-09-02 | 無 | `--per-def` で指定する `per_def.jsonl` | 標準出力のみ | `checks3.py — 検算 5〜10（再走行なし。analysis3/per_def.jsonl だけを読む）` |
| `checks4.py` | 2026-09-02 | 無 | `--per-def` で指定する `per_def.jsonl` | 標準出力のみ | `checks4.py — 検算11〜13（analysis4/per_def.jsonl。rev6 の alive_preds / dead_preds を使う）` |
| `sweep.py` | 2026-09-02 | 有（`tests/test_verbatim_theta.py`） | `--config` の JSON、`U-011_seed_v1.json`、再開時の `config["output"]["dir"]/cells/**/seed*.done` | `config["output"]["dir"]/sweep_config.json`、`cells/<cell>/seed*.jsonl[.gz]`、`cells/<cell>/seed*.done`、`manifest.jsonl`。較正時は `_calibration/` 以下と `calibration.json` | `sweep.py — 本走行の掃引ドライバ` |
| `sweep_ORIGINAL.py` | 2026-09-02 | 無 | `--config` の JSON、`U-011_seed_v1.json`、再開時の `config["output"]["dir"]/cells/**/seed*.done` | `config["output"]["dir"]/sweep_config.json`、`cells/<cell>/seed*.jsonl[.gz]`、`cells/<cell>/seed*.done`、`manifest.jsonl`。較正時は `_calibration/` 以下と `calibration.json` | `sweep.py — 本走行の掃引ドライバ` |
| `sweep_ldecouple.py` | 2026-09-02 | 無 | `--config` の JSON、`U-011_seed_v1.json`、再開時の `config["output"]["dir"]/cells/**/seed*.done` | `config["output"]["dir"]/sweep_config.json`、`cells/<cell>/seed*.jsonl[.gz]`、`cells/<cell>/seed*.done`、`manifest.jsonl`。較正時は `_calibration/` 以下と `calibration.json` | `sweep.py — 本走行の掃引ドライバ` |
| `build_battery.py` | 2026-09-02 | 無 | 生成時: `U-011_seed_v1.json`。検証時: `--verify` の JSON と同名の `.sha256` | 生成時: `--out` の JSON と同名の `.sha256`（既定: `battery_v1.json` と `battery_v1.json.sha256`）。検証時: 標準出力のみ | `build_battery.py — 電池（Sel 評価用の場面集合）を走行前に生成する` |
| `build_battery_v2.py` | 2026-09-02 | 無 | 生成時: `U-011_seed_v1.json`。検証時: `--verify` の JSON と同名の `.sha256` | 生成時: `--out` の JSON と同名の `.sha256`（既定: `battery_v1.json` と `battery_v1.json.sha256`）。検証時: 標準出力のみ | `build_battery.py — 電池（Sel 評価用の場面集合）を走行前に生成する` |

## `analyze_rev3.py`〜`analyze_rev6.py` の相互差分

### rev3（比較の起点）

- 対象四版の起点で、台帳から `per_run.jsonl` と `per_def.jsonl` を生成する。
- ファイル名は rev3 だが、冒頭 docstring の版表示は `rev2` のままである。
- 後続版で追加される `last_change`、`change_times`、`born`、`m_alloc`、述語生死欄はまだ出力しない。

### rev4（rev3 から）

- `per_def` に `last_change` を追加した。
- OA の説明を実装どおり「述語が一本でも欠けた割合」へ直した。
- OA の記述を「未決」から、主 `gstar`・副 `supply`・`applied` の扱いを明記する形へ変更した。

### rev5（rev4 から）

- `per_def` に `change_times`、`born`、`m_alloc` を追加した。
- 欠けた述語の割合 `OA_gstar_frac` と `n_alive_predicates` を追加した。
- OA の画面集計対象に `OA_gstar_frac` を追加した。

### rev6（rev5 から）

- 走行末の生存述語と墓石述語を分ける `predicate_split()` を追加した。
- `per_def` に `alive_preds` と `dead_preds` を追加した。
- 既存の画面集計経路は変えず、冒頭の版表示を rev6 に変更した。

## `sweep.py` と `sweep_ORIGINAL.py` の差分

- `sweep.py` は `axes.verbatim_theta` の任意軸を列挙し、セル名の `_vt...` 部分を生成・解析し、走行タスク・ヘッダ・完了記録へ値を渡す。`sweep_ORIGINAL.py` にはこの軸がない。
- `sweep.py` は `verbatim_theta` が指定された場合、0 より大きい有限の実数かを検証する。
- `sweep.py` は `fixed` の `pending_claims`、`pending_gamma`、`pending_hold_cost` を `AgentConfig` へ渡す。`sweep_ORIGINAL.py` は渡さない。

## `build_battery.py` と `build_battery_v2.py` の差分

- ペイロードの版が `battery-v1` から `battery-v2` へ変更されている。
- v1 の L3 は各場面の役割ユナリーをプールから一様に再抽出するが、v2 は全場面の実在ユナリーをシャッフルして場面間で置換する。
- v2 はこの置換により L3 の述語周辺分布を厳密に維持する設計とし、検証時の説明もその条件を明記する。

## 未参照かつ無出力のファイル

該当なし。`sweep.py` 以外は対象内で他の Python ファイルから import されていないが、いずれもファイルまたは標準出力へ結果を出す。

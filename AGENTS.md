# AGENTS.md — SfN圧縮ABM 層A 実装契約（エージェント運用規律）

> このファイルは Codex（素のGPT-5.5でも `codex -p fugu` でも同じ）が読む運用規律。
> 目的は層Aの一段ずつの実装と、「素のCodex vs Fugu」を**同一pytestで突き合わせる検証実験**を同時に成立させること。

## 0. 位置づけ（単一の真実源）

- 単一の真実源は `SPEC_v3_0625.md`。本AGENTS.mdはそれを実装に落とす際の運用規律であり、**SPECと矛盾したらSPECが優先**。
- コードがSPECとズレたら、**コードを直す前にSPEC（または本文書）の該当節を直し**、「該当節を読み直して」と指示し直す。コード側でズレを握りつぶさない。

## 1. 言語規約（SPEC運用規約より）

- 説明・コメント・コミットメッセージ・PR本文は**日本語**。
- コード識別子（クラス名・関数名・変数名・enum値・JSONLフィールド名・configキー）はSPEC指定の**英語のまま**。翻訳しない。

## 2. 着手前に必ず読む（毎ステップ）

着手するBUILD ORDER（§11）の段に対応するSPEC節を、**コードを書く前に**読む。最低限:

- §1.2 規律（破ったら全結果無効）
- §3 / §3.2 / §3.2b 三層グラフ・入力型分離・権限分割
- §5.3 圧縮目的関数と単一threshold判定
- §9 禁止条項 と §9.2 静的検査の限界

読まずに書き始めない。

## 3. 絶対規律 —— "滑り" の禁止（最重要）

新しいインスタンスは「不透明領域は別扱いが綺麗では」「ここで正解を補正すれば動く」と滑りやすい。
**その"気の利かせ方"こそが本研究を壊す**。以下を破った実装は破棄する。

1. **正解挙動を stipulate しない**（§6.0）。各オペレータは `G_star` / `held_out_edge` / `M` の置き方だけ決める。「この型ならこう振る舞え／この型は間違えろ」を書いた瞬間に非循環性（関門B）が壊れる。誤るか正しく振る舞うかは §5.3 の単一threshold判定に**内生**させる。
2. **`if(target_type)` を書かない**（C3）。剪定・生成・採点・MDL・写像・前処理・alignment→prediction・通信bufferのどれも領域で分岐しない。**辞書dispatch・クラス多相・関数ポインタ・配列index・前処理feature（`prototype_required`・`len(G)-len(M)`・`seed_id`・特定述語の有無・提示位置）による地域の実質復元も禁止**（§9.2）。
3. **leakage を構造で禁じる**（C2）。エージェント側4モジュール（写像器・候補生成・MDL・通信器）と `ModelScorer` / `BaselinePredictor` は `OracleView` / `G_star` / `held_out_edge` / `Feedback` を**引数に取らない**。自己申告 boolean（`committed_prototype_before_holdout` 等）は証拠にしない。
4. **二ゲインを合算しない**（C4）。`transfer_gain` と `coordination_gain` を足した量をどこにも作らない。
5. **送信は生インスタンスの無作為サンプリングのみ**（C5）。プロトタイプ経由送信を書かない。
6. **§6.2/§6.4 の「低threshold→…／高threshold→…」は期待結果（反証対象）であって仕様ではない**。構造pytestでこの誤答方向をassertしない（assertした瞬間その run は非循環性の証拠にならない）。

> 迷ったら「正解を埋め込もうとしていないか」「領域で分岐していないか」を自問する。該当するなら手を止めてSPECに戻る。

## 4. 進め方（BUILD ORDER・一段ずつ）

- §11 の順に一段ずつ。各段のゲートは **pytest green** かつ人間が自走確認できること。
- 後続関門の指標は手前が緑になるまで**読まない・実装しない**（C10）。
- 層B（付録Z: 減衰ダイヤル・系統異質性注入・再注入による神話生成・偽陽性/偽陰性分解・opaque二分割・オラクル共生成）は**関門Cが緑になるまで実装しない**。動き出すと前倒ししたくなるが、スコープを広げない。
- 横断変更の前に、**影響範囲を先に説明してから**編集する。
- 穴が出たらSPEC/本書に戻して直す。実装の目的は結果でなく**仕様の穴出し**（§11-11）。

## 5. 本検証実験（A/B）でのpytestの書き方

このリポジトリは「素のCodex vs `codex -p fugu`」を同一pytestで突き合わせる。したがってpytestは**構造的性質**を検査すること。挙動の近道をテストにしない。

- **型レベル到達不能を検査する**（§12・C2）。例: `AgentInput` / `AgentState` / `AgentConfig` が `G_star` / `held_out_edge` / `target_type` / `seed_id` / `Feedback` を型として持てない。`AgentInput` が serialization round-trip で `G_star` と共有参照を持たない。
- **権限分割を検査する**（§3.2b・C11）。`ModelScorer` / `BaselinePredictor` が `OracleView` を受けない、`QuadrantClassifier` が `target_type` / `seed_id` を受けない、`OracleEvaluator` が agent/state を参照しない。
- **誤答方向をassertしない**。「鋳型方向に外したか」等は §5.3 判定に内生する観測対象であって合格条件ではない。
- **関門A緑判定（§12）は実装妥当性を条件にする**。「ベースライン比で勝つ」等の望ましい結果を合格条件にしない（成功する刺激集合を選ぶまで反復する＝オーバーフィットを防ぐ）。

## 6. やってはいけないショートカット（具体・過去の停止級由来）

- opaque を「別扱い」にして tie-break 規則を opaque 専用に変える → **禁止**（§5.3・tie-break は全条件共通の一つ）。
- 非観測辺を「採点不能」にして `L(D_obs|H)` をゼロ化する → **禁止**（一辺が尤度項を持たないことと全データ尤度ゼロ化は別物・§6.6）。
- role_divergence で実行時プロトタイプを覗いて衝突する `G_star` を後生成する → **禁止**（version (a)・事前固定 near-miss・§6.4）。
- 述語名を「漏洩だから」と消す → **禁止**（tiered identicality は原典SMEの機構・§5.2）。構造の証拠は `flat_matcher_baseline` で取る。
- threshold を複数箇所で別単位に分散させる → **禁止**（§5.3・作用する単一量は `total_score(best_alignment) >= threshold` の一本）。
- オペレータに `AgentConfig`（threshold / lambda / correction_mode / prototype有無）を渡す → **禁止**（C12・`PerturbationParams` と別型）。同一 `instance_id` の `G_star` は全 threshold 腕で同一。

## 7. コミット / PR 規律

- 一段＝一PRを目安。PR本文に以下を日本語で明記する:
  1. 対応するSPEC節
  2. 追加したpytestが検査する**構造的性質**（挙動でなく）
  3. §3 の6規律に滑りがないことの自己点検
- SPECを変更したら、差分を付録E形式（停止理由・対処・新たな矛盾の有無）で記録する。

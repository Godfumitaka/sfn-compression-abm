# SME と共通の物配置の見積もり：根拠

報告は [control の日本語報告](../../control/2026-10-03_SMEに沿った照合_見積もり_Codex.md)。模型の修正・本番の走行は行っていない。種1の64試行と小さな照合だけを並列1で測った。

- `scoped_timings.csv`：共通配置とv4の役割競合の小例の照合時間。試作は完全なSMEではない。
- `v4_role_fixture.json`：見える名前と本数が等しい二入力。五物の全列挙で正しい組のみ対応が1個。高階の役割情報を入れない単体検査の案。
- `ordered_arguments_example.json`：実関数の正誤とAの保持採点で順の扱いが違った小例。蓄積先だけ小例の写しに替えた。
- `common_layout_visibility.json`：八葉の各一階を伏せても端の物が見えることの確認。
- `small_example.json`：現行照合の関係と物の対応が食い違う完全入力の小例。
- `matcher_calls.csv`：直接呼び出し87箇所。間接経路は報告の表。
- `desktop_arm_times.csv`：デスクトップの並列14の既存ログから数えた腕ごとの分。
- `trial_profile.json`：種1・64試行の時間の内訳。短いTと測定の負荷込みで、本番への直接延長はしない。
- `literature_metadata.json`・`official_materials.json`：公式URLと取得資料の指紋。第三者の全論文・ソース・例題を転載していない。

再測定にはPython3.12.13と、コミット3380344の自分の複製を`source/`に置いた作業場所を用いる。`scoped_examples.py`は`measure_matcher.py`の限定試作を読む。`profile_trial.py`はsourceを作業場所として実行する。これらは見積もりの測定台本で、模型の置換版・関門を通った版ではない。取得した原典と台帳・sideはマックのCodex自身の作業場所に全て残した。

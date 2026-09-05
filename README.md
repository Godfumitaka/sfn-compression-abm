## 正準構成
- 掃引ドライバ: sweep.py
- 一次解析: analyze_rev6.py
- 検算: checks4.py
- 電池生成: build_battery.py（現存する battery_v1.json の生成元）
- 本番解析出力: analysis_p_g0/, analysis_p_g1/, analysis_p_off/
  （analyze_rev6.py による）

## archive/
過去世代。ポスターの図の生成には使用していない。

## unresolved/
正準性が未確定。ポスターの図の生成には使用していない。

## 既知の未解決点
- build_battery_v2.py は L3 の述語周辺分布を厳密に維持する
  設計だが、現存する battery_v1.json は build_battery.py
  （v1）で生成されている。

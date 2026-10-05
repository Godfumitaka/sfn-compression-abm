
## 2026-10-05T11:40:08：段4の下見（stopped）

計画160本。模型走行2本、既存分類による解析1本が完了。

条件は旧い照合3380344上のN3／支持の割合×A／D（τ=0.4）×4水準×世界1・2×種1〜5、全1,740試行、λ=0.01873710622997919、Uは既定の答え。一本ずつ共有受付run --wait・--mem・--disk-pathで実行した。種21〜40には触れていない。事前予想は変更しない。

次の走行を起動せず停止した。

```
RuntimeError('走行が完了しない: Codex-shop-deco-read-skeleton_N3_A_w1_s001; resources.jsonとrun.logを参照')
```

停止した条件と段階：
```json
{
  "seed": 1,
  "selection": "N3",
  "retention": "A",
  "world": 1,
  "level": "skeleton",
  "tag": "skeleton_N3_A_w1_s001",
  "phase": "analysis"
}
```

詳細はローカルpreview/progress.jsonと、該当する走行または解析のrun.log・validation.json・候補のcheck.jsonに保存した。未完の分を完了と扱わない。

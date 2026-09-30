"""台帳・通信・小例の受入検査の記録をまとめる。"""
import json
from pathlib import Path
import sys

SOURCE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(SOURCE / "tools"))
import v311c_report

ROOT = SOURCE.parent / "outputs"
rows = []
for name in ["q0", "repeat1", "repeat2", "noprobe", "recvA_check", "notags", "solo_notags", "solo_q0"]:
    for cp in sorted((ROOT / name / "comm").glob("run*.jsonl")):
        p = v311c_report.one_population(str(ROOT / name), str(cp))
        c, s = p["突き合わせ"], p["数"]
        assert p["失敗"] == 0
        assert c["個体の課題の和"] == p["個体"] and c["誤答の出どころの和"] == p["個体"]
        assert c.get("一致の四分類の和", 0) == p["probes"]
        assert all(c[k] == 1 for k in ["送信＝配達", "配達＝受け取りの記録", "束のある試行は実際に答えた試行",
                                     "一個体一試行に束は一つまで", "受け取りで束を送らない"])
        assert s.get("誤答_?", 0) == 0
        assert all(s.get("STATS_" + k, 0) == 0 for k in ["recv_score_changed", "recv_merit_changed", "dC_mismatch"])
        rows.append({"condition": name, **p})
h = json.loads((ROOT / "checks_hashes.json").read_text())
assert all(p["equal"] for p in h["body_pairs"]) and h["comm_repeat_equal"]
(ROOT / "checks_counts.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n")
lines = [
    "# 集団化を urta に載せ直す：受入検査（2026-09-30、Codex）", "",
    "基準 v3.10urta-main（74b60da）。元の集団化 v3.11ch-main（eeb524c）。Python 3.12.13。--hist-role --score-role と --u-struct --relearn-init --tie-struct --amb-local を付けた。種21〜40は使用していない。", "",
    "台帳本体の SHA-256 は、圧縮を解いて見出し1行を除いた本文の指紋。本文が一字でも異なれば値が変わる。", "",
    "| 検査 | 結果 |", "|---|---|",
    "| ① 基準版との一致 | seed001・1740試行の本文一致。全機能を切った二体の各個体も300試行で単独と一致 |",
    "| ② 通信なしの二体と単独 | 名札の長さを揃え、seed001・seed1001の本文一致 |",
    "| ③ 沈黙と予測の数 | 元の小例1件合格。走行でも一個体一試行の束は最多1 |",
    "| ④ 開示前の固定・受け手の入力 | 元の小例1件合格。公開入力は束・名札・送り手・宛先だけ |",
    "| ⑤ 参照先 | 元の小例1件合格。多段追加・共有参照・予測への参照・連鎖除外・付け直しを検査 |",
    "| ⑥ 受信A/Bと空の記憶 | 元の小例1件合格。役割の履歴を受信経路で確認する追加例1件合格 |",
    "| ⑦ 名札の回数と抽選 | 元の小例1件合格 |",
    "| ⑧ 名札の費用 | 元の小例1件合格。短い通信走行で費用の見込みと実額の食い違い0件 |",
    "| ⑨ 受信の採点 | 短い通信走行で既存の席の通常採点0件、功績の変更0件。Uの親の対応から観察一回を集め、新世代へ初期評価だけ入れる追加例が合格 |",
    "| ⑩ 同じ試行で再送しない・再現性 | 二回の台帳2組と通信記録が一致 |",
    "| ⑪ 回答の一致の試験の非介入 | 試験あり・なしで台帳2組が一致。追加の保存・復元の小例1件合格 |",
    "| ⑫ 件数の和 | 下記すべてで課題数・誤答の出どころ・四分類・送配受の件数が一致 |", "",
    "E は取り込み先の各候補を仮に適用して費用を比較する処理。仮の適用にも、親が指す子だけを観察する履歴の直しが入る追加例1件が合格。", "",
    "小例はファイルごとに別のPythonプロセスで実行：集団化6、役割の追加3、受信・保存復元の追加2、U照合・初期評価9、候補ごとの棄権6、履歴5、採点5、B＋E11、v3.9 16、合計63件合格。受信の追加例は同化先を固定し、受信・役割観察・U照合・新世代の初期評価の実関数を通した。", "",
    "回答の一致の試験では、histrole・ustruct・relearninit・tiestruct の記録も保存・復元する。追加例はそれぞれの記録を試験中に変更し、試験後の一致を確認した。", "",
    "短い集団検査は300試行、λ=0.01873710622997919。受信A/Bの通信検査はq=0.5、二体。①の基準版との比較は1740試行。個体iの世界の種は元の実装どおり「集団の種＋1000×i」。回答の一致の試験だけの種は900000＋集団の種。", "",
    "| 本文の比較 | 種 | 行数 | SHA-256（両側共通） |", "|---|---:|---:|---|",
]
for p in h["body_pairs"]:
    lines.append(f"| {p['a']} / {p['b']} | {p['seed']} | {p['left']['rows']} | {p['left']['sha256']} |")
lines += ["", "通信記録の再現一致：最終要約（経過時間など）を除いて一致。", "",
          "| 短い検査 | 集団の種 | 世界課題 | 送信 | 受信 | 通常採点の変更 | 功績の変更 | 費用の食い違い |",
          "|---|---|---:|---:|---:|---:|---:|---:|"]
for p in rows:
    s = p["数"]
    lines.append(f"| {p['condition']} | {p['run']} | {s['課題']} | {s.get('送信',0)} | {s.get('受け取り',0)} | {s.get('STATS_recv_score_changed',0)} | {s.get('STATS_recv_merit_changed',0)} | {s.get('STATS_dC_mismatch',0)} |")
lines += ["", "実行台本：tools/v311c_checks/codex_runs.py。元のacc_runs.shは出力削除の処理があるため使用していない。全出力を専用のoutputs/に保持。", ""]
report = "\n".join(lines)
(SOURCE / "tools/v311c_checks/2026-09-30_Codex_urta_受入検査.md").write_text(report)
results = SOURCE.parents[2] / "codex_v310ans_2026-09-30/results/control"
(results / "2026-09-30_集団化_urta_受入検査_Codex.md").write_text(report)
print(f"受入検査の報告を保存：{len(rows)}集団")

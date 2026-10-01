"""全九腕の記録を保存し、日本語の数の表を作る。結果の解釈はしない。"""
from __future__ import annotations
import collections
import csv
import gzip
import hashlib
import json
import pathlib
import shutil
import subprocess
from run_worldv4 import ROOT, SOURCE, CELL, ARMS, completed, run_root, now

ARMS_MAIN = [arm for arm in ARMS if arm.startswith("v4spc_")]

def merge_csv(paths, output):
    fieldnames = None
    rows = 0
    with gzip.open(output, "wt", encoding="utf-8", newline="") as out:
        for path in paths:
            opener = gzip.open if str(path).endswith(".gz") else open
            with opener(path, "rt", encoding="utf-8", newline="") as source:
                reader = csv.DictReader(source)
                if fieldnames is None:
                    fieldnames = reader.fieldnames
                    writer = csv.DictWriter(out, fieldnames=fieldnames)
                    writer.writeheader()
                assert reader.fieldnames == fieldnames
                for row in reader:
                    assert 1 <= int(row["seed"]) <= 20
                    writer.writerow(row)
                    rows += 1
    return rows

def aggregate(metrics):
    result = dict(trials=0, memory_bits_sum=0, outcomes=collections.Counter(), reasons=collections.Counter(),
                  variants=collections.Counter(), switch=collections.defaultdict(collections.Counter),
                  roles=collections.defaultdict(collections.Counter), sources=collections.defaultdict(collections.Counter))
    for m in metrics:
        result["trials"] += m["trials"]
        result["memory_bits_sum"] += m["memory_bits_sum"]
        for dest, key in (("outcomes", "outcomes"), ("reasons", "abstain_reasons"), ("variants", "variants")):
            result[dest].update(m[key])
        for dest, key in (("switch", "switch"), ("roles", "role_outcomes"), ("sources", "sources")):
            for group, counts in m[key].items():
                result[dest][group].update(counts)
    return result

def percent(n, total):
    return f"{100*n/total:.4f}%" if total else "対象0"

def main():
    records = {}
    totals = {}
    public = ROOT / "results/mac"
    public.mkdir(exist_ok=True)
    seed_worlds = {}
    for arm in ARMS_MAIN:
        metrics = []
        for seed in range(1, 21):
            assert completed(arm, seed)
            m = json.loads((ROOT / "analysis" / arm / f"seed{seed:03d}/metrics.json").read_text())
            assert m["arm"] == arm and m["seed"] == seed and m["trials"] == 1740
            assert all(m["checks"][key] == 0 for key in ("check1_mismatch", "check2_mismatch", "hash_mismatch", "args_unrestored", "score_R_differs", "answer_R_differs"))
            if seed in seed_worlds:
                assert seed_worlds[seed] == m["world_hash"]
            else:
                seed_worlds[seed] = m["world_hash"]
            metrics.append(m)
        records[arm] = metrics
        totals[arm] = aggregate(metrics)
        dest = public / arm
        dest.mkdir(exist_ok=True)
        reference_flags = json.loads((run_root(arm, 1) / "flag.json").read_text())
        for seed in range(1, 21):
            assert json.loads((run_root(arm, seed) / "flag.json").read_text()) == reference_flags
        shutil.copy2(run_root(arm, 1) / "flag.json", dest / "flag.json")
        (dest / "run_metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=1) + "\n")
        assert merge_csv([ROOT / "analysis" / arm / f"seed{seed:03d}/trials.csv.gz" for seed in range(1, 21)], dest / "trials.csv.gz") == 34800
        answers = merge_csv([run_root(arm, seed) / "side" / CELL / f"seed{seed:03d}.answers.csv" for seed in range(1, 21)], dest / f"answers_{arm}.csv.gz")
        assert answers == totals[arm]["outcomes"]["correct"] + totals[arm]["outcomes"]["wrong"]
        with (dest / "sha256.jsonl").open("w") as out:
            for m in metrics:
                ledger = pathlib.Path(m["ledger_path"])
                file_hash = hashlib.file_digest(ledger.open("rb"), "sha256").hexdigest()
                out.write(json.dumps({k: m[k] for k in ("seed", "trials", "world_hash", "body_sha", "code_commit", "ledger_path")} | {"compressed_sha256": file_hash}, ensure_ascii=False) + "\n")
    report = ROOT / "results/control/2026-10-01_世界v4の取り直し_Codex.md"
    original = report.read_text()
    original = original.split("## 本番", 1)[0]
    analysis_commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=SOURCE, text=True).strip()
    total_trials = sum(t["trials"] for t in totals.values())
    lines = [original, "## 本番の完了", "", f"- {now()}：9腕×種1〜20、180本、{total_trials}課題を完了。各走行1740課題。通常世界の関門用一本は、この180本に含めない。",
             "- Aは--cf-learnなし、Cは--cf-learnあり。腕のL50/L90という名前は、この委任書で指定された0.0187371/0.0990004を指す。",
             f"- 走行180本のコードは234bf04dbc352db3336cde6a4be6e7ea832b000aで同じ。最終の解析道具の保存コミットは{analysis_commit}。",
             "- 解析の履歴のキーだけを再利用する変更を含め、小さな検査10件通過。世界v4・通常世界ともλ0.2・種1の1740試行の対応先CSVと検査JSONは、変更前後でバイト単位で一致。名前と回数の値は各試行から読む。",
             "- 走行の並列数は2から4へ、解析の並列数は1から4へ変更。一本ごとの旗・模型・検査は同じ。解析の進行役の切り替え中も、実行中の再計算は完了させてから検査して再利用した。",
             "- 全腕・同じ種の世界の指紋は一致。開示の確率0.5、二階の関係を伏せる設定は全走行で確認。種21〜40の使用・閲覧は0。",
             "- 棄権：答えを出さなかった試行。以下の割合の分母は正解・誤答・棄権を含む全課題。",
             "- ビット：記憶を符号で書く長さ。平均記憶量は、試行末のsideのbits_afterを学習期間の1740試行で平均し、20走行で平均したもの。",
             "- 対応先：答えた席が照合で指した場面の関係。伏せた関係・見えている関係・対応先なしの三つで数える。棄権には答えた席が無いので対応先の表の分母から除く。",
             "", "## 全課題と平均記憶量", "", "| 腕 | 忘却λ | 全課題 | 正解（割合） | 誤答（割合） | 棄権（割合） | 平均記憶ビット |", "|---|---:|---:|---:|---:|---:|---:|"]
    for arm, t in totals.items():
        counts = t["outcomes"]
        cells = [f"{counts[k]}（{percent(counts[k],t['trials'])}）" for k in ("correct", "wrong", "abstain")]
        lines.append(f"|{arm}|{ARMS[arm]['price']}|{t['trials']}|" + "|".join(cells) + f"|{t['memory_bits_sum']/t['trials']:.6f}|")
    lines += ["", "## 棄権の理由", "", "理由は台帳のabstain_reasonの値をそのまま数える。各行の和はその腕の棄権数。", ""]
    reason_names = sorted({reason for t in totals.values() for reason in t["reasons"]})
    lines += ["|腕|" + "|".join(reason_names) + "|合計|", "|---|" + "---:|"*(len(reason_names)+1)]
    for arm, t in totals.items():
        lines.append("|"+arm+"|"+"|".join(str(t["reasons"][k]) for k in reason_names)+f"|{sum(t['reasons'].values())}|")
    lines += ["", "理由の読み：no_prototype＝予測用の元の場面なし、below_threshold＝照合の基準未満、no_definition＝使う定義なし、below_tau＝発話の支持の門未満、no_projectable_relation＝投影できる関係なし、ambiguous_projection＝候補の答えが決まらない、no_gap_candidate＝欠けた位置に答える候補なし。", "",
              "## 切り替わる葉の課題と変種", "", "held_out_switchは、伏せた関係が同時に切り替わる二本の葉の一方だった課題の印。", "",
              "|腕|変種|葉の全課題|正解|誤答|棄権|誤答率（葉の全課題が分母）|", "|---|---|---:|---:|---:|---:|---:|"]
    for arm, t in totals.items():
        for variant in ("A", "B"):
            c = t["switch"][variant]; denominator = sum(c.values())
            lines.append(f"|{arm}|{variant}|{denominator}|{c['correct']}|{c['wrong']}|{c['abstain']}|{percent(c['wrong'],denominator)}|")
    lines += ["", "## 話した席の対応先と当たり外れ", "", "|腕|対応先|答えた課題（分母）|正解|誤答|", "|---|---|---:|---:|---:|"]
    labels = {"held_out": "(i)伏せた関係", "visible": "(ii)見えている関係", "none": "(iii)対応先なし"}
    for arm, t in totals.items():
        for key, label in labels.items():
            c = t["roles"][key]
            lines.append(f"|{arm}|{label}|{sum(c.values())}|{c['correct']}|{c['wrong']}|")
    lines += ["", "## いつもAを答える比べの相手", "", "比べの相手は、変種を無視して、切り替わる葉にいつもAの中身を答える。Bの課題だけで外すため、この表の誤答率は実際のBの割合。模型の誤答率も、棄権を含む同じ葉の全課題を分母にする。", "",
              "|腕|葉の全課題|Bの課題|いつもAの誤答率|模型の誤答数|模型の誤答率|模型の棄権数|", "|---|---:|---:|---:|---:|---:|---:|"]
    for arm, t in totals.items():
        denominator = sum(sum(c.values()) for c in t["switch"].values())
        baseline = sum(t["switch"]["B"].values()); wrong = sum(c["wrong"] for c in t["switch"].values()); abstain = sum(c["abstain"] for c in t["switch"].values())
        lines.append(f"|{arm}|{denominator}|{baseline}|{percent(baseline,denominator)}|{wrong}|{percent(wrong,denominator)}|{abstain}|")
    lines += ["", "## 走行ごとの数", "", "|腕|種|正解|誤答|棄権|葉A（正/誤/棄）|葉B（正/誤/棄）|平均記憶ビット|", "|---|---:|---:|---:|---:|---|---|---:|"]
    for arm, metrics in records.items():
        for m in metrics:
            c = m["outcomes"]; s = m["switch"]
            joined = ["/".join(str(s.get(v,{}).get(k,0)) for k in ("correct","wrong","abstain")) for v in ("A","B")]
            lines.append(f"|{arm}|{m['seed']}|{c.get('correct',0)}|{c.get('wrong',0)}|{c.get('abstain',0)}|{joined[0]}|{joined[1]}|{m['memory_bits_mean']:.6f}|")
    count_checked = sum(m["checks"]["check1_seats"] for metrics in records.values() for m in metrics)
    lines += ["", "## 照合と保存", "", f"- 全{total_trials}試行の世界・状態を台帳と照合。採点の記録の{count_checked}席で対応先と写した引数を再計算し、不一致0。二回の再計算の不一致・状態の変化・復元不能の引数・答えた定義の不一致は全走行で0。",
              f"- 本番180本と通常世界の関門用一本の元の台帳、side、回答、試験の記録を {ROOT}/runs/ に保持。",
              "- mac/<腕>/ に旗、20走行の数、全34800試行のtrials.csv.gz、answers_<腕>.csv.gz、台帳の本体と圧縮ファイルのsha256を保存。元の台帳への場所をsha256.jsonlに併記。",
              "- mac/world_v4_spc_2026-10-01/ に実行・検査・解析・表作成の道具と関門の記録を保存。", ""]
    report.write_text("\n".join(lines))
    meta = public / "world_v4_spc_2026-10-01"
    meta.mkdir(exist_ok=True)
    for name in ("run_worldv4.py", "check_gate1.py", "analyse_worldv4.py", "report_worldv4.py", "status_worldv4.py", "verify_exports.py", "gate1_passed.json", "history_cache_check.json", "history_cache_plain_check.json", "extrap_reader_before.py", "run_events.jsonl"):
        shutil.copy2(ROOT / name, meta / name)
    shutil.copy2(SOURCE / "config/sweep_b2_hide_s1_2026-09-22.json", meta / "sweep_b2_hide_s1_2026-09-22.json")
    patch = subprocess.check_output(["git", "diff", "bc5cd130ed14533d3f8be891bd99f5ee316601c9"], cwd=SOURCE)
    (meta / "analysis_tools.patch").write_bytes(patch)
    with (ROOT / "results/control/2026-09-30_Codex_進み具合.md").open("a") as out:
        out.write(f"\n- {now()} 世界v4の取り直し：180/180本、{total_trials}課題の走行・集計完了。採点の{count_checked}席で対応先と引数の不一致0。台帳181本を保持。9腕の表と種ごとの数をcontrolへ記録。\n")
    print(json.dumps(dict(arms=9, runs=180, trials=total_trials, checked_seats=count_checked, report=str(report)), ensure_ascii=False))

if __name__ == "__main__":
    main()

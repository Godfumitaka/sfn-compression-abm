"""N3の80本の開始・停止・終了を同じ報告へ追記し、数表を保存する。"""
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
import json
import shutil
import subprocess
import time
from common import ROOT, AREA, digest

HERE = Path(__file__).resolve().parent
PREVIEW = AREA / "preview_n3"
REPORT = AREA / "report"
NAME = "control/2026-10-06_飾り_SME版_Codex.md"
BRANCH = "codex/shop-deco-sme-2026-10-06"


def git(root, *args):
    return subprocess.check_output(["git", "-c", "user.name=Codex", "-c", "user.email=codex@openai.com", *args],
                                  cwd=root, text=True).strip()


def publish():
    progress = json.loads((PREVIEW / "progress.json").read_text())
    stamp = datetime.now().astimezone().isoformat()
    status = progress["status"]
    text = [f"\n## {stamp}：SME・N3先行80本（{status}）", "",
        "利用者の順序変更に従い、支持の割合の旗の実装・関門を保留する。N3の80本の下見とその報告の後に再開する。支持の旗の試作は別の作業場所へ保存し、今回のN3走行には適用しない。", "",
        f"N3：模型{progress['runs_completed']}／80本、解析{progress['analyses_completed']}／80本が完了。条件はA／D（τ=0.4）×skeleton・current・plus4・plus8×世界1・2×種1〜5、各1,740試行、λ=0.01873710622997919、Uは既定の答え。種21〜40には触れない。P-05cとD-04vは変更しない。", "",
        "模型・解析を一本ずつ`~/jobs/jobs.py run --wait --mem --disk-path`へ渡す。CPUは前置きの上限（物理CPU数−2）と熱の条件を確認する。模型1.0GB、解析3.0GBを受付の見込みとして指定する。実測の時間と資源を各一本のresources.jsonへ保存する。", "",
        "解析は既存のSME候補再生`tools/selcands_sme.py`を使用する。予測前の記憶・入力・設定・乱数、対応・答え・保留状態、学習／忘却後の記憶を全試行で元の状態記録と照合する。候補観測と記憶量の観測が状態を変えないことを確認する。元の全出力（完了印を含む）の前後のSHA-256を照合する。"]
    if (PREVIEW / "old_stop.json").exists():
        stop = json.loads((PREVIEW / "old_stop.json").read_text())
        text += ["", f"旧版の残りを止めた記録時刻：{stop['stopped_at']}。完了は模型{stop['runs_completed']}本・解析{stop['analyses_completed']}本。旧版の未完の条件は`{stop['last_current']['tag']}`。完了した出力と未完の出力を保存した。停止対象の稼働過程は{len(stop['terminated_pids'])}個。"]
    result = {k: v for k, v in progress.items() if k != "records"}
    index = []
    groups = defaultdict(list)
    public_unique = {}
    for record in progress["records"]:
        summary_path = Path(record["summary"])
        s = json.loads(summary_path.read_text())
        assert s["trial_count"] == 1740 and s["validation"]["C_end_mismatch"] == 0
        groups[(s["retention"], s["world"], s["level"])].append(s)
        pkey = (s["world"], s["level"], s["seed"])
        if pkey in public_unique:assert public_unique[pkey] == s["public_entity_distribution"]
        public_unique[pkey] = s["public_entity_distribution"]
        index.append({**record, "summary_sha256": digest(summary_path),
            "run_resources": json.loads(Path(record["run_resources"]).read_text()),
            "analysis_resources": json.loads(Path(record["analysis_resources"]).read_text())})
    if status == "complete":
        assert progress["runs_completed"] == progress["analyses_completed"] == len(index) == 80
    if groups:
        text += ["", "ドアを問う日だけの件数。外れのうち、門を通り正しく答える候補があるものを選び間違い、ないものを区別の喪失とする。黙りは二分類に入れない。各行は解析完了した種の合計。", "",
            "| 世界 | 保持 | 水準 | 完了した種 | 日 | 正解 | 外れ | 黙り | 選び間違い | 区別の喪失 |",
            "|---|---|---|---|---|---:|---:|---:|---:|---:|"]
        aggregates = []
        for (retention, world, level), cases in sorted(groups.items()):
            if status == "complete":assert {s["seed"] for s in cases} == set(range(1, 6))
            days = {c: dict(sum((Counter(s["days"][c]) for s in cases), Counter())) for c in ("e", "n")}
            memory = {"mean_total_bits": sum(s["memory"]["mean"]["total"] for s in cases) / len(cases),
                "mean_final_total_bits": sum(s["memory"]["final"]["total"] for s in cases) / len(cases),
                "max_total_bits": max(s["memory"]["max_total_bits"] for s in cases),
                "mean_final_definitions": sum(s["memory"]["final"]["defs"] for s in cases) / len(cases),
                "mean_final_parts": {k: sum(s["memory"]["final"][k] for s in cases) / len(cases)
                    for k in ("G", "Idef", "S", "seat2", "Hc", "Fc", "nF", "nH", "nU")}}
            aggregates.append({"retention": retention, "world": world, "level": level, "days": days, "memory": memory})
            for c, label in (("e", "例外"), ("n", "通常")):
                text.append(f"| {world} | {retention} | {level} | {','.join(str(s['seed']) for s in cases)} | {label} | " +
                    " | ".join(str(days[c].get(k, 0)) for k in ("正解", "外れ", "黙り", "選び間違い", "区別の喪失")) + " |")
        text += ["", "記憶量（既存sealmem.mem_partsと同じ式、全試行の合計は元のC_endと一致）。平均は各完了種を等しく平均する。", "",
            "| 世界 | 保持 | 水準 | 全試行平均bits | 終了時平均bits | 最大bits | 終了時平均定義数 |",
            "|---|---|---|---:|---:|---:|---:|"]
        for r in aggregates:
            m = r["memory"]
            text.append(f"| {r['world']} | {r['retention']} | {r['level']} | {m['mean_total_bits']:.3f} | {m['mean_final_total_bits']:.3f} | {m['max_total_bits']} | {m['mean_final_definitions']:.3f} |")
        distributions = defaultdict(Counter)
        for (world, level, seed), counts in public_unique.items():
            distributions[(world, level)].update({int(k): v for k, v in counts.items()})
        text += ["", "公開実体数の分布。同じ種・世界・水準を保持A／Dで重複して数えない。完全場面の実体集合は移植の関門で全水準同一と確認済み。", "",
            "| 世界 | 水準 | 2実体 | 3実体 | 4実体 | 合計 |", "|---|---|---:|---:|---:|---:|"]
        for (world, level), counts in sorted(distributions.items()):
            text.append(f"| {world} | {level} | {counts[2]} | {counts[3]} | {counts[4]} | {sum(counts.values())} |")
        result.update(aggregates=aggregates, public_entity_distributions={f"w{w}_{l}": dict(c) for (w, l), c in distributions.items()})
    if status == "stopped":
        text += ["", "次の一本を起動せず停止した。", "", "```text", progress["stopped_reason"], "```",
                 "", f"停止した条件と段階：`{progress['current']}`。run.log・resources.json・validation.jsonをローカルに保存する。"]
    else:
        text += ["", "各一本の完了後に次を受付へ渡し、終了・停止時にこの報告へ追記してpushする。支持の割合の作業はN3の80本の報告が済むまで進めない。"]
    proof = HERE / "preview_n3"
    proof.mkdir(exist_ok=True)
    for name in ("plan.json", "source_sha256.json", "old_stop.json"):
        if (PREVIEW / name).exists():shutil.copy2(PREVIEW / name, proof / name)
    (proof / "summary.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    (proof / "run_index.json").write_text(json.dumps(index, ensure_ascii=False, indent=2) + "\n")
    (proof / "tables.md").write_text("\n".join(text) + "\n")
    git(ROOT, "add", str(HERE.relative_to(ROOT)))
    if git(ROOT, "diff", "--cached", "--name-only"):
        git(ROOT, "commit", "-m", f"飾りのSME・N3先行下見の{status}を保存")
    git(ROOT, "push", "origin", f"HEAD:refs/heads/{BRANCH}")
    source_commit = git(ROOT, "rev-parse", "HEAD")
    text += ["", f"作業コミット：`{source_commit}`。元の台帳・side・候補・記憶量・実測時間はローカルの`{PREVIEW}`に保存する。成績の良し悪しは記述しない。"]
    assert not git(REPORT, "status", "--porcelain")
    git(REPORT, "fetch", "origin", "refs/heads/results-2026-09-27:refs/remotes/origin/results-2026-09-27")
    git(REPORT, "checkout", "--detach", "origin/results-2026-09-27")
    report_proof = REPORT / HERE.relative_to(ROOT) / "preview_n3"
    shutil.copytree(proof, report_proof, dirs_exist_ok=True)
    with (REPORT / NAME).open("a") as stream:stream.write("\n".join(text) + "\n")
    git(REPORT, "add", NAME, str(report_proof.relative_to(REPORT)))
    git(REPORT, "commit", "-m", f"飾りのSME・N3先行下見の{status}を報告")
    for attempt in range(6):
        try:
            git(REPORT, "push", "origin", "HEAD:refs/heads/results-2026-09-27")
            break
        except subprocess.CalledProcessError:
            if attempt == 5:raise
            git(REPORT, "fetch", "origin", "refs/heads/results-2026-09-27:refs/remotes/origin/results-2026-09-27")
            git(REPORT, "rebase", "origin/results-2026-09-27")
            time.sleep(2)
    receipt = {"status": status, "source_commit": source_commit, "report_commit": git(REPORT, "rev-parse", "HEAD"),
               "runs_completed": progress["runs_completed"], "analyses_completed": progress["analyses_completed"]}
    (PREVIEW / "report_done.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(receipt, ensure_ascii=False), flush=True)


if __name__ == "__main__":publish()

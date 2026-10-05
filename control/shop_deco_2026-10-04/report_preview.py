"""160本の終了・停止を承認済みの報告に追記する。数表だけを出し成績を評価しない。"""
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
import hashlib
import json
import subprocess
import time
from run_registered import AREA, ROOT

REPORT_NAME = "control/2026-10-04_お店の飾りの軸_Codex.md"
BASE_URL = "https://github.com/Godfumitaka/sfn-compression-abm"


def git(where, *args):
    return subprocess.check_output(["git", "-C", str(where), *args], text=True, stderr=subprocess.STDOUT).strip()


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def main():
    progress = json.loads((AREA / "preview/progress.json").read_text())
    status = progress["status"]
    dest = ROOT / "control/shop_deco_2026-10-04/stage4"
    dest.mkdir(exist_ok=True)
    date = datetime.now().isoformat(timespec="seconds")
    text = [f"\n## {date}：段4の下見（{status}）", "",
        f"計画160本。模型走行{progress['runs_completed']}本、既存分類による解析{progress['analyses_completed']}本が完了。", "",
        "条件は旧い照合3380344上のN3／支持の割合×A／D（τ=0.4）×4水準×世界1・2×種1〜5、全1,740試行、λ=0.01873710622997919、Uは既定の答え。一本ずつ共有受付run --wait・--mem・--disk-pathで実行した。種21〜40には触れていない。事前予想は変更しない。"]
    result = {k: v for k, v in progress.items() if k != "records"}
    if status == "complete":
        assert progress["runs_completed"] == progress["analyses_completed"] == len(progress["records"]) == 160
        groups = defaultdict(list)
        index = []
        unique_public = {}
        for record in progress["records"]:
            s = json.loads(Path(record["summary"]).read_text())
            assert s["trial_count"] == 1740 and s["args_unrestored"] == s["C_end_mismatch"] == 0
            assert all(s["check"][k] == 0 for k in ("予測が本物と違う", "一位が本物の選びと違う", "一位でやり直した答えが本物と違う"))
            key = (s["selection"], s["retention"], s["world"], s["level"])
            groups[key].append(s)
            pkey = (s["world"], s["level"], s["seed"])
            if pkey in unique_public:
                assert unique_public[pkey] == s["public_entity_distribution"]
            unique_public[pkey] = s["public_entity_distribution"]
            index.append({**record, "summary_sha256": digest(Path(record["summary"])),
                "run_resources": json.loads(Path(record["run_resources"]).read_text()),
                "analysis_resources": json.loads(Path(record["analysis_resources"]).read_text())})
        totals = []
        for key, cases in sorted(groups.items()):
            assert len(cases) == 5 and {s["seed"] for s in cases} == set(range(1, 6))
            selection, retention, world, level = key
            days = {cue: dict(sum((Counter(s["days"][cue]) for s in cases), Counter())) for cue in ("e", "n")}
            memory = {"mean_total_bits": sum(s["memory"]["mean"]["total"] for s in cases) / 5,
                      "mean_final_total_bits": sum(s["memory"]["final"]["total"] for s in cases) / 5,
                      "max_total_bits": max(s["memory"]["max_total_bits"] for s in cases),
                      "mean_final_definitions": sum(s["memory"]["final"]["defs"] for s in cases) / 5,
                      "mean_final_parts": {k: sum(s["memory"]["final"][k] for s in cases) / 5 for k in ("G", "Idef", "S", "seat2", "Hc", "Fc", "nF", "nH", "nU")}}
            totals.append({"selection": selection, "retention": retention, "world": world, "level": level,
                           "days": days, "memory": memory})
        text += ["", "ドアを問う日だけの件数（各行は種1〜5の合計）。外れは既存のselcandsの候補別の答えで分類した。門を通って正しく答える候補がある外れを選び間違い、ない外れを区別の喪失とする。黙りはこの二分類に入れない。", "",
                 "| 世界 | 選び方 | 保持 | 水準 | 日 | 正解 | 外れ | 黙り | 選び間違い | 区別の喪失 |", "|---|---|---|---|---|---:|---:|---:|---:|---:|"]
        for row in totals:
            for cue, day in (("e", "例外"), ("n", "通常")):
                d = row["days"][cue]
                text.append(f"| {row['world']} | {row['selection']} | {row['retention']} | {row['level']} | {day} | " + " | ".join(str(d.get(k, 0)) for k in ("正解", "外れ", "黙り", "選び間違い", "区別の喪失")) + " |")
        text += ["", "記憶量は既存のsealmem.mem_partsのビット数（全体の表＋定義数の符号＋骨組み＋席の状態と中身）。全試行の平均は各種1,740試行を等しく平均し、終了時は種1〜5の平均。最大は全試行・全5種の最大。RSSとは別の量。各試行の合計はv310beのC_endと一致し、全状態の指紋と全場面の一致も確認した。", "",
                 "| 世界 | 選び方 | 保持 | 水準 | 全試行の平均bits | 終了時の平均bits | 最大bits | 終了時の平均定義数 |", "|---|---|---|---|---:|---:|---:|---:|"]
        for row in totals:
            m = row["memory"]
            text.append(f"| {row['world']} | {row['selection']} | {row['retention']} | {row['level']} | {m['mean_total_bits']:.3f} | {m['mean_final_total_bits']:.3f} | {m['max_total_bits']} | {m['mean_final_definitions']:.3f} |")
        distributions = defaultdict(Counter)
        for (world, level, seed), counts in unique_public.items():
            distributions[(world, level)].update({int(k): v for k, v in counts.items()})
        text += ["", "公開実体数の分布（各世界・各水準で種1〜5の8,700場面。選び方・保持による同じ場面の重複を数えない）。本番の種と場面IDで、別の種で作る診断用の2場面を区別した。完全場面の実体集合は全水準で同一。", "",
                 "| 世界 | 水準 | 2実体 | 3実体 | 4実体 | 合計 |", "|---|---|---:|---:|---:|---:|"]
        for (world, level), counts in sorted(distributions.items()):
            assert sum(counts.values()) == 8700
            text.append(f"| {world} | {level} | {counts[2]} | {counts[3]} | {counts[4]} | {sum(counts.values())} |")
        result.update(aggregates=totals, public_entity_distributions={f"w{w}_{l}": dict(c) for (w, l), c in distributions.items()})
        (dest / "run_index.json").write_text(json.dumps(index, ensure_ascii=False, indent=2) + "\n")
    elif status == "stopped":
        text += ["", "次の走行を起動せず停止した。", "", "```", progress["stopped_reason"], "```", "",
                 "停止した条件と段階：", "```json", json.dumps(progress["current"], ensure_ascii=False, indent=2), "```",
                 "", "詳細はローカルpreview/progress.jsonと、該当する走行または解析のrun.log・validation.json・候補のcheck.jsonに保存した。未完の分を完了と扱わない。"]
    else:
        text += ["", "残る走行・解析を一本ずつ自動で受付へ渡す。全160本の集計は未完了。終了・停止時に同じ報告へ追記してpushする。"]
    (dest / "summary.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    (dest / "tables.md").write_text("\n".join(text) + "\n")
    git(ROOT, "add", "control/shop_deco_2026-10-04/stage4")
    if git(ROOT, "diff", "--cached", "--name-only"):
        git(ROOT, "-c", "user.name=Codex", "-c", "user.email=codex@openai.com", "commit", "-m", f"飾りの下見の{status}と記録を保存")
    git(ROOT, "push", "origin", "codex/shop-deco-2026-10-04")
    source_commit = git(ROOT, "rev-parse", "HEAD")
    text += ["", f"[作業枝の集計記録]({BASE_URL}/blob/{source_commit}/control/shop_deco_2026-10-04/stage4/summary.json)。元の台帳・side・研究者用実体数と、候補・記憶の試行別記録はローカルの `{AREA / 'preview'}` に保存した。実時間の値は書き換えていない。成績の良し悪しは記述しない。"]
    report = AREA / "report"
    prepared = False
    for attempt in range(6):
        try:
            git(report, "fetch", "origin", "results-2026-09-27")
            if prepared:
                git(report, "-c", "user.name=Codex", "-c", "user.email=codex@openai.com", "rebase", "origin/results-2026-09-27")
            else:
                assert not git(report, "status", "--porcelain")
                git(report, "checkout", "--detach", "origin/results-2026-09-27")
                with (report / REPORT_NAME).open("a") as stream:
                    stream.write("\n".join(text) + "\n")
                git(report, "add", REPORT_NAME)
                git(report, "-c", "user.name=Codex", "-c", "user.email=codex@openai.com", "commit", "-m", f"飾りの段4の{status}を報告")
                prepared = True
            git(report, "push", "origin", "HEAD:refs/heads/results-2026-09-27")
            marker = {"status": status, "source_commit": source_commit, "report_commit": git(report, "rev-parse", "HEAD")}
            (AREA / "preview/report_done.json").write_text(json.dumps(marker, indent=2) + "\n")
            print(json.dumps(marker), flush=True)
            return
        except subprocess.CalledProcessError as error:
            if attempt == 5:
                raise
            print(f"報告の更新を重ねて再試行: {error.output[-400:]}", flush=True)
            time.sleep(5)


if __name__ == "__main__":
    main()

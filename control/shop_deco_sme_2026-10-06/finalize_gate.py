"""関門制御の終了を待ち、その記録だけを保存・報告・pushする。下見は起動しない。"""
from pathlib import Path
from datetime import datetime
import argparse
import json
import os
import shutil
import subprocess
import time
import traceback
from common import ROOT, AREA, digest

BASE = "10cd8bdd46416aff55d0015e9072fc2186deed83"
BRANCH = "codex/shop-deco-sme-2026-10-06"
NAME = "control/2026-10-06_飾り_SME版_Codex.md"
RESEARCH = "control/shop_deco_sme_2026-10-06"
REPORT = AREA / "report"


def git(root, *args):
    return subprocess.check_output(["git", "-c", "user.name=Codex", "-c", "user.email=codex@openai.com", *args],
        cwd=root, text=True).strip()


def alive(pid):
    try:os.kill(pid, 0);return True
    except ProcessLookupError:return False


def push_report():
    # 他の係の報告を捨てず、通常の早送りだけで公開する。
    for attempt in range(4):
        git(REPORT, "fetch", "origin", "refs/heads/results-2026-09-27:refs/remotes/origin/results-2026-09-27")
        git(REPORT, "rebase", "origin/results-2026-09-27")
        try:
            git(REPORT, "push", "origin", "HEAD:refs/heads/results-2026-09-27")
            return git(REPORT, "rev-parse", "HEAD")
        except subprocess.CalledProcessError:
            if attempt == 3:raise
            time.sleep(2)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot", required=True)
    parser.add_argument("--controller-pid", type=int, required=True)
    args = parser.parse_args()
    status_path = AREA / "gates/run_gate.json"
    outcome = {"status":"waiting", "snapshot_commit":args.snapshot, "controller_pid":args.controller_pid}
    output = AREA / "gates/finalization.json"
    output.write_text(json.dumps(outcome, ensure_ascii=False, indent=2) + "\n")
    try:
        while True:
            result = json.loads(status_path.read_text())
            if result["status"] in ("passed", "stopped"):break
            if not alive(args.controller_pid):
                result.update(status="stopped", passed=False,
                    stopped_reason="関門の制御過程が終了し、完了した比較の記録が揃っていない。下見は開始しない。")
                status_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
                break
            time.sleep(5)
        # 最後の比較より前に模型のファイルが変わっていないことを再確認する。
        actual = {str(p.relative_to(ROOT)):digest(p) for folder in ("abm", "tools")
            for p in sorted((ROOT / folder).rglob("*.py"))}
        assert actual == result["source_sha256"]["ported"]
        assert git(ROOT, "rev-parse", "HEAD") == BASE
        # 比較中のHEADを動かさずに公開した控えへ、比較終了後に枝を早送りする。
        git(ROOT, "update-ref", f"refs/heads/{BRANCH}", args.snapshot, BASE)
        proof_dir = ROOT / RESEARCH / "gates"
        shutil.copy2(status_path, proof_dir / "run_gate.json")
        (proof_dir / "published_snapshot.json").write_text(json.dumps({
            "snapshot_commit":args.snapshot, "gate_header_commit":BASE,
            "reason":"比較中はHEADを共通土台に固定し、模型の実ファイルのSHA-256も保存した。"},
            ensure_ascii=False, indent=2) + "\n")
        git(ROOT, "add", RESEARCH)
        git(ROOT, "commit", "-m", "飾りのSME移植の全走行の照合記録を保存")
        source_commit = git(ROOT, "rev-parse", "HEAD")
        git(ROOT, "push", "origin", f"HEAD:refs/heads/{BRANCH}")
        report_dir = REPORT / RESEARCH
        (report_dir / "gates").mkdir(parents=True, exist_ok=True)
        for relative in ("preregistration.json", "approval.json", "gates/world_gate.json", "gates/run_gate.json", "gates/published_snapshot.json"):
            shutil.copy2(ROOT / RESEARCH / relative, report_dir / relative)
        report = REPORT / NAME
        text = report.read_text()
        marker = "\n## 全走行の関門の終了記録\n"
        text += marker + "\n" + f"記録時刻：{datetime.now().astimezone().isoformat()}。状態：`{result['status']}`。移植の控えは`{args.snapshot}`、関門の記録を足した作業枝のコミットは`{source_commit}`。\n\n"
        text += "| 世界 | 試行数 | 台帳本体・side等 | 比較ファイル数 |\n|---|---:|---|---:|\n"
        for pair in result["pairs"]:
            cmp = pair["comparison"]
            text += f"| {pair['world']} | {pair['trials']:,} | {'一致' if cmp['passed'] else '不一致'} | {cmp['compared_files']} |\n"
        text += "\n保持A、種1の比較。見出しを含み、承認済みの実測時間の数値以外は除外しない。\n\n"
        text += "| 世界 | 試行数 | checkout | 受付を含む秒 | 過程の最大常駐合計MB | 出力MB |\n|---|---:|---|---:|---:|---:|\n"
        for pair in result["pairs"]:
            for kind, r in pair["runs"].items():
                text += f"| {pair['world']} | {pair['trials']:,} | {kind} | {r['queue_and_run_sec']:.2f} | {r['peak_descendants_rss_bytes']/1e6:.2f} | {r['logical_output_bytes']/1e6:.2f} |\n"
        text += "\n受付の見込みは各模型1.0GB、各比較0.2GB。元の台帳・side・実時間・受付ログ・資源記録はローカルの`codex_shop_deco_sme_2026-10-06/gates/`へ保存した。全照合のハッシュと模型の実ファイルのハッシュはこの枝の`control/shop_deco_sme_2026-10-06/gates/run_gate.json`にも保存した。\n"
        if not result["passed"]:
            text += "\n停止の理由（計算や結果を補正していない）：\n\n```text\n" + result.get("stopped_reason", "未完了") + "\n```\n"
        text += "\n模型8本は完了していたが、最後の比較がCPU枠待ちのまま外側の制御過程が終了していた。制御終了そのものの理由は記録から特定できない。完了した模型の指紋が開始時と同じことを確認し、模型を再走行せず四つの比較だけを再受付した。待機した過程・監督用の親過程を計算中と誤って数えないようCPU監視を修正した。受付表のRAM・スワップ・熱・ディスクの条件は変更していない。\n"
        text += "\n2026-10-06に利用者から支持の割合の旗の追加を承認された。旗なしは現在のN3。支持数とF/H数は旧版と同じ定義にする。旗の関門は世界1・2、種1、200試行と全1,740試行で全バイト比較し、旗ありの手計算二例を残す。N3の80本は旗の関門より先に開始してよい。支持の割合の80本は旗の関門通過後に開始する。\n"
        text += "\nこの追記時点の下見は0／160本。N3の先行80本の準備を進めている。旧版の出力を変更していない。P-05cとD-04vを変更していない。承認は`control/shop_deco_sme_2026-10-06/approval.json`へ別に保存した。\n"
        report.write_text(text)
        git(REPORT, "add", NAME, RESEARCH)
        git(REPORT, "commit", "-m", "飾りのSME移植と関門の終了を報告")
        report_commit = push_report()
        outcome.update(status="reported", gate_status=result["status"], source_commit=source_commit,
            report_commit=report_commit, preview_started=0, next="N3先行80本、支持の割合の旗の関門")
        output.write_text(json.dumps(outcome, ensure_ascii=False, indent=2) + "\n")
        print(json.dumps(outcome, ensure_ascii=False), flush=True)
    except BaseException:
        outcome.update(status="stopped", error=traceback.format_exc())
        output.write_text(json.dumps(outcome, ensure_ascii=False, indent=2) + "\n")
        raise


if __name__ == "__main__":main()

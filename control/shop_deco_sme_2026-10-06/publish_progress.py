"""比較中のHEADを保ちながら実装の控えと、途中の報告を公開する。"""
from pathlib import Path
from datetime import datetime
import json
import shutil
from common import AREA, ROOT
from finalize_gate import BASE, BRANCH, NAME, RESEARCH, REPORT, git, push_report


assert git(ROOT, "rev-parse", "HEAD") == BASE
git(ROOT, "add", "tools/shopworld.py", "tools/v3_run.py", "tools/shop/test_deco.py", RESEARCH)
tree = git(ROOT, "write-tree")
changed = git(ROOT, "diff", "--name-only", BASE, tree).splitlines()
assert all(name in ("tools/shopworld.py", "tools/v3_run.py", "tools/shop/test_deco.py")
           or name.startswith(RESEARCH + "/") for name in changed)
snapshot = git(ROOT, "commit-tree", tree, "-p", BASE, "-m", "つなぎの飾りを指定のSME土台へ移植")
git(ROOT, "push", "origin", f"{snapshot}:refs/heads/{BRANCH}")
assert git(ROOT, "rev-parse", "HEAD") == BASE
receipt = {"snapshot_commit":snapshot, "local_comparison_HEAD":BASE,
    "published_at":datetime.now().astimezone().isoformat(), "comparison_still_running":True}
(AREA / "gates/published_snapshot.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n")
target = REPORT / RESEARCH
(target / "gates").mkdir(parents=True, exist_ok=True)
for relative in ("preregistration.json", "gates/world_gate.json"):
    shutil.copy2(ROOT / RESEARCH / relative, target / relative)
shutil.copy2(AREA / "gates/run_gate.json", target / "gates/run_gate_progress.json")
shutil.copy2(AREA / "gates/published_snapshot.json", target / "gates/published_snapshot_progress.json")
report = REPORT / NAME
text = report.read_text()
text += "\n## 途中の公開と、終了時の報告\n\n"
text += f"{receipt['published_at']}：実装の控え`{snapshot}`を作業枝へpushした。比較用checkoutのHEADは土台10cd8bdに保ち、模型の実ファイルのハッシュで差を記録した。控えの公開によって実行中の模型のファイルは変えていない。\n\n"
text += "200試行の世界1・2はともに通過した（各13ファイル）。全1,740試行の比較は受付で継続中。終了時は`finalize_gate.py`が結果と資源記録をこの報告へ追記し、通常の早送りで作業枝とresults枝をpushする。関門が不通なら下見を起動しない。通過しても支持の割合の判断が未確定なら下見を起動しない。\n"
report.write_text(text)
git(REPORT, "add", NAME, RESEARCH)
git(REPORT, "commit", "-m", "飾りのSME移植の途中と必要な判断を報告")
receipt["report_commit"] = push_report()
(AREA / "gates/published_snapshot.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n")
print(json.dumps(receipt, ensure_ascii=False), flush=True)

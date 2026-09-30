"""答えごとの記録を腕ごとに一つにまとめて上げる（2026-09-30 朝の委任書の 2）。★ まとめるだけ。数えない・判断しない。
side/<セル>/seed<種>.answers.csv（tools/answerlog.py）を種の順につなぎ、<結果>/<機械>/<腕>/answers_<腕>.csv.gz に書く。flag.json の写しも置く。
使い方  python3.12 tools/answerlog_gather.py <腕の走行根> <腕名> <結果の作業場所> <機械> [--no-push]"""
import glob
import gzip
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
a = [x for x in sys.argv[1:] if not x.startswith("--")]
root, arm, results, host = Path(a[0]), a[1], Path(a[2]), a[3]
files = sorted(glob.glob(str(root / "side/*/seed*.answers.csv")))
done = [f for f in files if os.path.exists(str(Path(f).parent.parent.parent / "ledgers/cells" / Path(f).parent.name / (Path(f).name.split(".")[0] + ".done")))]
dest = results / host / arm
dest.mkdir(parents=True, exist_ok=True)
n = 0
with gzip.open(dest / f"answers_{arm}.csv.gz", "wt", encoding="utf-8", newline="") as out:
    for i, f in enumerate(done):
        with open(f, encoding="utf-8", newline="") as fi:
            head = fi.readline()
            if i == 0:
                out.write(head)
            for line in fi:
                out.write(line)
                n += 1
shutil.copy(root / "flag.json", dest / "flag.json")
(dest / "README.md").write_text(f"# {arm}：答えごとの記録（{host}）\n\n- answers_{arm}.csv.gz：実際に答えた試行ごとに一行（列の意味は tools/answerlog.py の頭）。走行 {len(done)} 本、{n:,} 行。\n"
                                f"- 旗と版：flag.json。台帳は {host} の走行根に全部残してある（{root}）。\n", encoding="utf-8")
print(json.dumps({"arm": arm, "runs": len(done), "rows": n, "missing_done": len(files) - len(done)}, ensure_ascii=False))
if "--no-push" not in sys.argv:
    subprocess.run([sys.executable, str(REPO / "tools/results_push.py"), str(results), host, arm, f"結果：{host} の {arm}（答えごとの記録、tools/answerlog_gather.py）"], check=True)

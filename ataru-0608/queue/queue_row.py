"""走行の列（control/走行の列_2026-10-08.md）の行を読む・取る・済みにする（2026-10-07、受け箱の指示 1 (2) の準備）。
使い方：
  queue_row.py list                       列の行（#・中身・機械・版・旗・出力先・状態）を出す
  queue_row.py takeable                   デスクトップが取れる行（版・旗・出力先が埋まり、状態が「未着手」、機械が デスクトップ／デスクトップ優先／どちらでも）
  queue_row.py claim <#>                  pull → まだ「未着手」なら「走行中（デスクトップ・時刻）」にして push（衝突したら pull して確かめ直す）
  queue_row.py done <#> <出力先>          「済み（時刻、出力先）」にして push
  queue_row.py stop <#> <理由> <報告>     「止まり（時刻、理由、報告）」にして push
列の行は表の一行（| # | 中身 | 世界 | 種 | 本数 | 機械 | 版・旗・出力先 | 状態 |）。"""
import datetime
import subprocess
import sys

RES = "/home/tatsu/v33prod/results"
LIST = "control/走行の列_2026-10-08.md"
OK_MACHINE = ("デスクトップ", "デスクトップ優先", "どちらでも")
TRAILER = "\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"


def git(*a, check=True):
    return subprocess.run(["git", "-C", RES, *a], capture_output=True, text=True, check=check)


def rows(text):
    out = []
    for i, line in enumerate(text.split("\n")):
        c = [x.strip() for x in line.strip().strip("|").split("|")]
        if line.startswith("|") and len(c) == 8 and c[0] not in ("#", "---:") and not set(c[0]) <= set("-:"):
            out.append(dict(line=i, num=c[0], what=c[1], world=c[2], seeds=c[3], n=c[4], machine=c[5], spec=c[6], state=c[7]))
    return out


def read():
    git("pull", "-q", "--rebase", "origin", "results-2026-09-27")
    return open(f"{RES}/{LIST}", encoding="utf-8").read()


def takeable(rs):
    return [r for r in rs if r["state"] == "未着手" and r["spec"] and not r["spec"].startswith("（") and r["machine"] in OK_MACHINE]


def set_state(num, new, expect=None, msg=""):
    for attempt in range(5):
        text = read()
        rs = [r for r in rows(text) if r["num"] == num]
        if len(rs) != 1:
            sys.exit(f"★ 行 #{num} が一つに決まらない（{len(rs)} 行）")
        r = rs[0]
        if expect and r["state"] != expect:
            sys.exit(f"★ 行 #{num} の状態が「{r['state']}」（「{expect}」でない）。取らない")
        lines = text.split("\n")
        cells = lines[r["line"]].split("|")
        cells[-2] = f" {new} "
        lines[r["line"]] = "|".join(cells)
        open(f"{RES}/{LIST}", "w", encoding="utf-8").write("\n".join(lines))
        git("add", LIST)
        git("commit", "-q", "-m", f"走行の列 #{num}：{new}（デスクトップの走行の係）{msg}{TRAILER}")
        if git("push", "-q", "origin", "HEAD:results-2026-09-27", check=False).returncode == 0:
            print(f"#{num}：{r['state']} → {new}")
            return r
        git("reset", "-q", "--hard", "origin/results-2026-09-27", check=False)  # 自分の未 push の一つだけを戻して取り直す
    sys.exit("★ push が 5 回衝突した。取らない")


if __name__ == "__main__":
    now = datetime.datetime.now().strftime("%m/%d %H:%M")
    cmd = sys.argv[1]
    if cmd in ("list", "takeable"):
        rs = rows(read())
        for r in (rs if cmd == "list" else takeable(rs)):
            print(f"#{r['num']}\t{r['machine']}\t{r['state']}\t{r['spec'][:80]}\t{r['what'][:40]}")
    elif cmd == "claim":
        set_state(sys.argv[2], f"走行中（デスクトップ・{now}）", expect="未着手")
    elif cmd == "done":
        set_state(sys.argv[2], f"済み（{now}、{sys.argv[3]}）")
    elif cmd == "stop":
        set_state(sys.argv[2], f"止まり（{now}、{sys.argv[3]}、{sys.argv[4]}）")

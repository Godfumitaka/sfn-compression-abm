"""古い走行の整理（2026-10-01 夕方の返事の 2）：WSL の中の走行の置き場所ごとの一覧。読むだけ（何も消さない・動かさない）。
走行の置き場所＝manifest.jsonl 又は ledgers/ を持つディレクトリ。置き場所（~ の直下の名前）ごとにまとめ、その中の腕ごとに一行。
列：大きさ・台帳の本数・種の範囲・コード（manifest の code_commit、無ければ台帳の見出し）・設定の名前・主な旗（flag.json）・最後に書いた日時・
    results の枝に README／sha256 の一覧があるか（ataru-0608/ の下で同じ腕の名前のディレクトリ）・今の作業が読んでいるか（下の READERS の文字列に置き場所の道が出るか）。
使い方：inventory.py <出力 .md> <results の枝の ls-tree の一覧> <今の作業の台本・道具の一覧（読む道を探すファイル）…>"""
import glob
import gzip
import json
import os
import subprocess
import sys
import time
from collections import defaultdict

HOME = os.path.expanduser("~")
OUT, LSTREE = sys.argv[1], sys.argv[2]
READERS = sys.argv[3:]


def du(p):
    try:
        return int(subprocess.run(["du", "-sb", p], capture_output=True, text=True).stdout.split()[0])
    except Exception:
        return 0


def human(n):
    for u in ("B", "K", "M", "G"):
        if n < 1024 or u == "G":
            return f"{n:.0f}{u}" if u in ("B", "K") else f"{n:.1f}{u}"
        n /= 1024


REPO = os.path.join(HOME, "sfn/sfn-compression-abm")
STRICTPC0 = "0a64791"   # --strict-pc を足した最初のコミット（これを祖先に持つコードを「今の版（strict-pc 以降）」とする）
_anc = {}


def is_current(c):
    if not c:
        return False
    if c not in _anc:
        r = subprocess.run(["git", "-C", REPO, "merge-base", "--is-ancestor", STRICTPC0, c], capture_output=True)
        _anc[c] = r.returncode == 0
    return _anc[c]


res_paths = [l.strip() for l in open(LSTREE, encoding="utf-8")]
res_dirs = defaultdict(set)
for p in res_paths:
    parts = p.split("/")
    for i in range(1, len(parts)):
        res_dirs[parts[i - 1]].add("/".join(parts[:i]))
reader_text = ""
for f in READERS:
    try:
        reader_text += open(f, encoding="utf-8", errors="ignore").read() + "\n"
    except Exception:
        pass

arms = set()
REPOS = []
for root, dirs, files in os.walk(HOME):
    if "/." in root or "/node_modules" in root:
        dirs[:] = []
        continue
    if ".git" in files or ".git" in dirs:      # リポジトリの複製（消さないもの）。中には入らない
        REPOS.append(root)
        dirs[:] = []
        continue
    if "manifest.jsonl" in files or "ledgers" in dirs:
        arms.add(root)
        dirs[:] = [d for d in dirs if d not in ("ledgers", "side")]
    if root.count("/") - HOME.count("/") >= 5:
        dirs[:] = []

by_top = defaultdict(list)
KEEPSZ = {True: 0, False: 0}
for a in sorted(arms):
    rel = os.path.relpath(a, HOME)
    top = rel.split("/")[0] if not rel.startswith("sfn/") else "/".join(rel.split("/")[:2])
    by_top[top].append(a)

lines = ["# WSL の中の走行の置き場所の一覧（読むだけ。何も消していない）\n",
         f"作った日時：{time.strftime('%Y-%m-%d %H:%M')}。大きさは du -sb。\n"]
summary = []
for top, al in sorted(by_top.items()):
    tsize = du(os.path.join(HOME, top)) - sum(du(r) for r in REPOS if r.startswith(os.path.join(HOME, top) + "/"))
    summary.append((top, tsize, len(al)))
    lines.append(f"\n## ~/{top}（{human(tsize)}、腕 {len(al)}）\n")
    lines.append("| 腕 | 大きさ | 台帳 | 種 | コード | 設定 | 主な旗 | 最後に書いた | results の枝 | 今の作業が読む | 消さないもの |")
    lines.append("|---|---:|---:|---|---|---|---|---|---|---|---|")
    for a in al:
        rel = os.path.relpath(a, HOME)
        name = os.path.basename(a)
        led = sorted(glob.glob(os.path.join(a, "ledgers/**/seed*.jsonl.gz"), recursive=True))
        seeds = sorted({int(os.path.basename(p)[4:7]) for p in led})
        codes, cfgs = set(), set()
        mf = os.path.join(a, "manifest.jsonl")
        if os.path.exists(mf):
            for l in open(mf, encoding="utf-8"):
                try:
                    r = json.loads(l)
                except Exception:
                    continue
                if r.get("code_commit"):
                    codes.add(r["code_commit"][:7])
        if not codes and led:
            try:
                with gzip.open(led[0], "rt", encoding="utf-8") as f:
                    h = json.loads(f.readline())
                codes.add(str(h.get("code_commit", ""))[:7])
            except Exception:
                pass
        flags = ""
        fj = os.path.join(a, "flag.json")
        if os.path.exists(fj):
            try:
                fl = json.load(open(fj, encoding="utf-8"))
                cfgs.add(os.path.basename(str(fl.get("config", ""))))
                keys = [k for k in ("v39_price", "use_forget", "shop_world", "world_cue", "strict_pc", "answer_gap", "cf_learn", "e_price") if fl.get(k) not in (None, False)]
                flags = " ".join(f"{k}={fl[k]}" if fl[k] is not True else k for k in keys)
            except Exception:
                pass
        mt = time.strftime("%m-%d %H:%M", time.localtime(max((os.path.getmtime(p) for p in led), default=os.path.getmtime(a))))
        rr = sorted(d for d in res_dirs.get(name, ()) if d.startswith(("ataru-0608", "mac")))
        reads = "読む" if (rel in reader_text or a in reader_text) else ""
        s_r = f"{seeds[0]}〜{seeds[-1]}（{len(seeds)}）" if seeds else ""
        keep = []
        if any(is_current(c) for c in codes):
            keep.append("今の版")
        if any(21 <= x <= 40 for x in seeds):
            keep.append("種 21〜40")
        if "cal" in name.lower() or (seeds and all(41 <= x <= 60 for x in seeds)):
            keep.append("較正")
        KEEPSZ[bool(keep)] += du(a)
        lines.append(f"| {rel} | {human(du(a))} | {len(led)} | {s_r} | {' '.join(sorted(codes))} | {' '.join(sorted(cfgs))} | {flags} | {mt} | {'<br>'.join(rr)} | {reads} | {'・'.join(keep)} |")
lines.insert(2, "\n| 置き場所 | 大きさ | 腕 |\n|---|---:|---:|\n" + "\n".join(f"| ~/{t} | {human(s)} | {n} |" for t, s, n in sorted(summary, key=lambda x: -x[1])) + "\n")
lines.insert(3, f"\n腕の大きさの和：消さないもの（今の版・種 21〜40・較正）{human(KEEPSZ[True])}、それ以外 {human(KEEPSZ[False])}。"
                 f"置き場所の大きさはリポジトリの複製を除く。「今の版」＝コードが {STRICTPC0}（--strict-pc を足した最初のコミット）を祖先に持つ。\n")
lines.append("\n## リポジトリの複製（走行の置き場所ではない。消さないもの）\n")
lines += [f"- ~/{os.path.relpath(r, HOME)}（{human(du(r))}）" for r in sorted(REPOS)]
open(OUT, "w", encoding="utf-8").write("\n".join(lines) + "\n")
print(OUT, len(arms))

"""第 2 波（#8・#10〜#13・#15〜#18）の、表に使う写しの一覧と、surface の形（<root>/<arm>/seedNNN/）の見え方（シンボリックリンク）を作る
（受け箱の指示 68 の 1・84 の 3）。wave1_view.py の写し。wave1_view.py・wave1_view/ には触れない。
写しの選び方（走行の列 2026-10-08 の第 2 波の欄、指示 55・57）：
  - #8・#15・#16（全部入り、第二段を使う行）：旗ありの写し c7921598（名前の末尾 _c792）だけ。
    #8 の世界 1・種 1 と #15 の世界 2・種 1 にある旗なし（c57467ea、末尾 _c574）の写しは使わない（第 1 波の第二段を使う行と同じ決まり）。
  - #10〜#13・#17・#18（D・D＋注意）：daf69efd（末尾 _cdaf）。
  - 名前は wave2_<行>_w<世界>_s<種>_<末尾>（~/cloud/wave1/wave2_s55_commands.json・wave2d_commands.json の name）。
  - 持ち帰り済み（D: に output/ledgers/cells/*/seedNNN.done がある）本だけ。種 1〜20 を見る（第 2 波は種 1〜10 だけ走らせた）。種 21〜40 は扱わない。
見え方：~/surface/wave2_view/<行>/q<行>_w<世界>/seedNNN → /mnt/d/sfn_runs/cloud/<本>/output。
一覧：~/surface/wave2_view/selection.tsv（行・世界・種・使う本・版）。何度走らせてもよい（新しく持ち帰った本を足す）。"""
import glob, os
from pathlib import Path
D = Path("/mnt/d/sfn_runs/cloud"); V = Path.home() / "surface/wave2_view"; V.mkdir(exist_ok=True)
ROWS = {"8": ((1, 2), "_c792", "c7921598"), "10": ((1, 2), "_cdaf", "daf69efd"), "11": ((1, 2), "_cdaf", "daf69efd"),
        "12": ((1, 2), "_cdaf", "daf69efd"), "13": ((1, 2), "_cdaf", "daf69efd"), "15": ((2,), "_c792", "c7921598"),
        "16": ((2,), "_c792", "c7921598"), "17": ((2,), "_cdaf", "daf69efd"), "18": ((2,), "_cdaf", "daf69efd")}


def done(name, seed):
    return bool(glob.glob(str(D / name / "output/ledgers/cells/*" / f"seed{seed:03d}.done")))


rows = []
for r, (worlds, suf, ver) in ROWS.items():
    for w in worlds:
        for s in range(1, 21):
            name = f"wave2_{r}_w{w}_s{s}{suf}"
            pick = name if done(name, s) else None
            rows.append((r, w, s, pick or "", ver if pick else ""))
            link = V / r / f"q{r}_w{w}" / f"seed{s:03d}"
            if pick:
                link.parent.mkdir(parents=True, exist_ok=True)
                tgt = D / pick / "output"
                if link.is_symlink() and os.readlink(link) != str(tgt):
                    link.unlink()
                if not link.exists():
                    link.symlink_to(tgt)
with open(V / "selection.tsv", "w") as f:
    f.write("row\tworld\tseed\trun\tversion\n")
    for x in rows:
        f.write("\t".join(map(str, x)) + "\n")
have = sum(1 for x in rows if x[3]); print(f"写しが選べた本 {have}/{len(rows)}")

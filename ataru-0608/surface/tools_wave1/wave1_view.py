"""第 1 波（新しい版 #1a〜#7b）の、表に使う写しの一覧と、surface の形（<root>/<arm>/seedNNN/）の見え方（シンボリックリンク）を作る（受け箱の指示 44 の 1）。
写しの選び方（結果の前に固定、台帳 D-07γγ・指示 35・39・40・41・42）：
  - 1・3・4・6・7（第二段を使う行）：旗ありの写し。c7921598（名前の末尾 _c792）があればそれ、無ければ 4ceadf63 の完走した本（末尾なし）。
  - 2・5：旗なしの写し。種 1・2 は e9ed84a（末尾 _e9 があればそれ、無ければ末尾なし）、種 3〜20 は c57467ea（末尾 _c574）。
  - 持ち帰り済み（D: に output/ledgers/cells/*/seedNNN.done がある）本だけ。種 21〜40 は扱わない。
見え方：~/surface/wave1_view/<行>/<arm>/seedNNN → /mnt/d/sfn_runs/cloud/<本>/output（行は 1a・1b…7b、arm は q<行>_w<世界>）。
一覧：~/surface/wave1_view/selection.tsv（行・世界・種・使う本・版）。何度走らせてもよい（新しく持ち帰った本を足す）。"""
import glob, json, os
from pathlib import Path
D=Path("/mnt/d/sfn_runs/cloud"); V=Path.home()/"surface/wave1_view"; V.mkdir(exist_ok=True)
def done(name, seed):
    return bool(glob.glob(str(D/name/"output/ledgers/cells/*"/f"seed{seed:03d}.done")))
rows=[]
for r in "1234567":
    for w in (1,2):
        for s in range(1,21):
            half="a" if s<=10 else "b"; row=f"{r}{half}"
            base=f"wave1_{r}{'a' if s<=2 or s<=10 else 'b'}_w{w}_s{s}"
            # 種 1・2 の名前は wave1_<r>a_w_s（版の末尾つき／なし）、種 3〜10 は wave1_<r>a_…、種 11〜20 は wave1_<r>b_…
            if r in "2" or r in "5":
                cands=[base+"_e9", base] if s<=2 else [base+"_c574"]
            else:
                cands=[base+"_c792", base] if s<=2 else [base+"_c792"]
            pick=next((n for n in cands if done(n,s)), None)
            ver=None if pick is None else ("c7921598" if pick.endswith("_c792") else "c57467ea" if pick.endswith("_c574") else "e9ed84a" if pick.endswith("_e9") or r in "25" else "4ceadf63")
            rows.append((row,w,s,pick or "", ver or ""))
            link=V/row/f"q{row}_w{w}"/f"seed{s:03d}"
            if pick:
                link.parent.mkdir(parents=True,exist_ok=True)
                tgt=D/pick/"output"
                if link.is_symlink() and os.readlink(link)!=str(tgt): link.unlink()
                if not link.exists(): link.symlink_to(tgt)
with open(V/"selection.tsv","w") as f:
    f.write("row\tworld\tseed\trun\tversion\n")
    for x in rows: f.write("\t".join(map(str,x))+"\n")
have=sum(1 for x in rows if x[3]); print(f"写しが選べた本 {have}/{len(rows)}")

"""受け箱の指示 35 の 2・37 の 2・39 の 2：同じ行・世界・種の旗あり（4ceadf63 又は c7921598）と旗なし（e9ed84a 又は c57467ea）の写しが両方とも持ち帰られた組ごとに、
norm_hash（gz は解凍、台帳の見出しの行を除く、JSON の時間の欄を除く、flag.json・manifest・.done を除く）の表を比べる。表は ataru-0608/cloud_runs/<本>/norm_hash.tsv。
付帯の行（command・time.log など、norm_hash.tsv に入っていないもの）は比べない。"""
import csv, os, sys
R=os.path.expanduser("~/v33prod/results/ataru-0608/cloud_runs")
def table(name):
    p=f"{R}/{name}/norm_hash.tsv"
    if not os.path.exists(p): return None
    return {r[0]:r[-1] for r in csv.reader(open(p),delimiter="\t") if r and not r[0].startswith("#") and r[0]!="path"}
rows=[]
for row in ("1a","3a","4a","6a","7a"):
    for w in (1,2):
        for s in (1,2):
            base=f"wave1_{row}_w{w}_s{s}"
            flag=[n for n in (base, base+"_c792") if table(n)]; plain=[n for n in (base+"_e9", base+"_c574") if table(n)]
            for f in flag:
                for u in plain:
                    a,b=table(f),table(u); diff=sorted(k for k in set(a)|set(b) if a.get(k)!=b.get(k))
                    rows.append((f,u,len(a),len(b),len(diff),diff[:3]))
for r in rows: print("\t".join(map(str,r)))
print(f"組 {len(rows)}、一致 {sum(1 for r in rows if r[4]==0)}、違う {sum(1 for r in rows if r[4]>0)}")

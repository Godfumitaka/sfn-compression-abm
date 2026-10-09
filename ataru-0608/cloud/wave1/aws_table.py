"""指示 63 の 2：AWS の走っている本の全部の表（読むだけ、止めない）。~/cloud/wave1/aws_trials.tsv（30 分ごとの試行の記録）から、
最近の速さ（記録の最初と最後の差。間が 2 時間を越えるなら、最後の 2 時間の分）・残りの見込み（下限：最近の速さのままとして）・10/12（月）06:00 までに終わるかを出す。
機械ごとに、「月曜の朝までに終わらない本を全部止めたら、いつ消せるか」と、それで減る費用の見込みを出す。走っている本は止めない。"""
import csv, datetime, json, re, collections
W="/home/tatsu/cloud/wave1/"; P=json.load(open("/home/tatsu/cloud/prices_us_east_1.json"))
MACH={"i-0edf5697853141268":("m7a（m0）","m7a.8xlarge"),"i-06603dd646d82ca90":("m1","c7a.8xlarge"),"i-0fdf21ef22eb1a68b":("m2","c7a.8xlarge"),"i-087e6cee784e4f17b":("m3","c7a.8xlarge"),"i-07bd8ebba0b270717":("m4","c7a.8xlarge")}
DEAD=datetime.datetime(2026,10,12,6,0).timestamp()
rows=collections.defaultdict(list)
for r in csv.reader(open(W+"aws_trials.tsv"),delimiter="\t"):
    if len(r)==4 and r[3].isdigit(): rows[(r[0],r[2])].append((int(r[1]),int(r[3])))
now=max(t for v in rows.values() for t,_ in v)
def label(path):
    m=re.search(r"/wave1/(out\w*)/(\w+)/(\w+)/w(\d)_seed0*(\d+)/output",path)
    if not m: return path
    out,ver,row,w,s=m.groups()
    if out=="out55": return f"第 2 波 #{ver}・世界 {w}・種 {s}"
    return f"第 1 波 {row}・世界 {w}・種 {s}（{ver}）"
table=[]; per=collections.defaultdict(list)
for (mid,path),v in rows.items():
    v=sorted(v); last_t,last_tr=v[-1]
    if last_t<now-1200: continue          # 最後の記録に出ていない本は終わった
    base=[x for x in v if x[0]>=last_t-7200] or v; t0,tr0=base[0]
    rate=(last_tr-tr0)/((last_t-t0)/3600) if last_t>t0 and last_tr>tr0 else None
    rem=(1740-last_tr)/rate if rate else None
    fin=last_t+rem*3600 if rem is not None else None
    ok=None if fin is None else fin<=DEAD
    table.append((MACH.get(mid,(mid,))[0],label(path),last_tr,rate,rem,ok)); per[mid].append((fin,ok))
print("| 機械 | 本 | 今の試行 | 最近の速さ（試行／時） | 残りの見込み（下限、時間） | 月 06:00 までに |\n|---|---|---:|---:|---:|---|")
for t in sorted(table,key=lambda x:(x[0],-(x[4] or 1e9))):
    print(f"| {t[0]} | {t[1]} | {t[2]} | {'—' if t[3] is None else f'{t[3]:.1f}'} | {'速さを測れない' if t[4] is None else f'{t[4]:.1f}'} | {'—' if t[5] is None else ('終わる' if t[5] else '終わらない')} |")
print("\n| 機械 | 種類 | 走っている本 | 月曜の朝までに終わらない本 | 全部を待ったときに消せる時刻（下限） | 終わらない本を止めたら消せる時刻 | 減る費用の見込み |\n|---|---|---:|---:|---|---|---:|")
for mid,v in per.items():
    name,typ=MACH.get(mid,(mid,"?")); pr=P.get(typ,0)
    fins=[f for f,_ in v if f]; okf=[f for f,o in v if o]
    allend=max(fins) if fins else None; keep=max(okf) if okf else now
    late=sum(1 for _,o in v if o is False)
    fmt=lambda x: datetime.datetime.fromtimestamp(x).strftime("%m/%d %H:%M") if x else "—"
    save=(allend-keep)/3600*pr if allend else 0
    print(f"| {name} | {typ} | {len(v)} | {late} | {fmt(allend)} | {fmt(keep)} | 約 ${save:.0f} |")

"""二つの 200 試行の出力を全ファイルで比べる。除くのは台帳の見出し一行と、実測の sec_trial（cflearn などの jsonl の行の鍵）だけ。
flag.json・manifest.jsonl・.done は走行の付帯の記録（版の番号・時間・旗の一覧）なので、別に違う欄を書く。"""
import gzip, json, os, sys, hashlib
A, B = sys.argv[1], sys.argv[2]
def files(r): return sorted(os.path.relpath(os.path.join(dp,f), r) for dp,_,fs in os.walk(r) for f in fs)
fa, fb = files(A), files(B)
print("ファイルの一覧が同じ", fa == fb, sorted(set(fa) ^ set(fb)))
def raw(p): return (gzip.open(p,"rb") if p.endswith(".gz") else open(p,"rb")).read()
def strip_sec(b):
    out=[]
    for l in b.splitlines():
        try:
            o=json.loads(l)
            if isinstance(o,dict) and "sec_trial" in o: o.pop("sec_trial"); l=json.dumps(o,sort_keys=True).encode()
        except Exception: pass
        out.append(l)
    return b"\n".join(out)
bad=[]
for f in fa:
    if f not in fb: continue
    pa, pb = os.path.join(A,f), os.path.join(B,f)
    if f in ("flag.json","manifest.jsonl") or f.endswith(".done"):
        a=json.loads(open(pa).readline()) if f!="flag.json" else json.load(open(pa)); b=json.loads(open(pb).readline()) if f!="flag.json" else json.load(open(pb))
        print("付帯", f, "違う欄", sorted(k for k in set(a)|set(b) if a.get(k)!=b.get(k)))
        continue
    da, db = raw(pa), raw(pb)
    if "/ledgers/" in "/"+f and f.endswith(".jsonl.gz"):
        da, db = da.split(b"\n",1)[1], db.split(b"\n",1)[1]
    same = da == db or strip_sec(da) == strip_sec(db)
    if f.endswith(".gz") and same: same_raw = open(pa,"rb").read()==open(pb,"rb").read()
    else: same_raw = None
    print("同じ" if same else "★違う", f, "" if same_raw is None else ("（圧縮のままも同じ）" if same_raw else "（展開すると同じ）"))
    if not same: bad.append(f)
print("結果：", "全部一致" if not bad else f"違う {bad}")

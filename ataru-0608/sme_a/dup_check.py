"""読み取り用の写し（*_view）の展開したファイルが、元の走行の .gz を展開した中身と同じかを sha256 で確かめる（読むだけ）。"""
import hashlib, gzip, os, sys, json
H=os.path.expanduser("~")
MAP={"n3sel_view":lambda a:(f"{H}/n3prod/{a}" if a.startswith("n3_") else f"{H}/n3lgrid/{a}"),
     "lgrid_view":lambda a:f"{H}/lgrid/{a}", "chance_view":lambda a:f"{H}/chance/{a}", "dsel_view":lambda a:f"{H}/ufprod/full/{a}"}
def sha(path, gz=False):
    h=hashlib.sha256()
    with (gzip.open(path,"rb") if gz else open(path,"rb")) as f:
        for b in iter(lambda: f.read(1<<20), b""): h.update(b)
    return h.hexdigest()
res={}
for v, f in MAP.items():
    tot=same=diff=nogz=0; bytes_same=0; links=0
    for arm in sorted(os.listdir(f"{H}/{v}")):
        orig=f(arm)
        for dp,ds,fs in os.walk(f"{H}/{v}/{arm}"):
            if os.path.islink(dp): continue
            for fn in fs:
                p=os.path.join(dp,fn)
                if os.path.islink(p): links+=1; continue
                rel=os.path.relpath(p,f"{H}/{v}/{arm}")
                o=os.path.join(orig,rel)
                tot+=1
                if os.path.exists(o+".gz"): ok = sha(p)==sha(o+".gz",True)
                elif os.path.exists(o): ok = sha(p)==sha(o)
                else: nogz+=1; continue
                if ok: same+=1; bytes_same+=os.path.getsize(p)
                else: diff+=1
    res[v]=dict(files=tot,same=same,diff=diff,no_original=nogz,symlinks=links,bytes_same_GB=round(bytes_same/1e9,2))
    print(v, res[v], flush=True)
json.dump(res,open(f"{H}/dup_check.json","w"),ensure_ascii=False,indent=1)

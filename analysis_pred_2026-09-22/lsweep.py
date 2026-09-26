"""§2（追補）  定義ごとの m_live の系列から 通過群(L)（L=2〜6）の所属を出す。
★★ newlabel_R.py と原本は変えない。判定の式は newlabel_R.py:41-64 を そのまま写す。
★ m_live は constituent_states の alive な項目を **数える**（newlabel_R.py:50 と同じ）。
   → 鍵 (R,slot,registered_at) の衝突の影響を受けない。
★ 系列 end[R] は、その試行の constituent_states に R が現れた場合のみ足す（readings.py:47-55 と同じ）。
★ 固定する条件  max_end >= 8 ／ drops >= 1（案イ、θ=8）／ 単調なし（M1）／ N >= 50。
★ 検算  L=2 の所属が newlabelR_<腕>.json の 新θ8 と一致すること（呼び出し側で照合）。
★ 原本（abm/・runs/）には触れない。読むだけ。
使い方  python3.12 lsweep.py <腕名> <走行根> [workers]"""
import gzip,json,sys,pathlib,collections,time,hashlib,concurrent.futures,glob,os
ARM=sys.argv[1]; ROOT=sys.argv[2]; W=int(sys.argv[3]) if len(sys.argv)>3 else 3
OUT=pathlib.Path(f"/Users/tatsu-admin/sfn/sfn-compression-abm/analysis_pred_2026-09-22/lsweep_{ARM}.json")
if OUT.exists(): sys.exit(f"既存 {OUT} あり。上書きしない")
THETA=8; N_MIN=50; LOWS=(2,3,4,5,6)
def drops_i(ts,theta):
    idx=[i for i,v in enumerate(ts) if v>=theta]
    if not idx: return None
    last=max(idx)
    return sum(1 for i in range(last+1,len(ts)) if ts[i]<ts[i-1])
def stay_len(ts,low):
    idx=[i for i,v in enumerate(ts) if v<=low and v>=1]
    if not idx: return None
    last=len(ts)-1
    if not (1<=ts[last]<=low): return None
    i=last
    while i>0 and 1<=ts[i-1]<=low: i-=1
    return last-i+1,i
def one(p):
    cell=os.path.basename(os.path.dirname(p)); seed=os.path.basename(p).replace(".jsonl.gz","")
    end=collections.defaultdict(list)
    with gzip.open(p,"rt",encoding="utf-8") as f:
        next(f)
        for l in f:
            r=json.loads(l)
            if r.get("record_type")!="trial": continue
            live=collections.Counter(); present=set()
            for st in (r.get("constituent_states") or ()):
                R=st["R"]; present.add(R)
                if st.get("alive"): live[R]+=1
            for R in present: end[R].append(live[R])
    out={}
    for R,ts in end.items():
        if not ts: continue
        mx=max(ts)
        rec={"mx":mx,"final":ts[-1],"n":len(ts)}
        if mx>=THETA:
            di=drops_i(ts,THETA)
            rec["drops"]=di
            if di is not None and di>=1:
                ok=[]
                for low in LOWS:
                    sl=stay_len(ts,low)
                    if sl is None: continue
                    Ln,i0=sl
                    if Ln>=N_MIN: ok.append(low)
                rec["pass"]=ok
        out[R]=rec
    return dict(cell=cell,seed=seed,定義=out)
def main():
    fs=sorted(glob.glob(f"{ROOT}/cells/*/seed*.jsonl.gz")); assert fs,ROOT
    print(f"  腕 {ARM}  台帳 {len(fs)} 本  workers {W}",flush=True)
    t0=time.time(); res=[]
    with concurrent.futures.ProcessPoolExecutor(max_workers=W) as ex:
        for i,d in enumerate(ex.map(one,fs),1):
            res.append(d)
            if i%20==0: print(f"   {i}/{len(fs)} 経過{time.time()-t0:.0f}秒",flush=True)
    json.dump({"__版":dict(script="lsweep.py",md5=hashlib.md5(pathlib.Path(__file__).read_bytes()).hexdigest(),
        起動=time.strftime("%Y-%m-%d %H:%M:%S",time.localtime(t0)),腕=ARM,走行根=ROOT,
        条件=f"max_end>={THETA} ／ drops>=1（案イ θ={THETA}）／ 単調なし ／ N>={N_MIN} ／ L in {LOWS}"),
        "台帳":res},open(OUT,"w"),ensure_ascii=False)
    print(f"  完了 {time.time()-t0:.0f}秒 -> {OUT}",flush=True)
if __name__=="__main__": main()

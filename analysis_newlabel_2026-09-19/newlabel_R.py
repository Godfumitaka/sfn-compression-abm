#!/usr/bin/env python3
"""★★ newlabel.py の複製 ＋ R 別の所属（2026-09-20 04:45）。★ 原本は触っていない。\n★ 判定（drops_i / drops_ni / mono_* / stay_len / classify）は 一行も変えていない。\n中心的過程の新ラベル。★ 走行不要・台帳直読み・原本は変更しない。
★ 現行の厳  max_end >= 6 ∧ final ∈ {1,2} ∧ drops >= 2（readings.py:89-98）
   ★★ drops は「最後に 6 以上だった時点より後の 減少の回数」＝ 最終降下が何段階か。
      ★ last_ge6 の 6 が 2 行に埋め込まれているので 閾値を下げると max() が空列で落ちる。
★★ 新ラベル  max_end >= θ ∧ 単調 ∧ 低 L で停留 ∧ drops >= 1
   ★ 単調は 三案を並べる（2026-09-19 の指示）
     M1 単調なし     ★ 条件に入れない
     M2 入口のみ     ★ 停留に入る直前の一歩が降下（★ 復活で停留に入った定義だけ弾く）
     M3 全区間       ★ 頂点以降 一度も増えない（★ 従来の実装。厳しすぎる）
   ★ 旧走行は復活があるので単調が効く。★★ 新走行は L=0 が死ぬので復活が無く、M1 が本命になりうる
   単調降下  ★ 頂点（最大値）以降 一度も L が増えていない
   停留      ★ 低 L（既定 <=2、<=3 も併記）に最後に入ってから 走行末までの試行数 >= N
   drops     ★ 案イ  last_ge(θ) より後の減少回数（★ θ=6 で現行と一致）
             ★ 案ニ  最大値以降の減少回数（★ θ から独立）
★★ 停留の二種類を分ける（★ 四階では 46.8% の定義が 一度も τ を通らない）
   使われながら動かない  ★ 停留期間に採択がある  → ★ 神話らしい
   使われずに動かない    ★ 採択が無い            → ★ ただの残骸
★ 採択 ＝ 台帳 R_used 非 null（★ τ を通った試行。loop.py:512）
使い方  python3.12 newlabel.py <腕名> <走行根> [workers]"""
import collections,concurrent.futures,glob,gzip,json,pathlib,sys,time
ROOT=pathlib.Path("/Users/tatsu-admin/sfn/sfn-compression-abm")
sys.path.insert(0,str(ROOT/"analysis_runA_2026-09-10"))
from readings import scan_ledger,classify
NAME,RD=sys.argv[1],sys.argv[2];W=int(sys.argv[3]) if len(sys.argv)>3 else 3
THETAS=(4,5,6,7,8,10,12)
STAYS=(25,50,100)
def drops_i(ts,theta):
    """★ 案イ  θ を最後に満たした時点より後の 減少回数。★ θ=6 で現行の drops と一致。"""
    idx=[i for i,v in enumerate(ts) if v>=theta]
    if not idx: return None
    last=max(idx)
    return sum(1 for i in range(last+1,len(ts)) if ts[i]<ts[i-1])
def drops_ni(ts):
    """★ 案ニ  最大値以降の 減少回数。★ θ から独立。"""
    if not ts: return None
    mx=max(ts);last=max(i for i,v in enumerate(ts) if v==mx)
    return sum(1 for i in range(last+1,len(ts)) if ts[i]<ts[i-1])
def mono_all(ts):
    """★ 案(3) 全区間単調  頂点（最大値の最後の位置）以降 一度も増えていない。"""
    if not ts: return False
    mx=max(ts);last=max(i for i,v in enumerate(ts) if v==mx)
    return all(ts[i]<=ts[i-1] for i in range(last+1,len(ts)))
def mono_entry(ts,i0):
    """★ 案(2) 最後の降下のみ単調  停留に入る直前の一歩が 降下であること。
    ★★ 停留は 1<=L<=low の 最後の連続区間なので、直前の値は low 超か 0 のどちらか。
       ★ low 超なら 降下で入った。★ 0 なら 復活で入った（L=0 から行が足された）。
       → ★ この条件は 復活で停留に入った定義だけを弾く。★ 全区間の単調は要求しない。
    ★ 註  起草者は (1) と (2) が一致すると見ているが、上のとおり復活の分だけ差が出る。
       ★ 一致しなければ どちらかの実装が誤り、ではなく 復活の件数を測っていることになる。"""
    if i0<=0: return False
    return ts[i0-1]>ts[i0]
def stay_len(ts,low):
    """★ 低 L に最後に入ってから 走行末までの試行数。★ 入っていなければ None。"""
    idx=[i for i,v in enumerate(ts) if v<=low and v>=1]
    if not idx: return None
    # ★ 最後の連続区間の開始
    last=len(ts)-1
    if not (1<=ts[last]<=low): return None
    i=last
    while i>0 and 1<=ts[i-1]<=low: i-=1
    return last-i+1,i
def one(p):
    C=collections.Counter()
    # ★★ 追加  R 別の鍵に使う 台帳の識別子  <セル>/<種>（★ sbe_ledger_R.py と同じ作り方）
    RKEY=f"{pathlib.Path(p).parent.name}/{pathlib.Path(p).name.replace('.jsonl.gz','')}"
    h,end,reg,rows_,cnt,_=scan_ledger(p)
    # ★ 台帳の読みは 1 回にする（★ 試走で 3 回読んで 1本 95.7 秒かかっていた）
    use_t=collections.defaultdict(list)
    with gzip.open(p,"rt",encoding="utf-8") as fh:
        next(fh)
        for line in fh:
            r=json.loads(line)
            if r.get("record_type")!="trial": continue
            R=r.get("R_used")
            if R: use_t[R].append(r["prediction_order"])
    for R,seq in end.items():
        s2=sorted(seq);ts=[v for _,v in s2];tt=[t for t,_ in s2]
        if not ts: continue
        mx=max(ts)
        C["定義"]+=1;C["MX|"+str(min(mx,15))]+=1
        c=classify(R,end.get(R,[]),reg.get(R,[]),rows_.get(R,set()))
        strict=bool(c and c.get("strict"))
        if strict: C["現行の厳"]+=1
        mono3=mono_all(ts);dni=drops_ni(ts)
        hit={}
        for theta in THETAS:
            if mx<theta: continue
            di=drops_i(ts,theta)
            C[f"θ{theta}|max_end達成"]+=1
            for dtag,dv in (("案イ",di),("案ニ",dni)):
                if dv is None or dv<1: continue
                C[f"θ{theta}|{dtag}|drops>=1"]+=1
                for low in (2,3):
                    sl=stay_len(ts,low)
                    if sl is None: continue
                    L,i0=sl
                    mono2=mono_entry(ts,i0)
                    for mtag,ok in (("M1_単調なし",True),("M2_入口のみ",mono2),("M3_全区間",mono3)):
                        if not ok: continue
                        for N in STAYS:
                            if L<N: continue
                            key=f"θ{theta}|{dtag}|{mtag}|L{low}|N{N}"
                            C[f"新ラベル|{key}"]+=1
                            t0=tt[i0]
                            nuse=sum(1 for x in use_t.get(R,()) if x>=t0)
                            C[f"新ラベル|{key}|{'使われながら' if nuse else '使われずに'}"]+=1
                            C[f"停留採択計|{key}"]+=nuse
                            hit[key]=True
        # ★★ 追加  R 別の所属  鍵 = R|<セル>/<種>|<R名>|<指標>
        rk=f"R|{RKEY}|{R}"
        C[f"{rk}|定義"]+=1
        if strict: C[f"{rk}|厳"]+=1
        for theta in (6,8,10,12):
            if mx>=theta: C[f"{rk}|達成θ{theta}"]+=1
            if f"θ{theta}|案イ|M1_単調なし|L2|N50" in hit: C[f"{rk}|新θ{theta}"]+=1
        # ★★ 重なり  θ・drops 二案・単調三案 の格子すべてで出す
        for theta in THETAS:
            for dtag in ("案イ","案ニ"):
                for mtag in ("M1_単調なし","M2_入口のみ","M3_全区間"):
                    for low in (2,3):
                        for N in STAYS:
                            key=f"θ{theta}|{dtag}|{mtag}|L{low}|N{N}"
                            isnew=key in hit
                            if strict and isnew: C[f"重なり|{key}|厳∧新"]+=1
                            elif strict:         C[f"重なり|{key}|厳のみ"]+=1
                            elif isnew:          C[f"重なり|{key}|新のみ"]+=1
    return C
def main():
    fs=sorted(glob.glob(f"{RD}/cells/*/seed*.jsonl.gz"));assert fs,RD
    print(f"  腕 {NAME}  走行根 {RD}  走行 {len(fs)}  workers {W}",flush=True)
    t0=time.time();T=collections.Counter();n=0
    with concurrent.futures.ProcessPoolExecutor(max_workers=W) as ex:
        for c in ex.map(one,fs):
            T.update(c);n+=1
            if n%40==0: print(f"   {n}/{len(fs)} 経過 {time.time()-t0:.0f}秒",flush=True)
    json.dump(dict(T),open(ROOT/f"analysis_newlabel_2026-09-19/newlabelR_{NAME}.json","w"),ensure_ascii=False)
    print(f"  完了 経過 {time.time()-t0:.0f}秒  定義 {T['定義']:,}  現行の厳 {T['現行の厳']:,}",flush=True)
if __name__=="__main__": main()

"""★ 群S/N/P の割り当てを一箇所にまとめる（09-21 の暫定定義）。読むだけ。
群P = newlabelR の 新θ8（θ8|案イ|M1_単調なし|L2|N50）に入る定義
群S = 非P ∧ 生存述語の対に またぎ（pairs284）が 1 組以上
群N = 非P ∧ またぎ 0
★ またぎの母集合 analysis_sbe_2026-09-19/pairs252_v3a2.json は 実際には無向284組（名前は252）。
★ 生存述語は live_preds_<腕>.json（t1739 の生存行の述語の集合）。
★ 原本（abm/・runs/）には触れない。"""
import json,io,pathlib,itertools,ast
B=pathlib.Path("/Users/tatsu-admin/sfn/sfn-compression-abm")
PAIRS={tuple(sorted(x)) for x in json.load(io.open(B/"analysis_sbe_2026-09-19/pairs252_v3a2.json",encoding="utf-8"))}
def passes(arm):
    """新θ8 に入る (cell,seed,R) の集合と、newlabelR が見た全定義の集合を返す。"""
    d=json.load(io.open(B/f"analysis_newlabel_2026-09-19/newlabelR_{arm}.json",encoding="utf-8"))
    P=set(); U=set()
    for k,v in d.items():
        if not k.startswith("R|"): continue
        _,rkey,rn,tag=k.split("|",3)
        cell,seed=rkey.split("/")
        if tag=="定義": U.add((cell,seed,rn))
        elif tag=="新θ8" and v: P.add((cell,seed,rn))
    return P,U
def livepreds(arm):
    """live_preds_<腕>.json → {(cell,seed,R): [述語]}"""
    d=json.load(io.open(B/f"analysis_sbe_2026-09-19/live_preds_{arm}.json",encoding="utf-8"))
    return {tuple(ast.literal_eval(k)):v for k,v in d.items()}
def crossings(preds):
    """述語集合の中の またぎ組の数"""
    return sum(1 for a,b in itertools.combinations(sorted(set(preds)),2) if (a,b) in PAIRS)
def label(arm):
    """(cell,seed,R) -> 'P'/'S'/'N'。★ live_preds に無い定義は None（生存行なし）。"""
    P,U=passes(arm); LP=livepreds(arm); out={}
    for k in U:
        if k in P: out[k]="P"; continue
        pr=LP.get(k)
        if pr is None: out[k]=None; continue
        out[k]="S" if crossings(pr)>=1 else "N"
    return out,P,U,LP

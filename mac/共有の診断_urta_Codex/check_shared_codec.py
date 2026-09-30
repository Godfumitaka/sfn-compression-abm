"""模型を走らせず、共有の符号を小さな定義で確認する。"""
from dataclasses import replace
import json
from shared_diagnostic import setup, share_options, v39, NamedDefinition, Constituent, Relation, FrozenPrice

setup()

def make(name,prefix,state='F',counts=1):
    rows=tuple(Constituent(i,0,Relation(prefix+str(i),pred if state=='F' else v39.ERASED,args),
                           FrozenPrice(0,0,0,2),state=='F')
        for i,pred,args in [(0,'a',(prefix+'x',prefix+'y')),(1,'b',(prefix+'y',prefix+'z'))])
    definition=NamedDefinition(name,rows,2,0)
    history={(name,i):{pred:counts} for i,pred in [(0,'a'),(1,'b')]} if state!='U' else {}
    return definition,history

source,sh=make('source','s')
new,nh=make('new','n')
lengths={'a':1,'b':1}
checks=[]
a=share_options(new,nh,[(source,sh)],lengths,'A')
b=share_options(new,nh,[(source,sh)],lengths,'B')
assert a['best']['saving']==18 and a['best']['reference']==dict(a=3,b=0,c=5,d=2,e=6)
assert a['net']==2 and b['best']['saving']==26 and b['net']==10
checks.append('F二行の構造18・名前込み26・参照16・差し引き2/10')
assert share_options(new,nh,[],lengths,'A')['adjustment']==1
checks.append('共有先が無いと印1ビット')
hs,hsh=make('sourceH','s','H',5)
hn,hnh=make('newH','n','H',2)
hb=share_options(hn,hnh,[(hs,hsh)],lengths,'B')
assert hb['best']['saving_names']==8
checks.append('Hの名前集合が同じなら回数が違っても名前部分8を共有')
assert not share_options(new,nh,[(hs,hsh)],lengths,'B')['shared']
checks.append('FとHの席の状態が違う行は水準Bから除外')
un,unh=make('newU','u','U')
u=share_options(un,unh,[(source,sh)],lengths,'A')
assert not u['options'] and u['excluded_U_N']==2
checks.append('U二行を共有から除外し、本数を残す')
nh2={(k):{p:n+1 for p,n in h.items()} for k,h in nh.items()}
before=share_options(new,nh,[(source,sh),(new,nh)],lengths,'B')
after=share_options(new,nh2,[(source,sh),(new,nh)],lengths,'B')
assert before['adjustment']==after['adjustment']
checks.append('回数だけ変わる同化では共有の前後の追加費用が相殺')
source_hole=replace(source,constituents=(source.constituents[0],
    replace(source.constituents[1],alive=False,relation=replace(source.constituents[1].relation,predicate=v39.ERASED)),
    Constituent(2,0,Relation('sg','govern',('s0','s1')),FrozenPrice(0,0,0,3),True)),m_alloc=3)
source_hole_hist={('source',0):{'a':1},('source',2):{'govern':1}}
new_hole=replace(new,constituents=(new.constituents[0],
    replace(new.constituents[1],relation=replace(new.constituents[1].relation,predicate='c')),
    Constituent(2,0,Relation('ng','govern',('n0','n1')),FrozenPrice(0,0,0,3),True)),m_alloc=3)
new_hole_hist={('new',0):{'a':1},('new',1):{'c':1},('new',2):{'govern':1}}
hole=share_options(new_hole,new_hole_hist,[(source_hole,source_hole_hist)],dict(a=1,c=1,govern=2),'A')
assert hole['options'][0]['r']==2 and hole['options'][0]['holes']==1
assert hole['options'][0]['saving_structure']==15
assert hole['options'][0]['excluded_U_S']==1
checks.append('Uの子を共有せず、親のその引数は穴にして節約から除外')
print(json.dumps(dict(passed=len(checks),checks=checks),ensure_ascii=False,indent=2))

"""親子・伏せた子・H/Uの小さな場面で、述語と物の付け替えを計測する。"""
import hashlib,json,sys
from dataclasses import replace
from pathlib import Path
SOURCE=Path(__file__).resolve().parents[2];ROOT=SOURCE.parent
sys.path[:0]=[str(SOURCE/'tools'),str(SOURCE)]
from abm.definition import Constituent,NamedDefinition
from abm.domains import Entity,Relation,RelationGraph
import abm.sme as sme
import fixorder2,ustruct,strictpc,v39
fixorder2.install();v39._install_candidates();ustruct.install_matching();strictpc.install()


def G(gid,ents,rels):
 return RelationGraph(gid,tuple(Entity(e) for e in ents),tuple(Relation(i,p,tuple(a)) for i,p,a in rels))
base=G('b','ab',[('c1','hold',('a','b')),('c2','wrap',('a','b')),('P','P',('c1','c2'))])
cases={
 '名前が違う子':(base,G('t','xy',[('d1','push',('x','y')),('d2','wrap',('x','y')),('Q','P',('d1','d2'))]),None),
 '子が逆':(G('b','ab',[('c1','hold',('a','b')),('c2','push',('a','b')),('P','P',('c1','c2'))]),G('t','xy',[('d1','push',('x','y')),('d2','hold',('x','y')),('Q','P',('d1','d2'))]),None),
 '伏せられた子':(base,G('t','xy',[('d2','wrap',('x','y')),('Q','P',('dHIDDEN','d2'))]),None),
 '二階の違う子':(G('b','ab',[('c1','hold',('a','b')),('m1','M',('c1','c1')),('c2','wrap',('a','b')),('P','P',('m1','c2'))]),G('t','xy',[('d1','push',('x','y')),('n1','N',('d1','d1')),('d2','wrap',('x','y')),('Q','P',('n1','d2'))]),None),
 'Hの子':(base,G('t','xy',[('d1','hold_b',('x','y')),('d2','wrap',('x','y')),('Q','P',('d1','d2'))]),'H'),
 'Uの子':(base,G('t','xy',[('d1','push',('x','y')),('d2','wrap',('x','y')),('Q','P',('d1','d2'))]),'U')}


def mapped(g,pmap,emap):
 return replace(g,entities=tuple(replace(e,entity_id=emap.get(e.entity_id,e.entity_id)) for e in g.entities),relations=tuple(replace(r,predicate=pmap.get(r.predicate,r.predicate),arguments=tuple(emap.get(a,a) for a in r.arguments)) for r in g.relations))


def run(b,t,seat,pmap=None):
 strictpc.record_kinds(b)
 if seat is None:al=sme.map_graphs(b,t).alignment
 else:
  rows=tuple(Constituent(i,0,r,0.01873710622997919,i!=0) for i,r in enumerate(b.relations))
  d=NamedDefinition('D',rows,3,0,1)
  h={(d.name,i):{r.predicate:2} for i,r in enumerate(b.relations)}
  if seat=='H':
   h['D',0]={b.relations[0].predicate:2,(pmap or {}).get('hold_b','hold_b'):1}
  else:
   h.pop(('D',0))
  assert v39.seat_state(d,rows[0],h)==seat
  _g,al=v39.map_v39(d,h,t)
 return {'relations':dict(al.relation_mapping),'entities':dict(al.entity_mapping),'score':al.total_score,'breakdown':dict(al.score_breakdown)}
results=[]
for label,(b,t,seat) in cases.items():
 original=run(b,t,seat);names={r.predicate for g in (b,t) for r in g.relations}|{'hold_b'};entities={e.entity_id for g in (b,t) for e in g.entities}
 counts=0;first=None
 for j in range(32):
  pmap={p:'p'+hashlib.sha256(f'predicate:{j}:{p}'.encode()).hexdigest()[:12] for p in names}
  emap={e:hashlib.sha256(f'object:{j}:{e}'.encode()).hexdigest()[:16] for e in entities}
  inv={v:k for k,v in emap.items()}
  renamed=run(mapped(b,pmap,emap),mapped(t,pmap,emap),seat,pmap)
  renamed['entities']={inv.get(k,k):inv.get(v,v) for k,v in renamed['entities'].items()}
  if renamed!=original:
   counts+=1
   if first is None:first={'置換の番号':j,'元':original,'付け替え':renamed}
 results.append({'例':label,'元':original,'付け替えの回数':32,'相違':counts,'最初の相違':first})
p=Path(sys.argv[1]);assert not p.exists();p.write_text(json.dumps(results,ensure_ascii=False,indent=1)+'\n')
print(json.dumps(results,ensure_ascii=False))

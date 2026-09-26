"""記録済みの逐語痕跡を再構成し、凍結入力への prototype ゲートを測る。

世界走行、predict、update、削除判定は呼ばない。台帳の記録された部分場面、
開示、verbatim_deletion に従って状態を再構成するだけである。
"""
from __future__ import annotations
import argparse
from dataclasses import dataclass
import gzip
import json
from pathlib import Path
import sys
from typing import Any, Iterator
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
from abm.domains import Prototype, VerbatimTrace, RelationGraph, Relation
from abm.loop import _apply
from abm.sme import map_graphs


@dataclass(frozen=True)
class GateDecision:
    passed: bool
    reason: str | None
    score: float | None
    selected_graph_id: str | None
    selected_written_at: int | None
    n_traces: int

    def to_dict(self):
        return dict(passed=self.passed,reason=self.reason,score=self.score,
                    selected_graph_id=self.selected_graph_id,
                    selected_written_at=self.selected_written_at,n_traces=self.n_traces)


def evaluate_prototype(prototype: Prototype, scene: RelationGraph, threshold: float=0.0) -> GateDecision:
    """凍結された逐語痕跡に対する P1 ゲート。定義の採択とは独立。"""
    if not prototype.traces:
        return GateDecision(False,"no_prototype",None,None,None,0)
    ranked=[(map_graphs(trace.scene,scene).alignment.total_score,trace)
            for trace in prototype.traces]
    score,selected=min(ranked,key=lambda x:(-x[0],-x[1].written_at,x[1].scene.graph_id))
    passed=score>=threshold
    return GateDecision(passed,None if passed else "below_threshold",score,
                        selected.scene.graph_id,selected.written_at,len(prototype.traces))


@dataclass(frozen=True)
class GateObservation:
    t: int
    before: Prototype
    after: Prototype
    decision: GateDecision

    @property
    def passed(self): return self.decision.passed
    @property
    def score(self): return self.decision.score
    @property
    def reason(self): return self.decision.reason


class PrototypeReplay:
    def __init__(self, threshold: float=0.0):
        self.threshold=threshold
        self.prototype=Prototype()
        self.last_trial=-1

    def consume(self, row: dict[str,Any]) -> GateObservation:
        t=row['prediction_order']
        before=self.prototype
        decision=evaluate_prototype(before,RelationGraph.from_dict(row['partial']),self.threshold)
        self.advance(row)
        return GateObservation(t,before,self.prototype,decision)

    def advance(self,row: dict[str,Any]) -> Prototype:
        """生成・忘却を決定し直さず、既存記録だけを反映する。"""
        t=row['prediction_order']
        if t!=self.last_trial+1:
            raise ValueError(f'nonconsecutive trial: {self.last_trial} -> {t}')
        written_at=max((trace.written_at for trace in self.prototype.traces),default=-1)+1
        graph=RelationGraph.from_dict(row['partial'])
        if row['f_fired']:
            held=Relation.from_dict(row['held_out'])
            if all(r.relation_id!=held.relation_id for r in graph.relations):
                graph=RelationGraph(graph.graph_id,graph.entities,(*graph.relations,held))
        traces=[*self.prototype.traces,VerbatimTrace(written_at,graph)]
        for event in row['reg_del_events']:
            if event['kind']!='verbatim_deletion': continue
            key=(event['graph_id'],event['written_at'])
            matching=[i for i,trace in enumerate(traces)
                      if (trace.scene.graph_id,trace.written_at)==key]
            if len(matching)!=1:
                raise ValueError(f'trial={t}: verbatim deletion target count {len(matching)} for {key}')
            traces.pop(matching[0])
        self.prototype=Prototype(tuple(traces));self.last_trial=t
        return self.prototype


def iter_gates(compact_path: str | Path) -> Iterator[GateObservation]:
    replay=PrototypeReplay()
    with gzip.open(compact_path,'rt') as stream:
        meta=json.loads(next(stream))
        if meta['record_type']!='analysis_header': raise ValueError('analysis_header required')
        for line in stream:
            yield replay.consume(json.loads(line))


def verify_snapshot_prototype(raw_prototype: dict[str,Any], expected: Prototype,
                              known_graphs: dict[str,RelationGraph]) -> int:
    """snapshot の ID と順序を失った内容を、実入力の順序情報で補完して検証する。"""
    raw_traces=raw_prototype['traces']
    observed={};repairs=0
    for trace in raw_traces:
        raw=trace['scene'];gid=raw['graph_id'];ordered=known_graphs[gid]
        ordered_by_id={r.relation_id:r for r in ordered.relations}
        ids=[r['relation_id'] for r in raw['relations']]
        if len(ids)!=len(set(ids)) or set(ids)!=set(ordered_by_id):
            raise ValueError(f'prototype snapshot relation ID mismatch for {gid}')
        for r in raw['relations']:
            source=ordered_by_id[r['relation_id']]
            if r['predicate']!=source.predicate or sorted(r['arguments'])!=sorted(source.arguments):
                raise ValueError(f'prototype snapshot relation content mismatch for {gid}')
            if r.get('attributes',{})!=dict(source.attributes):
                raise ValueError(f'prototype snapshot attributes mismatch for {gid}')
            repairs+=int(tuple(r['arguments'])!=source.arguments)
        expected_entities={e.entity_id:e.to_dict() for e in ordered.entities}
        if {e['entity_id']:e for e in raw['entities']}!=expected_entities:
            raise ValueError(f'prototype snapshot entities mismatch for {gid}')
        key=(gid,trace['written_at'])
        if key in observed: raise ValueError(f'duplicate prototype trace {key}')
        observed[key]=ordered.to_dict()
    expected_map={(trace.scene.graph_id,trace.written_at):trace.scene.to_dict()
                  for trace in expected.traces}
    if observed!=expected_map:
        raise ValueError('prototype snapshot trace set/content mismatch')
    # snapshot は trace の配列順もソートするため、append順そのものは情報源にしない。
    return repairs


def audit(compact_path:Path,ledger_path:Path,output_path:Path):
    from collections import Counter
    counts=Counter(); examples=[]; prototype_raw=None;known={};replay=PrototypeReplay()
    with gzip.open(compact_path,'rt') as compact,gzip.open(ledger_path,'rt') as ledger,output_path.open('x') as out:
        meta=json.loads(next(compact));header=json.loads(next(ledger))
        if meta['header']!=header: raise ValueError('compact / ledger header mismatch')
        print('compact',compact_path,file=out);print('ledger',ledger_path,file=out)
        for compact_line,ledger_line in zip(compact,ledger,strict=True):
            row=json.loads(compact_line);original=json.loads(ledger_line)
            if row['prediction_order']!=original['prediction_order']: raise ValueError('trial mismatch')
            observation=replay.consume(row)
            # current graph は f の開示を反映した順序つき入力から作られる。
            scene=RelationGraph.from_dict(row['partial'])
            if row['f_fired']:
                edge=Relation.from_dict(row['held_out'])
                if all(r.relation_id!=edge.relation_id for r in scene.relations):
                    scene=RelationGraph(scene.graph_id,scene.entities,(*scene.relations,edge))
            known[scene.graph_id]=scene
            snapshot=original['state_snapshot']
            if snapshot['kind']=='full': prototype_raw=snapshot['value']['prototype']
            elif snapshot['kind']=='delta':
                if 'prototype' in snapshot['changes']:
                    prototype_raw=_apply(prototype_raw,snapshot['changes']['prototype'])
            else: raise ValueError('full / delta snapshot required')
            repairs=verify_snapshot_prototype(prototype_raw,observation.after,known)
            counts['rows']+=1;counts['snapshot_rows_verified']+=1
            counts['snapshot_argument_order_repairs']+=repairs
            counts['gate_passed']+=observation.passed
            if observation.reason: counts[observation.reason]+=1
            logged=original['abstain_reason']
            if not observation.passed and logged!=observation.reason:
                counts['gate_reason_mismatch']+=1
            if observation.passed and logged in {'below_threshold','no_prototype'}:
                counts['gate_reason_mismatch']+=1
            result={'t':observation.t,**observation.decision.to_dict(),
                    'logged_abstain_reason':logged,'snapshot_verified':True}
            print(json.dumps(result,ensure_ascii=False),file=out)
            if not observation.passed and len(examples)<8:examples.append(result)
        print('COUNTS',json.dumps(dict(counts),ensure_ascii=False),file=out)
        print('EXAMPLES',json.dumps(examples,ensure_ascii=False),file=out)
    print(json.dumps({'output':str(output_path),'counts':dict(counts),'examples':examples},ensure_ascii=False))


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--compact',required=True,type=Path)
    parser.add_argument('--ledger',required=True,type=Path)
    parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args();audit(args.compact,args.ledger,args.output)

if __name__=='__main__':main()

"""指示10の外付けの照合ごとのCPU時間。入力・返り値・乱数は変えない。"""
from pathlib import Path
import json,os,sys,time,types
SOURCE=Path(os.environ['SME_EXACT_SOURCE'])
sys.path[:0]=[str(SOURCE/'tools'),str(SOURCE)]
import v3_run
REAL_WORKER=v3_run.worker


def worker(task):
    import sweep
    real_run=sweep.run_one
    def run_one(task):
        import abm.loop as loop
        import cstar_runtime as cstar
        import smereplay,smeshared,v39
        from cstar_matcher import CstarMatcher
        root=Path(task['out_root']).parent
        stream=(root/'match_times.jsonl').open('x')
        record=dict(observer_cpu=0.,in_prediction=False,predictions=0,definition_calls=0,engine_calls=0,pipeline_calls=0)
        real_predict,real_map,real_match=loop.predict,v39.map_v39,CstarMatcher.match
        real_graph=smeshared.map_graphs
        def write(value):
            begin=time.process_time()
            stream.write(json.dumps(value,ensure_ascii=False,separators=(',',':'))+'\n')
            record['observer_cpu']+=time.process_time()-begin
        def predict(ai,state,config,rng):
            prior=record['in_prediction'];record['in_prediction']=True
            begin=time.process_time();aux=record['observer_cpu']
            try:
                out,pending=real_predict(ai,state,config,rng)
            finally:
                record['in_prediction']=prior
            elapsed=time.process_time()-begin-(record['observer_cpu']-aux)
            write(dict(kind='prediction_counts',trial_index=smereplay.ST['trial'],memory_definitions=len(state.definitions),
                       gate_passed_definitions=len(out.trace.get('tau_passed_defs',())),prediction_cpu_seconds=elapsed))
            record['predictions']+=1;stream.flush()
            return out,pending
        def map_v39(d,slot_history,scene):
            enabled=cstar.active();in_prediction=record['in_prediction']
            begin=time.process_time();wall=time.perf_counter();aux=record['observer_cpu']
            result=real_map(d,slot_history,scene)
            elapsed=time.process_time()-begin-(record['observer_cpu']-aux)
            if enabled:
                assert elapsed>=-1e-6
                write(dict(kind='definition_mapping',trial_index=smereplay.ST['trial'],R=d.name,
                           prediction=in_prediction,result=result[1].sme_result_id,
                           inclusive_cpu_seconds=max(elapsed,0.),wall_seconds=time.perf_counter()-wall))
                record['definition_calls']+=1
            return result
        def match(self,left,right,**kw):
            observed_at=time.process_time()
            frame=sys._getframe(1)
            raw=frame.f_locals.get('base_graph')
            graph_id=getattr(raw,'graph_id',None)
            definition=(graph_id.removeprefix('definition:') if isinstance(graph_id,str) and graph_id.startswith('definition:') else None)
            caller=frame.f_locals.get('use','unknown')
            del frame
            record['observer_cpu']+=time.process_time()-observed_at
            begin=time.process_time();wall=time.perf_counter();aux=record['observer_cpu']
            result=real_match(self,left,right,**kw)
            elapsed=time.process_time()-begin-(record['observer_cpu']-aux)
            assert elapsed>=-1e-6
            write(dict(kind='cstar_matcher_call',trial_index=smereplay.ST['trial'],R=definition,caller=caller,
                       prediction=record['in_prediction'],cpu_seconds=max(elapsed,0.),wall_seconds=time.perf_counter()-wall,
                       retained_correspondences=len(result.candidates)))
            record['engine_calls']+=1
            return result
        def graph_map(base_graph,target_graph_partial,params=None,*,prototype=None,prototype_prior_weight=0.0):
            # _callerは最初のsmeshared以外のframeを使う。下でこの観測frameも
            # 同じmodule名にすることで、元の呼び出し元と種をそのまま保つ。
            observed_at=time.process_time()
            caller=smeshared._caller()
            graph_id=base_graph.graph_id
            definition=graph_id.removeprefix('definition:') if graph_id.startswith('definition:') else None
            record['observer_cpu']+=time.process_time()-observed_at
            begin=time.process_time();wall=time.perf_counter();aux=record['observer_cpu']
            result=real_graph(base_graph,target_graph_partial,params,
                              prototype=prototype,prototype_prior_weight=prototype_prior_weight)
            elapsed=time.process_time()-begin-(record['observer_cpu']-aux)
            assert elapsed>=-1e-6
            write(dict(kind='matching_pipeline_call',trial_index=smereplay.ST['trial'],R=definition,caller=caller,
                       prediction=record['in_prediction'],result=result.alignment.sme_result_id,
                       inclusive_cpu_seconds=max(elapsed,0.),wall_seconds=time.perf_counter()-wall))
            record['pipeline_calls']+=1
            return result
        graph_globals=dict(globals(),__name__='smeshared')
        observed_graph=types.FunctionType(graph_map.__code__,graph_globals,graph_map.__name__,
                                          graph_map.__defaults__,graph_map.__closure__)
        observed_graph.__kwdefaults__=graph_map.__kwdefaults__
        graph_aliases=[]
        # nativeのinstallと同じく、元の関数を参照している窓口だけを包む。
        # OLD_MAP（旧照合の診断の参照）や別の関数は包まない。
        for module in tuple(sys.modules.values()):
            if module is None:continue
            for key,value in tuple(vars(module).items()):
                if value is real_graph:
                    graph_aliases.append((module,key))
                    setattr(module,key,observed_graph)
        # native map_v39自身のframeを残すので、_callerの種の材料はv39:map_v39のまま。
        loop.predict,v39.map_v39,CstarMatcher.match=predict,map_v39,match
        started_cpu=time.process_time()
        try:
            result=real_run(task)
        finally:
            loop.predict,v39.map_v39,CstarMatcher.match=real_predict,real_map,real_match
            for module,key in graph_aliases:
                assert getattr(module,key) is observed_graph
                setattr(module,key,real_graph)
            stream.close()
        assert record['predictions']==task['cfg']['trial_count']
        (root/'observations_complete.json').write_text(json.dumps(dict(passed=True,**record,
             configured_trials=task['cfg']['trial_count'],model_inputs_outputs_unchanged=True,
             process_cpu_seconds=time.process_time()-started_cpu,
             timing='time.process_timeのCPU秒とperf_counterの実時間。定義のmap_v39は図の作成・分布・照合・旧照合の記録・書き出しを含む。matching_pipeline_callはsmeshared.map_graphsの入口から戻りまで、CstarMatcher.matchは控えの鍵・控えの検索・照合器を含む。観測の書き出しとengineの追加の記録の負荷は外側のCPU秒から引く。各秒は入れ子なので足さない。',
             exactness='乱数を呼ばず、元の関数を一度呼び、同じ返り値をそのまま返す。実際の全バイトの一致は別の関門で確認する。'),ensure_ascii=False,indent=2)+'\n')
        return result
    sweep.run_one=run_one
    return REAL_WORKER(task)


def main():
    command=json.loads(Path(sys.argv[1]).read_text())
    assert command[command.index('--seeds')+1]=='1'
    assert not Path(command[3]).exists(),'既存の出力を上書きしない'
    v3_run.worker=worker;sys.argv=command[1:];os.chdir(SOURCE);v3_run.main()


if __name__=='__main__':main()

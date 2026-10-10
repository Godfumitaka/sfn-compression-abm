"""指示11：接続済みの最終入口の後で、500ごとの記録・状態・乱数を観察する。"""
from contextlib import contextmanager
from pathlib import Path
import io, json, sys
from instruction11_io import confirmed_content, names, save, sha
from confirmed_hash import hash_confirmed

def encoded(value):
    from smereplay import encode
    return encode(value)

def packed(value):
    return json.dumps(encoded(value),ensure_ascii=False,separators=(",",":")).encode()

def key_seed(key):
    return key[-1] if isinstance(key,tuple) and len(key)>=2 and key[-2]=="call-seed-v1" else None

def cache_rows(engine, origins):
    """原控えを触らず、P10と同じ由来の欄を後で読める形で保存する。"""
    result={}
    for table in ("cache","cache_rng","self_cache"):
        result[table]=[]
        for key,value in getattr(engine,table).items():
            seed=key_seed(key)
            if seed is not None:
                assert seed in origins, "観察していない控えの種は推測しない"
            result[table].append(dict(key_sha256=sha(packed(key)),value_sha256=sha(packed(value)),
                seed=seed,origin=None if seed is None else origins[seed]))
    return result

def posthoc_prune(rows, trial):
    return {name:[r for r in records if name=="self_cache" or r["seed"] is None or r["origin"]==trial]
            for name,records in rows.items()}

def flush_records(ledger):
    """接続済みの自分の記録のflushだけ。閉じたり行を追加したりしない。"""
    streams=[getattr(ledger,"_stream",None)]
    visited=set()
    def closures(value):
        if id(value) in visited:return
        visited.add(id(value))
        if isinstance(value,io.IOBase):streams.append(value)
        elif isinstance(value,dict):
            for x in value.values():closures(x)
        elif isinstance(value,(tuple,list)):
            for x in value:closures(x)
        else:
            for cell in getattr(value,"__closure__",None) or ():
                try:closures(cell.cell_contents)
                except ValueError:pass
    import abm.loop as loop
    for value in (loop._agent_input,loop.predict,loop.m1,loop.apply_theta,loop._ledger_record):
        closures(value)
    for name in ("v3_run","v39","smeshared","smereplay","attnsme","attnstage2_runtime",
                 "probeworld","answerlog","routelog","answergap"):
        mod=sys.modules.get(name)
        if mod is None:continue
        for value in vars(mod).values():
            if isinstance(value,dict):
                streams.extend(x for x in value.values() if isinstance(x,io.IOBase))
            elif isinstance(value,io.IOBase):
                streams.append(value)
    seen=set()
    for stream in streams:
        if stream is not None and id(stream) not in seen and not stream.closed:
            seen.add(id(stream));stream.flush()

def individuals():
    import attnsme
    return {agent:{"a":value["a"],"observations":vars(value["observations"])}
            for agent,value in attnsme.ST.get("individuals",{}).items()}

@contextmanager
def observe(out, ledger, *, attention_enabled=True, stage2_enabled=True):
    """模型の各入口を一度呼んだ後だけ観察し、終了時に元の入口へ戻す。"""
    import abm.loop as loop, smeshared, probeworld, cstar_runtime as cstar
    import attnstage2_runtime as stage2
    out=Path(out);dest=out/"comparison_checkpoints";dest.mkdir(exist_ok=False)
    native_input,native_predict,native_record=loop._agent_input,loop.predict,loop._ledger_record
    native_key=cstar.ENGINE.match_key
    native_sme_key=smeshared.ENGINE.match_key
    native_append=ledger.append
    absent=object();prior_append=vars(ledger).get("append",absent)
    prior_key=vars(cstar.ENGINE).get("match_key",absent)
    prior_sme_key=vars(smeshared.ENGINE).get("match_key",absent)
    native_save,native_restore=probeworld._snapshot_modules,probeworld._restore_modules
    native_probe=probeworld._probe
    audit=dict(trial=None,origins={},requests=0,forbidden_reads=0,probe_saves=0,probe_restores=0)
    boundary={}
    inside_probe=False
    def agent_input(trial,state):
        audit["trial"]=trial.trial
        return native_input(trial,state)
    def requested(key):
        seed=key_seed(key)
        if seed is not None:
            audit["requests"]+=1
            origin=audit["origins"].setdefault(seed,audit["trial"])
            if origin!=audit["trial"]:audit["forbidden_reads"]+=1
        return key
    def match_key(*args,**kw):
        return requested(native_key(*args,**kw))
    def sme_key(*args,**kw):
        return requested(native_sme_key(*args,**kw))
    def predict(ai,state,cfg,rng):
        result=native_predict(ai,state,cfg,rng)
        boundary["last_prediction_rng"]=encoded(rng.getstate())
        return result
    def record(agent_id,trial,config,output,score,coin,state,*args,**kw):
        result=native_record(agent_id,trial,config,output,score,coin,state,*args,**kw)
        boundary.update(state=state,trial=trial.trial,agent_id=agent_id)
        return result
    def snapshot():
        value=native_save()
        if inside_probe:audit["probe_saves"]+=1
        return value
    def restore(saved):
        value=native_restore(saved)
        if inside_probe:audit["probe_restores"]+=1
        return value
    def probe(*args,**kw):
        nonlocal inside_probe
        previous=inside_probe;inside_probe=True
        try:return native_probe(*args,**kw)
        finally:inside_probe=previous
    def append(row):
        result=native_append(row)
        t=row["prediction_order"]
        if t==500 or (t>=1000 and t%1000==0) or t==4999:
            flush_records(ledger)
            m1_checkpoint(out, dest, t, attention_enabled=attention_enabled,
                          stage2_enabled=stage2_enabled)
        n=t+1
        if n%500==0:
            assert boundary["trial"]==t
            flush_records(ledger)
            folder=dest/f"completed_{n:04d}";folder.mkdir()
            proofs=[]
            for rel in sorted(names(out)):
                # 指示26：確定した原行のSHAと行数だけ。履歴の複製を作らない。
                proof=hash_confirmed(out/rel)
                proofs.append(dict(path=str(rel),**proof))
            save(folder/"state.json",dict(agent_id=boundary["agent_id"],trial=t,
                 state=encoded(boundary["state"]),attention=encoded(individuals()),
                 questions=encoded({a:q.record() for a,q in stage2.ST.get("questions",{}).items()})))
            save(folder/"rng.json",dict(last_prediction_rng=boundary["last_prediction_rng"],
                 sme=encoded(smeshared.ENGINE.rng.getstate()),cstar=encoded(cstar.ENGINE.rng.getstate())))
            raw=cache_rows(cstar.ENGINE,audit["origins"])
            save(folder/"cache_raw.json",raw)
            save(folder/"cache_posthoc_p10.json",posthoc_prune(raw,t))
            save(folder/"cache_sme.json",cache_rows(smeshared.ENGINE,audit["origins"]))
            guard=getattr(cstar.ENGINE,"cache_prune_guard",None)
            proof=dict(completed_trials=n,last_trial=t,configured_trial_count=5000,horizon=5000,
                records=proofs,forbidden_reads=audit["forbidden_reads"],
                guard_forbidden_reads=None if guard is None else guard.forbidden_reads,
                requests=audit["requests"],probe_save_calls=audit["probe_saves"],
                probe_restore_calls=audit["probe_restores"],confirmed=True)
            save(folder/"confirmed.json",proof)
        return result
    loop._agent_input,loop.predict,loop._ledger_record=agent_input,predict,record
    cstar.ENGINE.match_key=match_key
    smeshared.ENGINE.match_key=sme_key
    probeworld._snapshot_modules,probeworld._restore_modules=snapshot,restore
    probeworld._probe=probe
    ledger.append=append
    try:yield
    finally:
        loop._agent_input,loop.predict,loop._ledger_record=native_input,native_predict,native_record
        probeworld._snapshot_modules,probeworld._restore_modules=native_save,native_restore
        probeworld._probe=native_probe
        if prior_key is absent:del cstar.ENGINE.match_key
        else:cstar.ENGINE.match_key=prior_key
        if prior_sme_key is absent:del smeshared.ENGINE.match_key
        else:smeshared.ENGINE.match_key=prior_sme_key
        if prior_append is absent:del ledger.append
        else:ledger.append=prior_append

def m1_rows(data, through=500):
    rows=[json.loads(x) for x in data.splitlines()]
    rows=[x for x in rows if 200<=x["trial"]<=through]
    assert [x["trial"] for x in rows]==list(range(200,through+1)), "指定範囲の確定行がまだ無い"
    small=sum(x["definitions"]<=1 for x in rows)
    return dict(zero_based=True,first_trial=200,last_trial=through,trials=len(rows),
                definitions_at_most_one=small,fraction=small/len(rows),
                stop_criterion=10*small>=9*len(rows),
                definition_count_stage="学習と忘却後。注意の原記録のdefinitions",
                claude_confirmation_required=True,automatic_stop=False)


def m1_checkpoint(out, dest, trial, *, attention_enabled, stage2_enabled):
    """指示20：注意も第二段もない構成は、M1の適用外を別記録に残す。"""
    if not attention_enabled and not stage2_enabled:
        value = dict(last_trial=trial, applicable=False, attention_enabled=False,
                     stage2_enabled=False, reason="注意も第二段もない構成", automatic_stop=False)
    else:
        files = list(Path(out).glob("attention/**/*.jsonl.gz"))
        assert len(files) == 1, "注意又は第二段のある構成の原注意ファイルが必要"
        value = m1_rows(confirmed_content(files[0]), trial)
    save(Path(dest) / f"m1_at_trial{trial}.json", value)

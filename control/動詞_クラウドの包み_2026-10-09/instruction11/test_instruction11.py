"""指示11の境界を人工記録で検査。学習模型・種21〜40は起動も読み取りもしない。"""
import gzip,json,random,sys
from pathlib import Path
from dataclasses import dataclass
from types import SimpleNamespace
import pytest
sys.path[:0]=[str(Path(__file__).resolve().parent),str(Path(__file__).resolve().parents[1]),
               str(Path(__file__).resolve().parents[2])]
import cloud_compare as C,cloud_run as R
from test_package import fixture,CELL
from instruction11_io import without_time,confirmed_content,compare_outputs,copy_confirmed,compare_paths
from checkpoint_observer import observe,m1_rows,posthoc_prune
from production_commands import emit
from checkpoint_compare import compare as compare_checkpoint
from speed_gate import mechanisms,gate
from model_count import count_models

def flags(on=False):
    return ["--stage2","on","--stage2-speed","on" if on else "off",
            "--stage2-cache-prune","on" if on else "off","--probe-world"]

def test_speed200_probe_mutation_is_a_mismatch(tmp_path):
    a=fixture(tmp_path/"a",True,200,flags());b=fixture(tmp_path/"b",True,200,flags(True))
    assert C.compare(a,b,tmp_path/"ok.json",200)==0
    (b/f"output/side/{CELL}/seed001.probe.jsonl").write_bytes(b"changed answer\n")
    assert C.compare(a,b,tmp_path/"bad.json",200)==1
    assert R.read(tmp_path/"bad.json")["mismatching_files"]==1

def test_native_probe_schema_uses_fixed_question_count(tmp_path):
    a=fixture(tmp_path/"a",True,300)
    assert R.complete(a,300)["probeworld"]["probes"]==48
    p=a/"output/manifest.jsonl";v=R.read(p);v["probeworld"]["rows"]=48;p.write_text(json.dumps(v))
    with pytest.raises(AssertionError):R.complete(a,300)

def test_time_only_mask_preserves_order_and_other_values():
    a=b'{"z":1, "seconds":1.234,"wrapper_seconds":2e-4, "q":[2,1]}\n'
    b=b'{"z":1, "seconds":9.234,"wrapper_seconds":3e-4, "q":[2,1]}\n'
    assert without_time(a)==without_time(b)
    assert without_time(a)!=without_time(b.replace(b'[2,1]',b'[1,2]'))
    assert without_time(a).startswith(b'{"z":1, "seconds":0,')

def test_stage2_and_researcher_are_compared(tmp_path):
    a=tmp_path/"a";b=tmp_path/"b"
    for out in (a,b):
        (out/"stage2").mkdir(parents=True);(out/"researcher").mkdir()
        (out/"stage2/x.jsonl").write_text('{"seconds":1,"rows":[1]}\n')
        (out/"researcher/x.jsonl").write_text('{"V":0.5}\n')
    (b/"stage2/x.jsonl").write_text('{"seconds":2,"rows":[1]}\n')
    assert compare_outputs(a,b)["passed"]
    (b/"stage2/x.jsonl").write_text('{"seconds":2,"rows":[2]}\n')
    assert not compare_outputs(a,b)["passed"]

def test_flushed_open_gzip_is_read_without_completing_it(tmp_path):
    p=tmp_path/"rows.gz"
    with gzip.open(p,"wb") as f:
        f.write(b'{"trial":499}\n');f.flush()
        assert confirmed_content(p)==b'{"trial":499}\n'
        f.write(b'{"trial":500}\n');f.flush()
        assert len(confirmed_content(p).splitlines())==2
        proof=copy_confirmed(p,tmp_path/"copy")
        assert proof["bytes"]==28 and (tmp_path/"copy").read_bytes()==confirmed_content(p)

def test_chunked_record_compare_keeps_first_byte_position(tmp_path):
    a=tmp_path/"a";b=tmp_path/"b"
    a.write_bytes(b"a"*(1024*1024)+b"same\n")
    b.write_bytes(b"a"*(1024*1024)+b"sAme\n")
    row=compare_paths("side/x.jsonl",a,b,raw_evidence=True)
    assert not row["equal"] and row["mismatching_bytes"]==1
    assert row["first_mismatch_byte"]==1024*1024+1

def test_p10_filter_is_posthoc_and_does_not_change_raw():
    raw=dict(cache=[dict(seed=1,origin=1),dict(seed=2,origin=2),dict(seed=None,origin=None)],
             cache_rng=[dict(seed=1,origin=1)],self_cache=[dict(seed=1,origin=1)])
    copy=json.loads(json.dumps(raw))
    pruned=posthoc_prune(raw,2)
    assert raw==copy and len(pruned["cache"])==2 and not pruned["cache_rng"] and pruned["self_cache"]==raw["self_cache"]

def test_m1_boundary_is_zero_based_inclusive_and_integer_threshold():
    data=b"".join((json.dumps(dict(trial=n,definitions=1 if n<470 else 2))+"\n").encode() for n in range(501))
    r=m1_rows(data)
    assert r["trials"]==301 and not r["stop_criterion"] and r["automatic_stop"] is False
    with pytest.raises(AssertionError):m1_rows(b"\n".join(data.splitlines()[:-1])+b"\n")
    later=b"".join((json.dumps(dict(trial=n,definitions=1))+"\n").encode() for n in range(1001))
    assert m1_rows(later,1000)["stop_criterion"] and m1_rows(later,1000)["trials"]==801

def test_calibration_pair_and_production_drafts_are_not_starts(tmp_path):
    p=R.read(R.HERE/"plan.json")
    for sign in ("off","on"):
        x=p["labels"]["calibration200_"+sign];y=p["labels"]["speed200_"+sign]
        assert x["flags"]==y["flags"]+["--no-forget-exec"] and x["completed_trials"]==200
    out=emit(tmp_path/"draft")
    v=R.read(out/"21_seed001.json")
    assert "--use-forget-attn" in v["flags"] and not v["ready_to_start"] and v["dependency"]
    for arm in ("21","22"):
        v=R.read(out/(arm+"_seed001.json"));assert not v["speed_applicable"]
        for f in ("--stage2-speed","--stage2-cache-prune"):assert v["flags"][v["flags"].index(f)+1]=="off"
    p=R.read(R.HERE/"production_templates.json")
    assert p["lambda_value"] is None and p["source_commit"] is None
    assert p["arms"]["#19c"]["seeds"]==list(range(41,49))
    assert R.read(out/"19_seed003.json")["claude_M1_required"]
    assert p["instruction12_policy"]["after_Claude_M1_200_500_start3_10_without_waiting_calibration1000"]

def test_speed_judgement_requires_prior_on100_record(tmp_path):
    with pytest.raises(AssertionError):
        gate(tmp_path/"a",tmp_path/"b",tmp_path/"verdict",tmp_path/"no-decision.json","unrecorded")
    assert not (tmp_path/"verdict").exists()

def test_production_wrapper_uses_existing_worker_classification():
    parent="python /srv/verb/source/tools/verb_measurement/production/measurement_driver.py /srv/verb/source"
    rows={1:dict(pid=1,ppid=0,state="S",command=parent),
          2:dict(pid=2,ppid=1,state="R",command="python -c multiprocessing spawn_main()"),
          3:dict(pid=3,ppid=1,state="T",command="python -c multiprocessing spawn_main()")}
    models,unknown,paused,stopped=count_models(rows)
    assert len(models)==1 and not unknown and len(stopped)==1

@dataclass
class State:
    definitions:dict

def test_observer_calls_native_once_restores_and_keeps_bytes(tmp_path,monkeypatch):
    import abm.loop as loop, smeshared, cstar_runtime as cstar,probeworld as pw
    import attnsme,attnstage2_runtime as stage
    counts=dict(input=0,predict=0,record=0,append=0)
    def ai(trial,state):counts["input"]+=1;return trial
    def predict(ai,state,cfg,rng):counts["predict"]+=1;rng.random();return ("answer","pending")
    attention=tmp_path/"attention"/"x.jsonl.gz";attention.parent.mkdir()
    stream=gzip.open(attention,"wt")
    def record(agent,trial,cfg,output,score,coin,state,*args,**kw):
        counts["record"]+=1;stream.write(json.dumps(dict(trial=trial.trial,definitions=len(state.definitions)))+"\n")
        return ({},None,"hash")
    for key,value in (("_agent_input",ai),("predict",predict),("_ledger_record",record)):monkeypatch.setattr(loop,key,value)
    def engine():
        return SimpleNamespace(rng=random.Random(1),cache={},cache_rng={},self_cache={},
                               match_key=lambda key:key)
    ce,se=engine(),engine()
    monkeypatch.setattr(cstar,"ENGINE",ce);monkeypatch.setattr(smeshared,"ENGINE",se)
    monkeypatch.setattr(attnsme,"ST",dict(f=stream,individuals={}))
    monkeypatch.setattr(stage,"ST",dict(questions={}))
    monkeypatch.setattr(pw,"_snapshot_modules",lambda:None)
    monkeypatch.setattr(pw,"_restore_modules",lambda saved:None)
    monkeypatch.setattr(pw,"_probe",lambda:pw._restore_modules(pw._snapshot_modules()))
    rows=tmp_path/"side"/"x.jsonl";rows.parent.mkdir()
    raw=rows.open("w")
    def append(row):counts["append"]+=1;raw.write(json.dumps(row)+"\n")
    ledger=SimpleNamespace(append=append,_stream=raw)
    with observe(tmp_path,ledger):
        for n in range(501):
            trial=SimpleNamespace(trial=n);state=State({"R":n})
            loop._agent_input(trial,state)
            loop.predict(None,state,None,random.Random(n))
            key=("fixture","call-seed-v1",n)
            ce.match_key(key);ce.cache[key]=n;ce.cache_rng[key]=n
            loop._ledger_record("agent",trial,None,None,None,None,state)
            if (n+1)%100==0:pw._probe()
            ledger.append({"prediction_order":n})
    stream.close();raw.close()
    assert counts==dict(input=501,predict=501,record=501,append=501)
    assert loop.predict is predict and ledger.append is append and "match_key" in vars(ce)
    assert rows.read_bytes()==b"".join((json.dumps({"prediction_order":n})+"\n").encode() for n in range(501))
    root=tmp_path/"comparison_checkpoints"/"completed_0500"
    p=R.read(root/"confirmed.json");assert p["probe_save_calls"]==p["probe_restore_calls"]==5
    assert p["forbidden_reads"]==0 and R.read(root/"state.json")["trial"]==499
    assert R.read(tmp_path/"comparison_checkpoints"/"m1_at_trial500.json")["trials"]==301

def checkpoint_fixture(case,on):
    case.mkdir();flags=["--seeds","1","--stage2-speed","on" if on else "off",
                       "--stage2-cache-prune","on" if on else "off","--probe-world"]
    R.save(case/"runtime.json",dict(flags=flags,source_commit="same",model_commit="same",
           observer_sha256="same",configured_trial_count=5000,horizon=5000))
    R.save(case/"start.json",dict(machine_sha256="same"))
    folder=case/"output"/"comparison_checkpoints"/"completed_0500"
    (folder/"records"/"side").mkdir(parents=True)
    raw=b'{"answer":"same","trial":499}\n'
    (folder/"records"/"side"/"seed001.probe.jsonl").write_bytes(raw)
    for name in ("state","rng","cache_sme","cache_posthoc_p10"):
        R.save(folder/(name+".json"),{"value":1})
    R.save(folder/"cache_raw.json",{"value":1 if on else 2})
    from instruction11_io import sha
    R.save(folder/"confirmed.json",dict(confirmed=True,completed_trials=500,last_trial=499,
        records=[dict(path="side/seed001.probe.jsonl",sha256=sha(raw))],
        probe_save_calls=5,probe_restore_calls=5,forbidden_reads=0,guard_forbidden_reads=0 if on else None))
    return case,folder

def test_parallel_probe_rng_and_prior_failure_cannot_be_overwritten(tmp_path):
    a,_=checkpoint_fixture(tmp_path/"a",False);b,bp=checkpoint_fixture(tmp_path/"b",True)
    reports=tmp_path/"reports";reports.mkdir()
    assert compare_checkpoint(a,b,500,reports/"checkpoint_500_pass.json")==0
    assert R.read(reports/"checkpoint_500_pass.json")["provisional"]
    (bp/"rng.json").write_text('{"value":2}\n')
    assert compare_checkpoint(a,b,500,reports/"checkpoint_500_bad.json")==1
    (bp/"rng.json").write_text((tmp_path/"a"/"output"/"comparison_checkpoints"/"completed_0500"/"rng.json").read_text())
    assert compare_checkpoint(a,b,500,reports/"checkpoint_500_later.json")==1
    assert R.read(reports/"checkpoint_500_later.json")["prior_mismatch"]

def test_mechanism_actual_counts_include_post_probe_and_do_not_double_summary(tmp_path):
    a=fixture(tmp_path/"a",True,200,flags(True));out=a/"output"
    p=out/f"ledgers/cells/{CELL}/seed001.jsonl.gz"
    with gzip.open(p,"wt") as f:
        for n in range(200):
            f.write(json.dumps(dict(record_type="trial",prediction_order=n,
                deletion_event=[dict(v39="FH")]+([dict(kind="definition_removed")] if n==110 else [])))+"\n")
    (out/f"side/{CELL}/seed001.jsonl").write_text('{"kind":"birth","trial":120,"R":"R1"}\n')
    (out/f"side/{CELL}/seed001.probe.jsonl").write_text('{}\n'*96)
    (out/f"side/{CELL}/seed001.routing.jsonl").write_text('{}\n')
    guard=out/"p10_cache_guard.jsonl.gz"
    with gzip.open(guard,"wt") as f:
        f.write('{"kind":"trial_boundary","removed":{"cache":3,"cache_rng":3}}\n')
        f.write('{"kind":"summary","removed":{"cache":3,"cache_rng":3}}\n')
    R.save(Path(str(guard)+".summary.json"),dict(removed=dict(cache=3,cache_rng=3),forbidden_reads=0,native_loop_returned=True))
    v=mechanisms(a)
    assert v["counts"]["birth"]==1 and v["counts"]["forgetting_FH"]==200
    assert v["counts"]["definition_removed"]==1 and v["counts"]["p10_removed_cache"]==3
    assert v["coverage"]["p10_discard"]=="実発生を確認"
    (out/f"side/{CELL}/seed001.jsonl").write_text('')
    assert mechanisms(a)["coverage"]["birth"]=="関門では未検証"
    r=R.read(a/"runtime.json");r["flags"]+=["--no-forget-exec"];(a/"runtime.json").write_text(json.dumps(r))
    with pytest.raises(AssertionError):mechanisms(a)

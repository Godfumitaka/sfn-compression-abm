"""指示11の全5000用観察入口。試行を切らず、模型の入口を変更し続けない。"""
import os, sys
from pathlib import Path

if __name__ in ("__main__","__mp_main__"):
    if __name__=="__main__":os.environ["VERB_PRODUCTION_SOURCE"]=sys.argv[1]
    source=Path(os.environ["VERB_PRODUCTION_SOURCE"]).resolve()
    sys.path[:0]=[str(Path(__file__).resolve().parent.parent),str(source/"tools"),str(source)]
    import sweep, v3_run
    from checkpoint_observer import observe
    from timing100_observer import observe_timing
    original_worker=v3_run.worker
    original_longitudinal=sweep.run_longitudinal
    sweep.code_commit=lambda:"4dc6a05d88ba10dbc22fd14ec77ec5c720e1c9a2"
    def worker(task):
        assert task["cfg"]["trial_count"]==5000 and task["cfg"]["agent_ids"]==["agent"]
        assert task["seed"] in (*range(1,11),*range(41,49))
        def longitudinal(world,*args,**kw):
            assert len(world.trials)==5000
            ledger=kw["ledger"] if "ledger" in kw else args[2]
            with observe(Path(task["out_root"]), ledger, attention_enabled=bool(task.get("attn_sme")),
                         stage2_enabled=task.get("stage2") == "on"), observe_timing(Path(task["out_root"]), ledger):
                return original_longitudinal(world,*args,**kw)
        sweep.run_longitudinal=longitudinal
        try:return original_worker(task)
        finally:sweep.run_longitudinal=original_longitudinal
    v3_run.worker=worker
    if __name__=="__main__":
        sys.argv=[str(source/"tools/v3_run.py"),*sys.argv[2:]]
        v3_run.main()

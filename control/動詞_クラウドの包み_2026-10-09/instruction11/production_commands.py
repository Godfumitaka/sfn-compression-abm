"""指示11の命令草稿を出力するだけ。未記入のλ・列・関門を補わず、走行しない。"""
from pathlib import Path
import argparse,json,shlex
from cloud_run import read,save,digest

def emit(destination):
    destination=Path(destination);destination.mkdir(exist_ok=False)
    plan=read(Path(__file__).with_name("production_templates.json"))
    assert plan["lambda_value"] is None and plan["source_commit"] is None
    for arm,spec in plan["arms"].items():
        seeds=spec["seeds"]+spec.get("after_M1_seeds",[])
        for seed in seeds:
            flags=list(spec["flags"])
            flags[flags.index("--seeds")+1]=str(seed)
            # 空欄は明示的な環境変数。未設定で実行する台本ではない。
            args=[]
            for value in flags:
                args.append('"$VERB_SHOP_L50_REF"' if value=="{{SHOP_L50_REF}}" else shlex.quote(value))
            entry=('"$VERB_TOOLS/'+spec["observer"]+'" "$VERB_PROD_SOURCE"'
                   if spec["observer"] else '"$VERB_PROD_SOURCE/tools/v3_run.py"')
            label=arm.removeprefix("#")+f"_seed{seed:03d}"
            command=('"$VERB_PY" "$VERB_JOBS" run --owner verb-production-'+label+' --wait --mem "$VERB_PROD_MEM" '
                     '--disk-path "$VERB_PROD_OUT" -- "$VERB_PY" '+entry+
                     ' "$VERB_PROD_SOURCE/config/sweep_verb_hide1_s1_2026-10-04.json" '
                     '"$VERB_PROD_OUT" '+' '.join(args))
            save(destination/(label+".json"),dict(arm=arm,seed=seed,flags=flags,
                 source_commit=None,lambda_value=None,ready_to_start=False,
                 claude_M1_required=seed in range(3,11),
                 command_draft=command,resource_monitor_required=True,
                 queue_claim_and_normal_push_required=True,
                 production_gates_required=plan["required_speed_gates"] if spec["speed_applicable"] else [],
                 dependency=spec.get("requires"),speed_applicable=spec["speed_applicable"],
                 template_sha256=digest(Path(__file__).with_name("production_templates.json"))))
    save(destination/"status.json",dict(starts_model=False,lambda_value=None,
         source_commit=None,seeds3_to10_prepared_but_not_claimed=True,
         initial_production_seeds=[1,2],required_confirmation="ClaudeのM1と列・版・全旗・出力先",
         commands_are_drafts=True))
    return destination

if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("destination",type=Path)
    a=p.parse_args();emit(a.destination)

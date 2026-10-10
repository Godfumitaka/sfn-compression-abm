"""指示20：集団試験のD不変、八個体の実過程・記録の分離、直列拒否。"""
from pathlib import Path
from types import SimpleNamespace as NS
import ast
import json
import os
import subprocess
import sys
import pytest
import abm.loop as loop
import useforget as D
import useforget_cstar as N
import useforget_evaluation as E
import v311c as C
from test_useforget_instruction9 import case
from test_useforget_instruction13 import installed


@pytest.mark.parametrize('installed', ['legacy', 'q', 'q_attention'], indirect=True)
def test_native_collective_probe_does_not_enter_D(installed, monkeypatch):
    state, scene, config, res, output, root, mode = installed
    monkeypatch.setattr(C, 'CFG', dict(inner_predict=loop.predict, run=1))
    monkeypatch.setattr(C, 'CTX', {})
    monkeypatch.setattr(C, 'probe', C.probe)
    monkeypatch.setattr(C, '_check_dictionary_guard', lambda *args: None)
    E.install(root/'collective_checks.json')
    before = N.probe_snapshot()
    answers = C.probe(state, [{'scene':scene}], config)
    assert answers == [[output.prediction.edge.predicate, list(output.prediction.edge.arguments)]]
    assert N.probe_snapshot() == before and not E.active()
    assert E.CHECKS[-1]['call'] == 'v311c.probe' and E.CHECKS[-1]['unchanged']
    assert D.ST['stats']['uses'] == 0 and not D.ST['S']
    loop._agent_input(NS(trial=2),state)
    loop.predict(scene,state,config,None)
    assert D.ST['stats']['uses'] == 1


def test_eight_real_processes_have_disjoint_D_and_audit_files(tmp_path):
    # 模型は走らせない。八個体を別のPython過程で順に作り、親の控えへ戻らないことも点検。
    before = N.probe_snapshot()
    native = """
import json,os,sys
from pathlib import Path
import useforget as D
import useforget_cstar as N
import v39
root=Path(sys.argv[1]);agent=int(sys.argv[2]);run=1;seed=run+1000*agent
assert not D.ST and not N.AUDIT
v39.CFG.update(decay=(.5,)*16,u_abstain=False)
v39.run_conversions=lambda state,trial:(state,())
side=root/'side'/'cell';ret=root/'retention'/'cell';side.mkdir(parents=True,exist_ok=True);ret.mkdir(parents=True,exist_ok=True)
D.install(side/f'seed{seed:03d}.useforget.jsonl',tau=.4,horizon=20)
N.install(ret/f'seed{seed:03d}.jsonl',expected_usage=True,attention_usage=True)
key=('same_definition',0,0);N.use_amount(key,1,agent+1.)
N.AUDIT['f'].write(json.dumps({'agent':agent,'pid':os.getpid(),'amount':D.ST['S'][key][1][0]})+'\n')
D.ST['f'].write(json.dumps({'agent':agent,'pid':os.getpid(),'amount':D.ST['S'][key][1][0]})+'\n')
N.close();D.close()
print(json.dumps({'agent':agent,'pid':os.getpid(),'strength':agent+1.,'side':str(side/f'seed{seed:03d}.useforget.jsonl'),'retention':str(ret/f'seed{seed:03d}.jsonl')}))
"""
    records=[]
    for agent in range(8):
        value=subprocess.check_output([sys.executable,'-c',native,str(tmp_path),str(agent)],text=True)
        records.append(json.loads(value))
        assert N.probe_snapshot() == before
    assert len({r['pid'] for r in records}) == 8
    for field in ['side','retention']:
        assert len({r[field] for r in records}) == 8
        for r in records:
            data=[json.loads(line) for line in Path(r[field]).read_text().splitlines()]
            assert data==[{'agent':r['agent'],'pid':r['pid'],'amount':r['strength']}]
    (tmp_path/'eight_process_records.json').write_text(json.dumps(records,indent=2)+'\n')


@pytest.mark.parametrize('q,attention',[(False,False),(True,False),(True,True)])
def test_D_and_serial_are_rejected_before_model_start(tmp_path,q,attention):
    source=Path(__file__).resolve().parents[1]
    # パーサ検査に必要な正式設定を下のAST検査へ渡し、模型や世界を作る前の同じ検査だけを実行する。
    tree=ast.parse((source/'tools/v3_run.py').read_text())
    main=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='main')
    check=next(n for n in ast.walk(main) if isinstance(n,ast.If) and 'Dと集団化の直列' in ast.unparse(n))
    if not isinstance(check.test,ast.BoolOp) or 'args.use_forget' not in ast.unparse(check.test):
        check=next(n for n in main.body if isinstance(n,ast.If) and 'args.v311c_serial' in ast.unparse(n.test))
    args=NS(use_forget=.4,v311c_serial=True,use_forget_q=q,use_forget_attn=attention)
    with pytest.raises(SystemExit,match='Dと集団化の直列'):
        exec(compile(ast.Module(body=[check],type_ignores=[]),'<parser-check>','exec'),{'args':args})
    args.use_forget=None
    exec(compile(ast.Module(body=[check],type_ignores=[]),'<parser-check>','exec'),{'args':args})
    assert not list(tmp_path.rglob('*.jsonl.gz'))

"""機械の上限停止後の運用。今回の独立した関門走行も並列1にする。模型は不変。"""
from pathlib import Path
import json, sys

root = Path(__file__).resolve().parent
sys.path.insert(0, str(root/'source/tools/v311c_checks'))
import coll8_gate as gate


def sequential(function, values):
    for value in values:
        function(value)


gate.parallel = sequential
if gate.RESULT['status'] != 'stopped' or gate.RESULT.get('reason') != '機械の並列上限：SME等を優先して今回の処理を停止':
    raise RuntimeError('機械の上限停止以外からはこの入口で再開しない')
gate.save(gate.EV/'gates-machine-limit-stop.json',gate.RESULT)
archive = gate.OUT/'interrupted-machine-limit-20261003_202256'
archive.mkdir(exist_ok=False)
preserved=[]
for name in ('solo_r1_a2','solo_r1_a3'):
    for path in (gate.OUT/name, gate.OUT/(name+'.stdout.log'), gate.OUT/(name+'.time.log')):
        target=archive/path.name
        path.rename(target)
        preserved.append({'original':str(path),'preserved':str(target)})
gate.save(gate.EV/'interrupted-machine-limit-preserved.json',preserved)
gate.RESULT['status']='running'
gate.RESULT['machine_interruption']={
    'record':'gates-machine-limit-stop.json', 'remaining_independent_parallelism':1,
    'preserved':'interrupted-machine-limit-preserved.json'}
gate.RESULT.pop('traceback',None)
gate.RESULT.pop('reason',None)
gate.RESULT.pop('finished',None)
gate.checkpoint()
try:
    gate.main()
except BaseException as error:
    import traceback
    gate.RESULT.update(status='stopped',finished=gate.now(),reason=str(error),traceback=traceback.format_exc())
    gate.checkpoint()
    print(gate.RESULT['traceback'],flush=True)
    raise

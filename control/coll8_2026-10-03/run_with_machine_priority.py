"""機械の上限だけによる中断は保存して空きを待つ。配管不成立・熱警告は再開しない。"""
from pathlib import Path
import json, sys, time, traceback

root=Path(__file__).resolve().parent
sys.path.insert(0,str(root/'source/tools/v311c_checks'))
import coll8_gate as gate


def sequential(function,values):
    for value in values:function(value)


gate.parallel=sequential
machine_reason='機械の並列上限：SME等を優先して今回の処理を停止'
while True:
    if gate.RESULT['status']=='stopped':
        if gate.RESULT.get('reason')!=machine_reason:
            raise RuntimeError('配管不成立・熱警告等の停止からは再開しない')
        stamp=gate.RESULT['finished'].replace('-','').replace(':','').replace('+0900','')
        record='gates-machine-stop-'+stamp+'.json'
        gate.save(gate.EV/record,gate.RESULT)
        archive=gate.OUT/('interrupted-machine-'+stamp)
        archive.mkdir(exist_ok=False)
        names={json.loads(line)['name'] for line in (gate.EV/'jobs.jsonl').read_text().splitlines()}
        saved=[]
        for name in sorted(names):
            if (gate.EV/(name+'.resource.json')).exists():continue
            for path in (gate.OUT/name,gate.OUT/(name+'.stdout.log'),gate.OUT/(name+'.time.log')):
                if path.exists():
                    target=archive/path.name;path.rename(target)
                    saved.append({'original':str(path),'preserved':str(target)})
            a=gate.EV/(name+'.argv.json')
            if a.exists():(archive/a.name).write_bytes(a.read_bytes())
        gate.save(archive/'preserved.json',saved)
        gate.RESULT.setdefault('machine_stop_history',[]).append({'record':record,'archive':str(archive)})
        gate.HALT.clear()
        for key in ('reason','traceback','finished'):gate.RESULT.pop(key,None)
        gate.RESULT['status']='waiting_for_machine'
        gate.checkpoint()
    while True:
        try:h,_=gate.health()
        except BaseException as error:
            gate.RESULT.update(status='stopped',finished=gate.now(),reason=str(error))
            gate.checkpoint();raise
        # 今回は1本のみ。さらに他の処理の起動に1枠の余裕を残す。
        if len(h['foreign_heavy'])<=2:break
        print('他の重い処理の空きを待つ',len(h['foreign_heavy']),flush=True)
        time.sleep(30)
    gate.RESULT['status']='running';gate.checkpoint()
    try:
        gate.main()
        break
    except BaseException as error:
        gate.RESULT.update(status='stopped',finished=gate.now(),reason=str(error),traceback=traceback.format_exc())
        gate.checkpoint()
        print(gate.RESULT['traceback'],flush=True)
        if str(error)!=machine_reason:raise

"""クラウドの小例の受付と証拠。Macの準備検査を実関門に読み替えない。"""
import argparse
from datetime import datetime,timezone
import os
from pathlib import Path
import subprocess
import sys
from run import C,DEADLINE,host,now,save

TESTS=['tests/test_v311c_allin.py','tools/v311c_checks/test_sme_port.py',
    'tools/test_cstar_runtime.py','tools/test_cstar_fixed.py',
    'tests/test_attnstage2_questions.py','tests/test_attnstage2_runtime.py',
    'tests/test_attncstar.py','tests/test_attnstage2_birth.py',
    'tests/test_attnstage2_birth_hu.py','tests/test_attnstage2_initial.py',
    'tests/test_attnallin.py']
HERE=Path(__file__).resolve().parent

def main():
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['run','registered'])
    p.add_argument('--source',type=Path,required=True);p.add_argument('--root',type=Path,required=True)
    p.add_argument('--jobs',type=Path);a=p.parse_args()
    assert sys.platform.startswith('linux') and sys.version_info[:2]==(3,12)
    assert datetime.now(timezone.utc)<DEADLINE
    assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=a.source,text=True).strip()==C
    assert not subprocess.check_output(['git','status','--porcelain'],cwd=a.source)
    output=a.root.resolve()/'component-evidence';gate=a.root.resolve()/'gates/gate-components.json'
    assert not gate.exists() and not (a.root/'STOP.json').exists()
    if a.mode=='run':
        assert not output.exists();output.mkdir(parents=True,exist_ok=False)
        command=[sys.executable,str(a.jobs),'run','--wait','--owner','Codex3 N7 小例','--mem','1',
          '--disk-path',str(output),'--',sys.executable,str(HERE/'components.py'),'registered',
          '--source',str(a.source.resolve()),'--root',str(a.root.resolve())]
        save(output/'admission-command.json',dict(command=command,time=now()))
        return subprocess.call(command)
    env={**os.environ,'PYTHONPATH':os.pathsep.join([str(a.source/'tools'),str(a.source),str(HERE)]),
       'PYTHONDONTWRITEBYTECODE':'1','PYTEST_DISABLE_PLUGIN_AUTOLOAD':'1','PYTHONHASHSEED':'0'}
    assert not (output/'pytest-temp').exists(),'検査の一時場所も保全し、消して使い直さない'
    command=[sys.executable,'-m','pytest','-q','-p','no:cacheprovider',*TESTS,str(HERE/'test_stops.py'),
             '--basetemp',str(output/'pytest-temp')]
    with (output/'stdout.log').open('x') as f:
        result=subprocess.run(['/usr/bin/time','-v','-o',str(output/'time.log'),*command],
          cwd=a.source,env=env,stdout=f,stderr=subprocess.STDOUT)
    gate.parent.mkdir(exist_ok=True)
    save(gate,dict(passed=result.returncode==0,candidate=C,host=host(),time=now(),command=command,
        test_files=TESTS+['test_stops.py'],exitcode=result.returncode,
        coverage=['入れ子・pending同一性・乱数・診断の隔離','公開材料・source世界/報告・二材料の誕生HU',
        '実課題の回数・実開示名集合を診断/受信で増やさない','C*確率枠・同点・共有の鍵',
        '墓石の再参照停止・未知名停止・再生不一致停止']))
    if result.returncode:
        save(a.root/'STOP.json',dict(reason='小例の失敗',gate=str(gate)))
    return result.returncode

if __name__=='__main__':sys.exit(main() or 0)

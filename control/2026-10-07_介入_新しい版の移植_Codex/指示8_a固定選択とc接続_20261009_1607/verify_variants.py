"""診断部品の合成小例だけを通常受付で検査し、元の資料を保全する。"""
from pathlib import Path
import datetime
import hashlib
import json
import os
import subprocess
import sys
import time
import xml.etree.ElementTree as ET

PORT = Path(__file__).resolve().parents[1]
SOURCE = PORT/'source_e9'
GATE = PORT/'instruction5/gate_200_01'
DEST = PORT/'instruction8'/sys.argv[1]
DEST.mkdir(exist_ok=False)


def save(name, value):
    (DEST/name).write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n')


def hashes(root):
    result = {}
    for path in root.rglob('*'):
        if path.is_file():
            h = hashlib.sha256()
            with path.open('rb') as stream:
                for block in iter(lambda:stream.read(1048576), b''):
                    h.update(block)
            result[str(path.relative_to(root))] = h.hexdigest()
    return result


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


protected = ['abm/loop.py', 'abm/agent_runtime.py', 'abm/abstraction.py', 'tools/v39.py',
    'tools/v310be.py', 'tools/attnstage2_runtime.py', 'tools/attnstage2_initial.py',
    'tools/attncstar.py', 'tools/intervention46_records.py', 'tools/intervention46_record_run.py',
    'tools/intervention46_record_gate.py', 'tools/intervention46_off_gate.py',
    'tools/intervention46_native.py', 'tools/test_intervention46_native.py',
    'tools/attnsme.py', 'tools/attnsme_features.py', 'tools/attnstage2_sme.py',
    'tools/attnstage2_questions.py', 'tools/smeshared.py', 'tools/cstar_runtime.py']
protected_before = {name:sha(SOURCE/name) for name in protected}
for name, value in protected_before.items():
    old = subprocess.check_output(['git','show','9411a26b580e3511f6cd273f7af271376fb0251e:'+name],cwd=SOURCE)
    assert hashlib.sha256(old).hexdigest()==value, ('旧入口又は本体の変更',name)
gate_before = hashes(GATE)
save('protected_before.json', protected_before)
save('input_before.json', gate_before)
test = SOURCE/'tools/test_intervention46_variants_instruction8.py'
files = [SOURCE/'tools/intervention46_variants_instruction8.py', test, Path(__file__)]
old_candidate = {'tools/intervention46_variants.py':'879aa77651bb828c8149531eeee864c02f16d17de4ed65f827c177ae9ad63d95',
    'tools/test_intervention46_variants.py':'7dc9f1e2317218515c6ffe9036e0fe0139089b547cf3662a288bca69db645f5a'}
assert {name:sha(SOURCE/name) for name in old_candidate} == old_candidate
old_stop = hashes(PORT/'instruction3/variants_tests_01')
old_stop['variants_stop_status.json'] = sha(PORT/'instruction3/variants_stop_status.json')
save('old_stop_before.json', old_stop)
save('old_candidate_before.json', old_candidate)
# cの誕生・初期化・予測のコードは旧候補と全バイト同じ。
old_c = (SOURCE/'tools/intervention46_variants.py').read_text().split('def add_past(',1)[1]
new_c = (files[0]).read_text().split('def add_past(',1)[1]
assert old_c == new_c
source_before = {str(path):sha(path) for path in files}
for path in files:
    (DEST/(path.name+'.txt')).write_bytes(path.read_bytes())
env = dict(os.environ, PYTHONPATH=os.pathsep.join(map(str, (SOURCE/'tools',SOURCE/'tests',SOURCE,
    PORT/'instruction3/test_dependencies_01'))), PYTHONDONTWRITEBYTECODE='1',
    PYTEST_DISABLE_PLUGIN_AUTOLOAD='1', INTERVENTION46_INSTRUCTION8_EVIDENCE=str(DEST))
command = [sys.executable,'-m','pytest','-q',str(test),'--junitxml='+str(DEST/'pytest.xml')]
save('command.json',command)
status = dict(status='running', model_run_called=False, formal_3b_material=False,
              actual_record_interventions=False, iii_b_called=False,
              iii_c_code_bytes_unchanged=True, pid=os.getpid())
save('status.json',status)
start = time.perf_counter()
try:
    process = subprocess.run(command,cwd=SOURCE,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
    (DEST/'pytest.log').write_text(process.stdout)
    print(process.stdout,end='')
    status['exit_code'] = process.returncode
    assert process.returncode==0, '構造pytestの停止'
    suites = ET.parse(DEST/'pytest.xml').getroot()
    status['tests'] = sum(int(s.attrib.get('tests',0)) for s in suites)
    status['status'] = 'passed'
except BaseException as error:
    status.update(status='stopped',error=repr(error))
    raise
finally:
    after = hashes(GATE)
    protected_after = {name:sha(SOURCE/name) for name in protected}
    source_after = {str(path):sha(path) for path in files}
    candidate_after = {name:sha(SOURCE/name) for name in old_candidate}
    stop_after = hashes(PORT/'instruction3/variants_tests_01')
    stop_after['variants_stop_status.json'] = sha(PORT/'instruction3/variants_stop_status.json')
    save('old_stop_after.json',stop_after)
    save('old_candidate_after.json',candidate_after)
    save('input_after.json',after)
    save('protected_after.json',protected_after)
    status.update(seconds=time.perf_counter()-start,
        verified_at_jst=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).isoformat(timespec='seconds'),
        input_files=len(gate_before),inputs_unchanged=gate_before==after,
        protected_files=len(protected_before),protected_unchanged=protected_before==protected_after,
        source_before=source_before,source_after=source_after,source_unchanged=source_before==source_after,
        old_candidates_unchanged=candidate_after==old_candidate,
        old_stop_unchanged=stop_after==old_stop,
        peak_children_rss_bytes=__import__('resource').getrusage(__import__('resource').RUSAGE_CHILDREN).ru_maxrss)
    save('status.json',status)
    assert (gate_before==after and protected_before==protected_after and source_before==source_after
            and candidate_after==old_candidate and stop_after==old_stop), '元の資料が変わった'

"""完了した13本と全走行を重複実行せず、承認後の残りだけ進める。"""
from pathlib import Path
from datetime import datetime
import json
import pipeline as p
root=p.HERE
state={'started':datetime.now().astimezone().isoformat(),'previous':json.loads((root/'pipeline_result.json').read_text()),'completed':[]}
assert 'full_1740_exact' in state['previous']['completed']
assert json.loads((root/'proof_full_01/comparison.json').read_text())['all_bytes_equal']
try:
    folder=root/'profile_200_01'
    p.run(json.loads((folder/'command.json').read_text()),folder,model=True,profile=True)
    state['completed'].append('profile_200')
    p.run([p.PYTHON,str(root/'collective_counts.py'),str(root/'collective_counts_registered.json')],root/'collective_counts_01')
    state['completed'].append('collective_existing_records')
    state['passed']=True
except Exception as error:
    state['passed']=False;state['error']=str(error);raise
finally:
    state['ended']=datetime.now().astimezone().isoformat()
    (root/'continuation_result_01.json').write_text(json.dumps(state,ensure_ascii=False,indent=2)+'\n')

"""一本の走行又は保存状態の再解析・集計。模型のコードは変更しない。"""
from pathlib import Path
from datetime import datetime
import hashlib,json,subprocess,sys
ROOT=Path(__file__).resolve().parent
folder=Path(sys.argv[1]).resolve();mode=sys.argv[2]
if mode=='native':
    subprocess.run([sys.executable,str(ROOT/'run_case_01.py'),str(folder)],check=True)
else:
    assert mode=='analysis' and (folder/'run_complete.json').exists()
    spec=json.loads((folder/'analysis_spec.json').read_text());source=json.loads((folder/'run_spec.json').read_text())['source']
    if not (folder/'reused_record.json').exists():
        out=Path(spec['original_output']);states=next(out.glob('side/**/*.sme.states.jsonl.gz'))
        adir=folder/'analysis_job';adir.mkdir(exist_ok=False)
        cmd=[sys.executable,'tools/selcands_sme.py',str(folder/'command.json'),spec['analysis_output'],str(states)]
        (adir/'command.json').write_text(json.dumps(cmd,indent=2)+'\n')
        a={'source':source,'commit':json.loads((folder/'run_spec.json').read_text())['commit'],'output':spec['analysis_output'],'validation_command':str(folder/'command.json')}
        (adir/'run_spec.json').write_text(json.dumps(a,indent=2)+'\n')
        subprocess.run([sys.executable,str(ROOT/'run_case_01.py'),str(adir)],check=True)
    subprocess.run([sys.executable,str(ROOT/'summarize_01.py'),str(folder)],check=True)
    # 本人の記録とは別の管理ファイルも、完了時の値を残す。更新中のclaim.logを末尾まで含めた表は条件終了時に作る。
    (folder/'case_complete.json').write_text(json.dumps({'passed':True,'at':datetime.now().astimezone().isoformat(),'commit':json.loads((folder/'run_spec.json').read_text())['commit'],'seed':json.loads((folder/'summary.json').read_text())['seed']},indent=2)+'\n')

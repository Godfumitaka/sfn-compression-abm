"""受付内の比較。全長の模型を走らせ直さない。"""
from pathlib import Path
import json,sys
ROOT=Path(__file__).resolve().parent
WORK=ROOT/'native_full_01'
PAR=ROOT/'parallel_instruction7_01'
sys.path.insert(0,str(ROOT.parent/'codex_logp_main_2026-10-06'))
from common_01 import now, save
from compare_gate_01 import compare
cases=['base_A','off_A','base_L','off_L','on_own','on_keep']
try:
    for name in cases: assert json.loads((WORK/(name+'.json')).read_text())['exit']==0
    for name in ['off_A','off_L']: assert json.loads((WORK/(name+'_comparison.json')).read_text())['passed']
    assert not (WORK/'material_same_flags_comparison.json').exists(), '比較の重複起動'
    compare(WORK/'on_own/output',WORK/'on_keep/output',WORK/'material_same_flags_comparison.json')
    save(WORK/'complete.json',{'at':now(),'passed':True,'completed':cases,'execution':'指示7で未着手のC*二本を個別に受付へ分割','administrative_serial_stop':str(WORK/'STOP.json')})
    print(json.dumps({'at':now(),'passed':True,'completed':cases},ensure_ascii=False),flush=True)
except Exception as e:
    save(PAR/'STOP_comparison.json',{'at':now(),'reason':str(e),'passed':False})
    if not (PAR/'STOP.json').exists():save(PAR/'STOP.json',{'at':now(),'reason':str(e)})
    raise

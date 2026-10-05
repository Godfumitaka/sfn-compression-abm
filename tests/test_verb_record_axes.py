"""台帳からの席の復元だけを検査し、模型の誤答方向は検査しない。"""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools/verb'))
from record_axes import seat_record, selected_record


def test_raw_seat_states_and_tie():
    d={'name':'R'}
    r={'slot_index':2,'alive':True,'relation':{'predicate':'P'}}
    assert seat_record(d,r,{})['state']=='F'
    assert seat_record(d,r,{})['stored_answer']=='P'
    r['alive']=False
    assert seat_record(d,r,{})['state']=='U'
    assert seat_record(d,r,{str(('R',2)):{}})['state']=='H'
    h={str(('R',2)):{'P':2,'Q':2}}
    rec=seat_record(d,r,h)
    assert rec['state']=='H' and rec['stored_answer'] is None
    h[str(('R',2))]['P']=3
    assert seat_record(d,r,h)['stored_answer']=='P'


def test_selected_definition_from_record_not_prediction():
    probe={'R':'R@0','R_used':True,'t':100,'verb_name':'V41','answer':'IRR_1','source':'H_fill'}
    row={'slot_index':1,'alive':False,'relation':{'relation_id':'name','predicate':'gone'}}
    state={'definitions':{'R':{'name':'R','registered_at':0,'constituents':[row]}},'slot_history':{}}
    rec=selected_record(probe,state,{'name'},{'past'})
    assert rec['selected_name_states']==['U']
    assert rec['past_seats']==[]

"""指定した8条件だけ、同じ固定候補と開示順で比較すること。"""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from attnposition_run import CONDITIONS,candidate
import attnposition as P

def test_exact_eight_preregistered_conditions():
 assert len(CONDITIONS)==len({c['id'] for c in CONDITIONS})==8
 assert [(c['mode'],c['eta'],c['fixed_a']) for c in CONDITIONS]==[
  ('binary',.1,None),('binary',.5,None),('global',.1,None),('global',.5,None),('position',.1,None),('position',.5,None),('global',None,1.),('position',None,1.)]

def test_fixed_answers_and_no_candidate_recalculation():
 row={'R':'example','q_numerator':3,'q_denominator':4,'n':5,'registered_at':1,'m':{'binary':{'key':1.}},'answer':['given',['a','b']],'payload':{'prediction_kind':'EdgePrediction','predicted_edge':{'predicate':'given','arguments':['a','b']}}}
 c=candidate(row,'binary');learner=P.Learner(.5)
 prepared=learner.prepare(0,True,{},[c])
 result=learner.finish(prepared,{'prediction_order':0,'f_fired':True,'f_realized':.5,'feedback_content':{'predicate':'different','arguments':['a','b']}})
 assert result['answer_before_update']==row['payload'] and result['reason']=='no_correct_candidates'
 assert c.answer==('given',('a','b'))

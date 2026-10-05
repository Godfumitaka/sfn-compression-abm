"""確定した回答の外れ・黙りを分け、三つの既存シール分類を保持する。"""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from attnposition_summary import outcome,seal_class,saved_outcome_name

def test_correct_requires_name_and_arguments_quiet_is_separate():
 truth=['e',['a','b']]
 assert outcome({'predicted_edge':None},truth)=='abstain'
 assert outcome({'predicted_edge':{'predicate':'e','arguments':['a','b']}},truth)=='correct'
 assert outcome({'predicted_edge':{'predicate':'e','arguments':['a','x']}},truth)=='wrong'
 assert outcome({'predicted_edge':{'predicate':'n','arguments':['a','b']}},truth)=='wrong'

def test_keeps_original_three_seal_classes():
 assert seal_class({'state':'U'})=='U'
 for name in ('sig_n','sig_e'):
  assert seal_class({'state':'H','seats':[{'names':[name]}]})=='H['+name+']'


def test_saved_silent_is_same_abstention_without_score_change():
 assert saved_outcome_name('silent')=='abstain'
 for name in ('correct','wrong'):assert saved_outcome_name(name)==name

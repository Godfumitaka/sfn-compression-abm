"""実際の開示だけで仮の問いを分け、反実仮想で頻度を変えない。"""
from pathlib import Path
from types import SimpleNamespace
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import pytest
from attnstage2_questions import Questions, Snapshot


def test_current_disclosure_is_not_used_to_classify_its_own_birth():
    q=Questions()
    pre=q.present(True)
    rows,_=pre.virtual_weights(['hold','sig_e'])
    assert [r['class'] for r in rows]==['other','other']
    assert [r['weight'] for r in rows]==[0,0]
    q.finish(pre,fired=True,feedback=SimpleNamespace(predicate='hold'))
    following=q.present(False)
    rows,_=following.virtual_weights(['hold','sig_e'])
    assert rows==({'class':'door','weight':.5},{'class':'other','weight':.5})


def test_non_disclosed_names_never_read_or_enter_disclosed_set():
    class Hidden:
        @property
        def predicate(self):raise AssertionError('未開示の正解を読んだ')
    q=Questions()
    pre=q.present(True)
    q.finish(pre,fired=False,feedback=Hidden())
    assert q.record()=={'door':1,'other':0,'door_names':[],'other_names':[]}


def test_frequency_is_shared_within_kind_not_between_missing_kinds():
    pre=Snapshot(3,1,frozenset({'hold'}),frozenset(),True)
    rows,stats=pre.virtual_weights(['hold','hold','sig_n'])
    assert [r['weight'] for r in rows]==[.375,.375,.25]
    rows,stats=pre.virtual_weights(['sig_n','attach'])
    assert [r['weight'] for r in rows]==[.125,.125]
    assert stats['unassigned_mass']==.75


def test_no_real_question_record_uses_uniform_weights():
    pre=Snapshot(0,0,frozenset(),frozenset(),False)
    rows,stats=pre.virtual_weights(['a','b','c'])
    assert [r['weight'] for r in rows]==[1/3]*3
    assert stats['unassigned_mass']==0


def test_no_visible_virtual_questions_does_not_reassign_mass():
    rows,stats=Snapshot(3,1,frozenset(),frozenset(),True).virtual_weights([])
    assert rows==() and stats['unassigned_mass']==1


def test_overlap_uses_disclosed_door_condition_and_is_recorded():
    pre=Snapshot(1,1,frozenset({'both'}),frozenset({'both'}),False)
    rows,stats=pre.virtual_weights(['both','different'])
    assert rows[0]['class']=='door' and stats['overlap']==1


def test_virtual_questions_do_not_change_frequency_or_names():
    q=Questions();pre=q.present(False);saved=q.record()
    for _ in range(5):pre.virtual_weights(['a','b'])
    assert q.record()==saved and q.pending is pre
    with pytest.raises(ValueError):q.present(True)


def test_names_can_be_renamed_without_changing_class_weights():
    left=Snapshot(4,2,frozenset({'x'}),frozenset({'y'}),True)
    right=Snapshot(4,2,frozenset({'renamed'}),frozenset({'other'}),True)
    assert left.virtual_weights(['x','y'])==right.virtual_weights(['renamed','other'])

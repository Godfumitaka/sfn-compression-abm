"""受入③〜⑧の共通小例を8体・二集団の設定でも検査する。"""
import pytest
import test_v311c as C
import v311c

@pytest.mark.parametrize('name', [
    'test_03_silent_no_bundle_and_single_prediction',
    'test_04_bundle_fixed_and_no_truth_to_receiver',
    'test_05_reference_resolution',
    'test_06_receive_B_candidates',
    'test_07_tags_counts_sampling_init',
    'test_08_tag_cost_changes'])
def test_eight_agent_structure(monkeypatch,name):
    original=C.setup
    def setup8():
        original()
        v311c.CFG.update(n=8,groups=[0,0,0,0,1,1,1,1],b=14)
    monkeypatch.setattr(C,'setup',setup8)
    getattr(C,name)()

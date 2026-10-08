"""20の観察が最終追記を一度だけ呼び、書出しの回数だけ数える検査。"""
from pathlib import Path
from types import SimpleNamespace
import importlib.util, copy, io, json, random, sys
sys.path[:0]=[str(Path(__file__).parent/'source/tools'),str(Path(__file__).parent/'source')]
import smeshared as S
spec=importlib.util.spec_from_file_location('observer20',Path(__file__).with_name('measurement_driver.py'))
O=importlib.util.module_from_spec(spec);spec.loader.exec_module(O)
def test_prefix20_keeps_configured_length_and_order():
    p=O.PrefixTrials(list(range(5000)),20)
    assert len(p)==5000 and list(p)==list(range(20))
def test_final_append_is_called_once_and_restored():
    calls=[];seen=[];native=calls.append;ledger=SimpleNamespace(append=native)
    with O.observe_written_rows(ledger,seen.append):
        for x in range(20):ledger.append(x)
    assert calls==seen==list(range(20)) and ledger.append is native
def test_fallback_counts_outer_serialization_once_and_preserves_input_rng(monkeypatch):
    output=io.StringIO();monkeypatch.setattr(S,'LOG',{'f':output});monkeypatch.setattr(S,'_diagnosing',lambda:False)
    original=S._log_string_keys;record={'p':[{None:.25,'name':.75}]};before=copy.deepcopy(record);rng=random.getstate();stats=dict(S.STATS)
    with O.observe_log_fallbacks(S) as counts:
        S._log({'kind':'normal'})
        assert counts['fallback_calls']==0
        S._log(record)
        assert counts['fallback_calls']==1
    assert S._log_string_keys is original and record==before and random.getstate()==rng and S.STATS==stats
    assert json.loads(output.getvalue().splitlines()[1])=={'p':[{'null':.25,'name':.75}]}
def test_observer_restores_on_exception():
    original=S._log_string_keys
    try:
        with O.observe_log_fallbacks(S):raise ValueError('検査')
    except ValueError:pass
    assert S._log_string_keys is original

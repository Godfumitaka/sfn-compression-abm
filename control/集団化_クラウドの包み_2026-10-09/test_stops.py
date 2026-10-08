"""小例だけで、未知名と墓石の停止を検査する。世界の種は読まない。"""
import io
import gzip
from types import SimpleNamespace
import pytest

def test_unknown_name_stops_and_keeps_diagnostic(monkeypatch):
    import v311c as C
    import v39
    stream=io.StringIO()
    monkeypatch.setattr(C,'CFG',dict(run=1,agent=0))
    monkeypatch.setattr(C,'CTX',dict(fo=stream,dictionary_unknown_names={'辞書外の例'}))
    monkeypatch.setattr(v39,'STATS',dict(not_in_dictionary=1))
    with pytest.raises(C.NotInDictionary):C._check_dictionary_guard(0,'world')
    assert '辞書外の例' in stream.getvalue()

def test_tombstone_stops_without_recreating_entry(tmp_path):
    import smeevict
    shared=SimpleNamespace(CTX={'trial':1},_text_gzip=lambda path:gzip.open(path,'wt'))
    manager=smeevict.Manager(shared,tmp_path/'small.keys.jsonl.gz',True)
    key=('小例','call-seed-v1',1);manager.dead['cache'].add(key)
    try:
        with pytest.raises(RuntimeError):manager.lookup('cache',key)
        assert manager.tombstone_hits==1 and key in manager.dead['cache']
        assert (tmp_path/'small.keys.jsonl.gz.failure.json').exists()
    finally:manager.stream.close()

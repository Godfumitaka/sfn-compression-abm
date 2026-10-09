"""非模型検査：原行の字節と外側の出力・入口・状態/RNGを保つ。"""
from pathlib import Path
from types import ModuleType, SimpleNamespace
import ast, gzip, hashlib, importlib.util, json, random, sys, zlib
import pytest

ROOT = Path(__file__).resolve().parent
TOOLS = ROOT/'tools'
OLD = ROOT.parent/'instruction20_production/tools'
sys.path.insert(0, str(TOOLS))
from confirmed_hash import hash_confirmed, CHUNK_BYTES
from instruction11_io import copy_confirmed

def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

@pytest.mark.parametrize('kind', ['plain','gzip','gzip_open','gzip_members','empty','long_line'])
def test_hash_matches_old_confirmed_copy_without_materializing(kind, tmp_path):
    data = ('過去形\t世界\nもう一行\n'*300).encode()
    if kind == 'empty':
        data = b''
    if kind == 'long_line':
        data = b'x'*(CHUNK_BYTES*3+17)+b'\n'
    suffix = '.gz' if kind in ('gzip','gzip_open','gzip_members') else '.jsonl'
    path = tmp_path/('records'+suffix)
    if kind == 'gzip':
        raw = gzip.compress(data)
    elif kind == 'gzip_open':
        obj = zlib.compressobj(wbits=31)
        raw = obj.compress(data)+obj.flush(zlib.Z_SYNC_FLUSH)
    elif kind == 'gzip_members':
        cut = data.index(b'\n')+1
        raw = gzip.compress(data[:cut])+gzip.compress(data[cut:])
    else:
        raw = data
    path.write_bytes(raw)
    before = path.read_bytes()
    old = copy_confirmed(path, tmp_path/'old_copy')
    new = hash_confirmed(path)
    assert {key:new[key] for key in ('sha256','bytes')} == old
    assert new['lines'] == data.count(b'\n')
    assert new['sha256'] == hashlib.sha256(data).hexdigest()
    assert path.read_bytes() == before
    assert sorted(p.name for p in tmp_path.iterdir()) == sorted([path.name,'old_copy'])

@pytest.mark.parametrize('compressed', [False, True])
def test_incomplete_line_is_not_fabricated(compressed, tmp_path):
    path = tmp_path/('records.gz' if compressed else 'records.jsonl')
    data = b'complete\nincomplete'
    path.write_bytes(gzip.compress(data) if compressed else data)
    with pytest.raises(AssertionError, match='確定前'):
        hash_confirmed(path)

def test_only_checkpoint_record_copy_block_changes():
    for rel in ('instruction11_io.py','timing100_observer.py','production/measurement_driver.py'):
        assert (TOOLS/rel).read_bytes() == (OLD/rel).read_bytes()
    before = ast.parse((OLD/'checkpoint_observer.py').read_text())
    after = ast.parse((TOOLS/'checkpoint_observer.py').read_text())
    old_observe = next(n for n in before.body if isinstance(n,ast.FunctionDef) and n.name=='observe')
    new_observe = next(n for n in after.body if isinstance(n,ast.FunctionDef) and n.name=='observe')
    old_append = next(n for n in old_observe.body if isinstance(n,ast.FunctionDef) and n.name=='append')
    new_append = next(n for n in new_observe.body if isinstance(n,ast.FunctionDef) and n.name=='append')
    old_loop = next(n for n in ast.walk(old_append) if isinstance(n,ast.For))
    new_loop = next(n for n in ast.walk(new_append) if isinstance(n,ast.For))
    old_append.body = [ast.Pass()]
    new_append.body = [ast.Pass()]
    assert ast.dump(old_observe) == ast.dump(new_observe)
    # 差がある部分を一つの記録読み取りに置換すれば、appendの残りも同じ。
    before = ast.parse((OLD/'checkpoint_observer.py').read_text())
    after = ast.parse((TOOLS/'checkpoint_observer.py').read_text())
    old_loop = next(n for n in ast.walk(before) if isinstance(n,ast.For) and isinstance(n.target,ast.Name) and n.target.id=='rel')
    new_loop = next(n for n in ast.walk(after) if isinstance(n,ast.For) and isinstance(n.target,ast.Name) and n.target.id=='rel')
    old_loop.body = [ast.Pass()]
    new_loop.body = [ast.Pass()]
    before.body = [n for n in before.body if not isinstance(n,ast.ImportFrom)]
    after.body = [n for n in after.body if not isinstance(n,ast.ImportFrom)]
    assert ast.dump(before) == ast.dump(after)

def exercise_observer(module, out, monkeypatch):
    out.mkdir()
    calls = []
    rng = random.Random(19)
    abm = ModuleType('abm'); loop = ModuleType('abm.loop'); abm.loop = loop
    loop._agent_input = lambda trial,state: calls.append(('input',trial.trial)) or trial
    loop.predict = lambda ai,state,cfg,rng: calls.append(('predict',ai.trial)) or rng.random()
    def record(agent,trial,config,output,score,coin,state):
        calls.append(('record',trial.trial));state['t'] = trial.trial
        return None
    loop._ledger_record = record
    loop.m1 = lambda *args: None
    loop.apply_theta = lambda *args: None
    monkeypatch.setitem(sys.modules,'abm',abm)
    monkeypatch.setitem(sys.modules,'abm.loop',loop)
    def engine(seed):
        return SimpleNamespace(match_key=lambda key:key, cache={}, cache_rng={}, self_cache={}, rng=random.Random(seed))
    for name in ('smeshared','cstar_runtime'):
        mod = ModuleType(name);mod.ENGINE = engine(3)
        monkeypatch.setitem(sys.modules,name,mod)
    probe = ModuleType('probeworld')
    probe._snapshot_modules = lambda: calls.append(('save',)) or {'saved':True}
    probe._restore_modules = lambda snapshot:calls.append(('restore',))
    probe._probe = lambda: calls.append(('probe',))
    monkeypatch.setitem(sys.modules,'probeworld',probe)
    for name in ('attnstage2_runtime','attnsme'):
        mod = ModuleType(name);mod.ST = {}
        monkeypatch.setitem(sys.modules,name,mod)
    replay = ModuleType('smereplay');replay.encode = lambda value:value
    monkeypatch.setitem(sys.modules,'smereplay',replay)
    path = out/'ledgers/cells/cell/seed001.jsonl';path.parent.mkdir(parents=True)
    stream = path.open('wb')
    class Ledger:
        _stream = stream
        def append(self,row):
            calls.append(('append',row['prediction_order']))
            stream.write((json.dumps(row)+'\n').encode())
            return 'original-result'
    ledger = Ledger()
    originals = (loop._agent_input,loop.predict,loop._ledger_record,probe._snapshot_modules,probe._restore_modules,probe._probe)
    state = {}
    with module.observe(out,ledger,attention_enabled=False,stage2_enabled=False):
        for t in (499,500,999):
            trial = SimpleNamespace(trial=t)
            ai = loop._agent_input(trial,state)
            value = loop.predict(ai,state,None,rng)
            loop._ledger_record('agent',trial,None,value,None,None,state)
            assert ledger.append({'prediction_order':t,'value':value}) == 'original-result'
    stream.close()
    assert originals == (loop._agent_input,loop.predict,loop._ledger_record,probe._snapshot_modules,probe._restore_modules,probe._probe)
    assert 'append' not in vars(ledger)
    return calls, state, rng.getstate()

def test_external_outputs_and_checkpoint_state_rng_are_identical(tmp_path, monkeypatch):
    old = load(OLD/'checkpoint_observer.py','old_checkpoint_observer')
    new = load(TOOLS/'checkpoint_observer.py','new_checkpoint_observer')
    left,right = tmp_path/'left',tmp_path/'right'
    assert exercise_observer(old,left,monkeypatch) == exercise_observer(new,right,monkeypatch)
    def files(out):
        return {str(p.relative_to(out)):p.read_bytes() for p in out.rglob('*') if p.is_file() and 'comparison_checkpoints' not in p.parts}
    assert files(left) == files(right)
    for boundary in ('completed_0500','completed_1000'):
        a,b = (folder/'comparison_checkpoints'/boundary for folder in (left,right))
        for rel in ('state.json','rng.json','cache_raw.json','cache_posthoc_p10.json','cache_sme.json'):
            assert (a/rel).read_bytes() == (b/rel).read_bytes()
        old_proof,new_proof = (json.loads((folder/'confirmed.json').read_text()) for folder in (a,b))
        new_proof['records'] = [{k:v for k,v in x.items() if k!='lines'} for x in new_proof['records']]
        assert old_proof == new_proof
        assert not (b/'records').exists()
    assert (left/'comparison_checkpoints/m1_at_trial500.json').read_bytes() == (right/'comparison_checkpoints/m1_at_trial500.json').read_bytes()

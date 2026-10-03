"""終了通知の修正の承認後、指定された当て直しと8体の完走を先に確認する。"""
from pathlib import Path
import json, sys, time, traceback

root = Path(__file__).resolve().parent
sys.path.insert(0, str(root / 'source/tools/v311c_checks'))
import coll8_gate as gate

snapshot = gate.EV / 'gates-before-terminal-fix.json'
if not snapshot.exists():
    assert gate.RESULT.get('reason') == '関門不成立：record8_plainの終了通知の相互待ち（直列旗）'
    gate.save(snapshot, gate.RESULT)
    gate.RESULT = {'status': 'running', 'checks': [], 'runs': [],
        'authorization': '2026-10-03 ユーザー：直列旗の終了通知だけを修正、指定検査を当て直してrecord8_plain完走後に残りへ進む',
        'previous_stop': snapshot.name}
    gate.checkpoint()
else:
    if gate.RESULT['status'] == 'stopped':
        raise RuntimeError('新しい関門不成立からは自動で再開しない')

def sequential(function, values):
    for value in values:
        function(value)

gate.parallel = sequential
original_job = gate.run_job
fresh = {name: 'exitfix_' + name for name in (
    'serial2_simultaneous', 'serial2_serial', 'default2_baseline', 'default2_current', 'record8_plain')}

def job(name, count, **kw):
    return original_job(fresh.get(name, name), count, **kw)

gate.run_job = job
try:
    proof = json.loads((gate.EV / 'terminal-fix-model-proof.json').read_text())
    gate.check('終了通知以外の模型の計算は不変', proof['other_model_files_unchanged']
        and proof['v311c_except_agent_main_ast_identical'], proof=proof)
    units = json.loads((gate.EV / 'terminal-fix-unit-suite.json').read_text())
    gate.check('大きな終了通知・逆順完了・一度だけ解放の検査',
        all(r['returncode'] == 0 for r in units) and any(r['file'] == 'test_v311c_terminal.py' for r in units),
        isolated_files=len(units))
    # 新しい実行を、旧い合格記録の再利用より先に行う。
    p = job('serial2_simultaneous', 100, fs=[0.1, 0.9], groups=[0, 1], serial=False)
    s = job('serial2_serial', 100, fs=[0.1, 0.9], groups=[0, 1])
    gate.compare('終了通知修正後：直列と同時（2体）', p, s, comm=True)
    old = job('default2_baseline', 200, fs=[0.1, 0.9], groups=[0, 1], serial=False,
              shop=False, audit=False, lineage=False, source=root/'baseline')
    new = job('default2_current', 200, fs=[0.1, 0.9], groups=[0, 1], serial=False,
              shop=False, audit=False, lineage=False)
    gate.compare('終了通知修正後：追加旗全てオフと土台（2体）', old, new, comm=True)
    plain = job('record8_plain', 200, shop=False, audit=True, lineage=False)
    gate.inspect_population('exitfix_record8_plain', plain, gate.FS, gate.GROUPS, 200, 0.2, 0.1)
    gate.check('終了通知修正後：record8_plain完走を先に確認',
               (plain/'comm/run001.summary.json').exists())
    gate.main()
except BaseException as error:
    gate.RESULT.update(status='stopped', finished=gate.now(), reason=str(error), traceback=traceback.format_exc())
    gate.checkpoint()
    print(gate.RESULT['traceback'], flush=True)
    raise

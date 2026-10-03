"""ユーザー承認後、保存済みの全走行と過去の合格を再検査してから再開可能にする。"""
import json, subprocess
import coll8_gate as gate

old = json.loads((gate.EV / 'gates-stopped-original.json').read_text())
gate.RESULT = {'status': 'rechecking', 'checks': [], 'runs': [],
               'authorization': '2026-10-03 ユーザー：検査台本だけ修正、全合格を再検査、保存結果を再利用して続行',
               'previous_stop': 'gates-stopped-original.json'}
try:
    unchanged = not subprocess.check_output(['git', 'diff', '8273aac', '--', 'abm/',
        'tools/v311c.py', 'tools/v3_run.py', 'tools/v311c_lineage.py', 'config/'], cwd=gate.SOURCE)
    gate.check('模型のコードは承認前から不変', unchanged)
    simultaneous = gate.run_job('serial2_simultaneous', 100, fs=[0.1, 0.9], groups=[0, 1], serial=False)
    serial = gate.run_job('serial2_serial', 100, fs=[0.1, 0.9], groups=[0, 1])
    gate.compare('直列と同時（2体）', simultaneous, serial, comm=True)
    gate.inspect_population('serial2_simultaneous', simultaneous, [0.1, 0.9], [0, 1], 100, 0.2, 0.1)
    gate.inspect_population('serial2_serial', serial, [0.1, 0.9], [0, 1], 100, 0.2, 0.1)
    first = gate.run_job('no_comm_r1', 1740, q=0, m=0)
    gate.inspect_population('no_comm_r1', first, gate.FS, gate.GROUPS, 1740, 0, 0)
    prior = {c['name'] for c in old['checks'] if c['passed']}
    current = {c['name'] for c in gate.RESULT['checks'] if c['passed']}
    gate.check('以前の合格記録を全て再検査', prior <= current,
               previous_unique_checks=len(prior), missing=sorted(prior-current))
    gate.RESULT['status'] = 'running'
    gate.save(gate.EV / 'recheck-saved-results.json', gate.RESULT)
    gate.checkpoint()
except BaseException:
    gate.RESULT['status'] = 'stopped'
    gate.checkpoint()
    raise

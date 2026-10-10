"""合成構造だけを検査する。fixtureは残し、実関門には代用しない。"""
import ast
import copy
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cohort18 as M

BASE = Path(__file__).resolve().parent
FIXTURES = BASE.parent / 'fixtures_02'
A, B, U = 'a' * 64, 'b' * 64, 'c' * 64
COHORT = dict(machine_type='synthetic-c3d-standard-8', cpu_type='synthetic-cpu',
              os_image='synthetic-image', python={'version': 'synthetic-3.12',
              'implementation': 'CPython', 'executable_sha256': 'd' * 64},
              package_sha256='e' * 64, version_sha=M.C)


def write(p, x):
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open('x') as f:
        json.dump(x, f)


class Gates(unittest.TestCase):
    def setUp(self):
        self.root = FIXTURES / self.id().split('.')[-1]
        self.root.mkdir(parents=True, exist_ok=False)
        self.fp = dict(COHORT, host=A, machine_id_sha256='1' * 64, boot_id_sha256='2' * 64)
        self.reg = dict(schema=1, direct_instruction18_authorization=True,
                        cohort=COHORT.copy(), machines=[], imports={})
        for label, host in [('A', A), ('B', B)]:
            fp = dict(COHORT, host=host, machine_id_sha256=host, boot_id_sha256='2' * 64)
            if host == A:
                fp = self.fp.copy()
            name = f'fingerprints/{label}.json'
            write(self.root / name, {'fingerprint': fp})
            self.reg['machines'].append(dict(fp, fingerprint_file=name,
                                                fingerprint_sha256=M.sha(self.root / name)))
        for name in set(M.LOCAL_GATES) | M.CROSS_GATES:
            write(self.root / 'gates' / name, dict(passed=True, candidate=M.C, host=A))
        ev = self.root / 'evidence/on1_pilot20'
        self.pilot = dict(host=A, phase='pilot', commit=M.C, argv=['--trial-count', '20'])
        write(ev / 'runtime.json', self.pilot)
        write(ev / 'resource.json', {'host': A})
        self.complete_calls = []

    def complete(self, root, name):
        self.complete_calls.append((root, name))
        return self.pilot, {'host': A}, None, None, None

    def save_registry(self):
        p = self.root / 'machine_registry_instruction18.json'
        p.write_text(json.dumps(self.reg))

    def run_gate(self, phase='receive', requires=None):
        self.save_registry()
        s = dict(phase=phase, requires=requires or ['gate-on1-f0.1.json', 'gate-components.json'])
        with patch.object(M, 'fingerprint', return_value=self.fp):
            return M.check_gates(s, self.root, BASE, A, self.complete)

    def imported(self, name='gate-on1-f0.1.json', host=B, passed=True, candidate=M.C):
        p = f'foreign/{host}/{name}'
        write(self.root / p, dict(passed=passed, candidate=candidate, host=host))
        self.reg['imports'][name] = dict(path=p, host=host, sha256=M.sha(self.root / p))

    def test_registered_peer_allowed_only_for_cross_stage(self):
        self.imported()
        x = self.run_gate()
        self.assertEqual(x['required']['gate-on1-f0.1.json']['host'], B)
        self.assertEqual(self.complete_calls, [(self.root, 'on1_pilot20')])
        self.assertEqual(x['local']['gate-off8-parallel.json']['host'], A)

    def test_unknown_peer_rejected(self):
        self.imported(host=U)
        with self.assertRaisesRegex(AssertionError, '一覧に無い'):
            self.run_gate()

    def test_unlisted_current_host_rejected(self):
        self.reg['machines'] = self.reg['machines'][1:]
        with self.assertRaisesRegex(AssertionError, '現在の機械が一覧に無い'):
            self.run_gate()

    def test_each_common_fingerprint_difference_rejected(self):
        for key in M.COMMON:
            old = self.reg['machines'][1][key]
            self.reg['machines'][1][key] = 'different'
            with self.subTest(key=key), self.assertRaisesRegex(AssertionError, '同じ種類'):
                self.run_gate()
            self.reg['machines'][1][key] = old

    def test_current_boot_or_python_change_rejected(self):
        for key in ('boot_id_sha256', 'python'):
            old = self.fp[key]
            self.fp[key] = 'different'
            with self.subTest(key=key), self.assertRaisesRegex(AssertionError, '現在の機械の実指紋'):
                self.run_gate()
            self.fp[key] = old

    def test_fingerprint_archive_hash_change_rejected(self):
        (self.root / 'fingerprints/B.json').write_text('{}')
        with self.assertRaises(AssertionError):
            self.run_gate()

    def test_peer_gate_sha_change_rejected(self):
        self.imported()
        (self.root / self.reg['imports']['gate-on1-f0.1.json']['path']).write_text('{}')
        with self.assertRaisesRegex(AssertionError, 'SHA不一致'):
            self.run_gate()

    def test_failed_gate_rejected(self):
        self.imported(passed=False)
        with self.assertRaisesRegex(AssertionError, '未合格'):
            self.run_gate()

    def test_wrong_candidate_rejected(self):
        self.imported(candidate='f' * 40)
        with self.assertRaisesRegex(AssertionError, '未合格'):
            self.run_gate()

    def test_wrong_proof_host_rejected(self):
        self.imported()
        p = self.root / self.reg['imports']['gate-on1-f0.1.json']['path']
        p.write_text(json.dumps(dict(passed=True, candidate=M.C, host=U)))
        self.reg['imports']['gate-on1-f0.1.json']['sha256'] = M.sha(p)
        with self.assertRaisesRegex(AssertionError, '機械と起動が違う'):
            self.run_gate()

    def test_on1_cannot_import_other_host_even_if_registered(self):
        self.imported(name='gate-off8.json')
        with self.assertRaisesRegex(AssertionError, 'この段では'):
            self.run_gate('on1', ['gate-off8.json', 'gate-components.json'])

    def test_local_previous_gates_cannot_use_peer(self):
        p = self.root / 'gates/gate-off2.json'
        p.write_text(json.dumps(dict(passed=True, candidate=M.C, host=B)))
        with self.assertRaisesRegex(AssertionError, '機械と起動'):
            self.run_gate()

    def test_local_pilot_missing_or_wrong_host_rejected(self):
        self.pilot['host'] = B
        with self.assertRaises(AssertionError):
            self.run_gate()

    def test_pilot_complete_failure_propagated(self):
        self.complete = lambda *_: (_ for _ in ()).throw(AssertionError('原20件の不完走'))
        with self.assertRaisesRegex(AssertionError, '原20件の不完走'):
            self.run_gate()

    def test_nonapproved_gate_cannot_import_peer(self):
        self.imported(name='gate-components.json')
        with self.assertRaisesRegex(AssertionError, 'この段では'):
            self.run_gate()

    def test_production_keeps_original_same_host_requirement(self):
        p = self.root / 'gates/gate-on1-f0.1.json'
        p.write_text(json.dumps(dict(passed=True, candidate=M.C, host=B)))
        with self.assertRaisesRegex(AssertionError, '機械と起動'):
            self.run_gate('production')

    def test_registry_change_changes_frozen_inputs(self):
        x = self.run_gate()
        self.reg['note'] = 'changed while waiting'
        y = self.run_gate()
        self.assertNotEqual(x, y)

    def test_path_outside_evidence_root_rejected(self):
        self.reg['imports']['gate-on1-f0.1.json'] = dict(path='../outside.json', host=B, sha256='a' * 64)
        with self.assertRaisesRegex(AssertionError, 'rootの外'):
            self.run_gate()

    def test_duplicate_machine_rejected(self):
        self.reg['machines'].append(self.reg['machines'][1].copy())
        with self.assertRaisesRegex(AssertionError, '機械の重複'):
            self.run_gate()


class Preserved(unittest.TestCase):
    def test_original_non_gate_guards_and_functions_unchanged(self):
        old = ast.parse((BASE / 'reference_run_spawn15.py').read_text())
        new = ast.parse((BASE / 'run_cohort18.py').read_text())
        original = {x.name: x for x in old.body if isinstance(x, ast.FunctionDef)}
        new.body = [x for x in new.body if not (isinstance(x, ast.FunctionDef) and x.name == 'materialize_with_registry')]
        for i, node in enumerate(new.body):
            if not isinstance(node, ast.FunctionDef):
                continue
            if node.name == 'gates':
                new.body[i] = original['gates']
            elif node.name == 'registered':
                b = []
                for stmt in node.body:
                    if isinstance(stmt, ast.Assign) and isinstance(stmt.targets[0], ast.Name) and stmt.targets[0].id == 'gate_inputs':
                        b.append(ast.Expr(value=stmt.value))
                    elif isinstance(stmt, ast.Assert) and isinstance(stmt.msg, ast.Constant) and stmt.msg.value == '受付前後で登録一覧・関門の証拠が変わった':
                        continue
                    else:
                        b.append(stmt)
                node.body = b
            elif node.name == 'main':
                for child in ast.walk(node):
                    if isinstance(child, ast.Name) and child.id == 'materialize_with_registry':
                        child.id = 'materialize'
                    if isinstance(child, ast.Constant) and child.value == 'run_cohort18.py':
                        child.value = 'run_spawn15.py'
        self.assertEqual(ast.dump(old), ast.dump(new))

    def test_actual_original_compare_rejects_cross_host_pairs(self):
        tree = ast.parse((BASE / 'reference_compare.py').read_text())
        nodes = [x for x in tree.body if isinstance(x, ast.FunctionDef) and x.name == 'compare']
        pairs = next(x for x in tree.body if isinstance(x, ast.Assign) and isinstance(x.targets[0], ast.Name) and x.targets[0].id == 'PAIRS')
        ns = {}
        exec(compile(ast.Module(body=[pairs] + nodes, type_ignores=[]), '<原比較関数>', 'exec'), ns)
        for mode in ('on1-f0.1', 'on1-f0.9', 'receive-replay'):
            count = [0]
            def complete(*_):
                count[0] += 1
                return {'host': A if count[0] == 1 else B}, None, None, None, None
            ns['complete'] = complete
            with self.subTest(mode=mode), self.assertRaisesRegex(AssertionError, '別機械を混ぜない'):
                ns['compare'](FIXTURES, mode)

    def test_conflicted_original_index_rejected_without_selection(self):
        root = FIXTURES / self.id().split('.')[-1]
        root.mkdir(parents=True, exist_ok=False)
        (root / 'SHA256SUMS').write_text('<<<<<<< HEAD\na\n=======\nb\n>>>>>>> old\n')
        with self.assertRaisesRegex(AssertionError, '原索引の衝突'):
            M.package_fingerprint(root)

    def test_empty_original_index_rejected(self):
        root = FIXTURES / self.id().split('.')[-1]
        root.mkdir(parents=True, exist_ok=False)
        (root / 'SHA256SUMS').write_text('')
        with self.assertRaisesRegex(AssertionError, '原索引が空'):
            M.package_fingerprint(root)

    def test_measurement_checks_preserved_except_permitted_gate_reader(self):
        old = (BASE / 'reference_measurement.py').read_text()
        new = (BASE / 'measurement_cohort18.py').read_text()
        new = new.replace('from run_cohort18 import C,host,read,save,gates', 'from run import C,host,read,save')
        new = new.replace("gate_inputs=gates(r,root)\nassert gate_inputs==r['gate_inputs_instruction18'],'受付から測定点検までの証拠の変更'\n",
                          "for name in r['requires']:\n    proof=read(root/'gates'/name);assert proof['passed'] is True and proof['candidate']==C and proof['host']==r['host']\n")
        self.assertEqual(old, new)


if __name__ == '__main__':
    unittest.main(verbosity=2)

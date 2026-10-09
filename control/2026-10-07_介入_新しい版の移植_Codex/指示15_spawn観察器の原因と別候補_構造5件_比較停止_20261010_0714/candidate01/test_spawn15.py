"""指示15の親子読込と原記録関数の構造を検査する。"""
import ast
import hashlib
import importlib.util
import json
import multiprocessing as mp
import os
from pathlib import Path
import random
import sys
import unittest

HERE = Path(__file__).resolve().parent


def import_in_child(path, argv, result):
    sys.argv = argv
    os.environ.pop('SFN_INDEPENDENT_OBSERVER_RUNTIME_PATH', None)
    initial = random.getstate()
    try:
        spec = importlib.util.spec_from_file_location('__mp_main__', path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        row = {'ok': True, 'spec_unread': module.spec is None,
               'model_unimported': module.v3_run is None,
               'random_unchanged': random.getstate() == initial}
    except Exception as error:
        row = {'ok': False, 'error': repr(error)}
    Path(result).write_text(json.dumps(row))


class SpawnContract(unittest.TestCase):
    def child(self, name, path, argv):
        dest = HERE / 'structural_fixtures_01' / (name + '.json')
        process = mp.get_context('spawn').Process(target=import_in_child,
                                                 args=(str(path), argv, str(dest)))
        process.start(); process.join(20)
        self.assertFalse(process.is_alive(), '子の自然終了が未確認')
        self.assertEqual(process.exitcode, 0)
        return json.loads(dest.read_text())

    def test_old_child_reads_world_config_instead_of_runtime(self):
        world = HERE / 'shop_f0.1.json'
        row = self.child('old_stop', HERE / 'reference_observe_independent.py',
                         ['tools/v3_run.py', str(world), 'unused'])
        self.assertEqual(row, {'ok': False, 'error': "KeyError('cwd')"})

    def test_candidate_child_does_not_read_model_argv(self):
        row = self.child('new_spawn', HERE / 'observe_independent_spawn15.py',
                         ['tools/v3_run.py', str(HERE / 'shop_f0.1.json'), 'unused'])
        self.assertEqual(row, dict(ok=True, spec_unread=True,
                                  model_unimported=True, random_unchanged=True))

    def test_candidate_child_import_does_not_need_a_config_file(self):
        row = self.child('new_no_file', HERE / 'observe_independent_spawn15.py',
                         ['tools/v3_run.py', str(HERE / 'missing_world.json'), 'unused'])
        self.assertEqual(row, dict(ok=True, spec_unread=True,
                                  model_unimported=True, random_unchanged=True))

    def test_recording_bodies_are_original(self):
        old = ast.parse((HERE / 'reference_observe_independent.py').read_text())
        new = ast.parse((HERE / 'observe_independent_spawn15.py').read_text())
        for name in ('write', 'run', 'worker'):
            a = next(x for x in old.body if isinstance(x, ast.FunctionDef) and x.name == name)
            b = next(x for x in new.body if isinstance(x, ast.FunctionDef) and x.name == name)
            if name != 'write':
                self.assertEqual(ast.unparse(b.body[0]), 'initialize()')
                b.body = b.body[1:]
            self.assertEqual(ast.dump(a), ast.dump(b), name)

    def test_parent_argv_and_order_are_original(self):
        tree = ast.parse((HERE / 'observe_independent_spawn15.py').read_text())
        body = next(x for x in tree.body if isinstance(x, ast.FunctionDef) and x.name == 'main').body
        self.assertEqual([ast.unparse(x) for x in body],
                         ['initialize(sys.argv[1])', "sys.argv = spec['argv'][1:]",
                          'os.chdir(source)', 'v3_run.main()'])
        guard = tree.body[-1]
        self.assertEqual(ast.unparse(guard.test), "__name__ == '__main__'")
        self.assertEqual(ast.unparse(guard.body[0]), 'main()')


if __name__ == '__main__':
    (HERE / 'structural_fixtures_01').mkdir(exist_ok=False)
    unittest.main(verbosity=2)

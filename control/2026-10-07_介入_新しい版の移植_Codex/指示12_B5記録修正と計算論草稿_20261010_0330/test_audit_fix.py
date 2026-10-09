"""指定された監査書き出しの四つの構造だけを確かめる。"""
import copy
import io
import json
from pathlib import Path
import sys
import unittest

source = Path(__file__).resolve().parents[2] / 'source_coll_instruction12_B5'
sys.path[:0] = [str(source / 'tools'), str(source)]
import smeshared


class AuditFix(unittest.TestCase):
    def setUp(self):
        self.saved = dict(smeshared.LOG)
        self.stream = io.StringIO()
        smeshared.LOG.clear()
        smeshared.LOG.update(f=self.stream, diagnostic=False)

    def tearDown(self):
        smeshared.LOG.clear()
        smeshared.LOG.update(self.saved)

    def test_normal_bytes(self):
        record = {'z': [1, 2], 'a': {'c': None, 'b': True}}
        smeshared._log(record)
        self.assertEqual(self.stream.getvalue(), json.dumps(record, ensure_ascii=False, sort_keys=True) + '\n')

    def test_mixed_keys_copy_only(self):
        record = {'nested': [{None: 'x', 1: 'y', 'z': 'w'}]}
        before = copy.deepcopy(record)
        smeshared._log(record)
        self.assertEqual(record, before)
        self.assertEqual(json.loads(self.stream.getvalue()), {'nested': [{'null': 'x', '1': 'y', 'z': 'w'}]})

    def test_collision_stops_without_partial_row(self):
        record = {None: 'a', 'null': 'b'}
        before = copy.deepcopy(record)
        with self.assertRaises(TypeError):
            smeshared._log(record)
        self.assertEqual(record, before)
        self.assertEqual(self.stream.getvalue(), '')

    def test_non_key_type_error_not_hidden(self):
        with self.assertRaises(TypeError):
            smeshared._log({'x': object()})
        self.assertEqual(self.stream.getvalue(), '')


if __name__ == '__main__':
    unittest.main()

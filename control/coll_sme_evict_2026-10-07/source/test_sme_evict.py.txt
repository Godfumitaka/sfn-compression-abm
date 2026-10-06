"""寿命の境目、墓石、集団の試験による保存復元を構造で検査する。"""
import gzip
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path[:0] = [str(Path(__file__).resolve().parents[1]), str(Path(__file__).resolve().parents[2])]
import smeevict
import smeshared
import v311c
from sme2017 import Matcher
from v311c_fingerprint import canonical_text


class EvictTest(unittest.TestCase):
    def setUp(self):
        self.old_engine = smeshared.ENGINE
        self.saved = {k: getattr(smeshared, k) for k in ('RESULTS', 'GRAPHS', 'CHOICES', 'STATS', 'CTX', 'LOG')}
        self.cfg = dict(v311c.CFG)
        smeshared.ENGINE = Matcher(tie_seed=1, tie_uniform=True)
        for k in self.saved:
            setattr(smeshared, k, {})
        smeshared.CTX.update(call_seed=True, trial=0)
        self.temp = tempfile.TemporaryDirectory()
        self.manager = smeevict.Manager(smeshared, Path(self.temp.name)/'keys.jsonl.gz', True)
        self.manager.wrap()

    def tearDown(self):
        self.manager.stream.close()
        self.temp.cleanup()
        smeshared.ENGINE = self.old_engine
        for k, v in self.saved.items():
            setattr(smeshared, k, v)
        v311c.CFG.clear()
        v311c.CFG.update(self.cfg)

    def put(self, key, value=1):
        for table in self.manager.tables().values():
            table[key] = value

    def test_only_finished_seeded_keys_are_deleted(self):
        self.manager.enter(0)
        old = ('old', 'call-seed-v1', 101)
        unseeded = ('keep', 'ordinary', 101)
        self.put(old)
        self.put(unseeded)
        smeshared.CTX['trial'] = 1
        current = ('current', 'call-seed-v1', 102)
        self.put(current)
        self.manager.enter(1)
        for label, table in self.manager.tables().items():
            self.assertEqual(list(table), [unseeded, current])
            self.assertEqual(self.manager.dead[label], {old})
        self.manager.enter(1)
        self.assertEqual(self.manager.boundaries, 1)
        self.manager.close()
        with gzip.open(self.manager.path, 'rt') as f:
            rows = [json.loads(x) for x in f]
        self.assertEqual(len(rows), 4)
        self.assertTrue(all(r['trial'] == 1 and r['created_trial'] == 0 for r in rows))

    def test_all_lookup_forms_stop_on_exact_tombstone(self):
        key = ('old', 'call-seed-v1', 101)
        self.manager.enter(0)
        self.put(key)
        self.manager.enter(1)
        for table in self.manager.tables().values():
            for lookup in (lambda t: key in t, lambda t: t[key], lambda t: t.get(key)):
                with self.assertRaisesRegex(RuntimeError, '墓石'):
                    lookup(table)
        self.assertEqual(self.manager.tombstone_hits, 12)

    def test_unknown_age_is_retained_and_time_cannot_go_back(self):
        key = ('preinstalled', 'call-seed-v1', 103)
        dict.__setitem__(smeshared.ENGINE.cache, key, 1)
        self.manager.wrap()
        self.manager.enter(0)
        self.manager.enter(1)
        self.assertIn(key, smeshared.ENGINE.cache)
        with self.assertRaisesRegex(RuntimeError, '前の試行'):
            self.manager.enter(0)

    def test_collective_probe_keeps_dead_keys_and_restores_logical_tables(self):
        from abm.domains import Abstain
        import random
        self.manager.enter(0)
        self.put(('old', 'call-seed-v1', 101))
        self.manager.enter(1)
        smeshared.CTX['trial'] = 1
        v311c.CFG.update(sme2017=True, audit=True, run=1)
        before = canonical_text(smeshared.snapshot())
        dead = {k: set(v) for k, v in self.manager.dead.items()}
        rng = random.getstate()
        real_restore = smeshared.ENGINE.restore
        def restore(snapshot):
            real_restore(snapshot)
            self.manager.wrap()
        def predict(*args):
            self.put(('diagnostic', 'call-seed-v1', 102))
            smeshared.ENGINE.rng.random()
            smeshared.CHOICES['diagnostic'] = 1
            return SimpleNamespace(prediction=Abstain('probe')), None
        v311c.CFG['inner_predict'] = predict
        with patch.object(smeshared.ENGINE, 'restore', restore), patch('v311c._check_dictionary_guard'):
            self.assertEqual(v311c.probe(('state',), [{'scene': SimpleNamespace(relations=())}], None), [None])
        self.assertEqual(canonical_text(smeshared.snapshot()), before)
        self.assertEqual(self.manager.dead, dead)
        self.assertEqual(self.manager.tombstone_hits, 0)
        self.assertEqual(self.manager.last_trial, 1)
        self.assertEqual(random.getstate(), rng)
        self.assertTrue(all(isinstance(t, smeevict.CacheTable) for t in self.manager.tables().values()))
        self.manager.enter(2)
        for ages in self.manager.epochs.values():
            self.assertNotIn(('diagnostic', 'call-seed-v1', 102), ages)


if __name__ == '__main__':
    unittest.main()

"""SME移植の配管だけを小例で検査する。世界の成績の方向は検査しない。"""
import io
import json
import random
import sys
import subprocess
import unittest
from dataclasses import replace
from fractions import Fraction
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path[:0] = [str(Path(__file__).resolve().parents[1]), str(Path(__file__).resolve().parents[2])]
import v311c
import smeshared
import smereplay
from sme2017 import Graph, Node, Matcher
from v311c_fingerprint import canonical_text, fingerprint


class PortTest(unittest.TestCase):
    def setUp(self):
        self.cfg = dict(v311c.CFG)
        self.old_engine = smeshared.ENGINE
        self.own = {k: dict(getattr(smeshared, k)) for k in ('RESULTS', 'GRAPHS', 'CHOICES', 'STATS', 'CTX', 'LOG')}
        self.st = dict(smereplay.ST)

    def tearDown(self):
        v311c.CFG.clear(); v311c.CFG.update(self.cfg)
        smeshared.ENGINE = self.old_engine
        for k, d in self.own.items():
            current = getattr(smeshared, k); current.clear(); current.update(d)
        smereplay.ST.clear(); smereplay.ST.update(self.st)

    def test_cli_parses_without_duplicate_flags(self):
        p = subprocess.run([sys.executable, str(Path(__file__).resolve().parents[1]/"v3_run.py"), "--help"], capture_output=True, text=True)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn("--v311c-sme-replay", p.stdout)

    def test_receiver_uses_uniform_trace_choice(self):
        v311c.CFG.update(sme2017=True)
        smeshared.CTX.update(tie_uniform=True)
        tr = [SimpleNamespace(scene=SimpleNamespace(graph_id=s), written_at=1) for s in ('a', 'b')]
        state = SimpleNamespace(prototype=SimpleNamespace(traces=tr), c_trace_tags={})
        mapping = SimpleNamespace(alignment=SimpleNamespace(total_score=1))
        with patch('abm.sme.map_graphs', return_value=mapping), patch('smeshared.choose_trace', return_value=(mapping, tr[1])) as choose:
            out = v311c.choose_partner(state, 'target', None, 'A')
        self.assertIs(out[0], tr[1]); choose.assert_called_once()

    def test_receiver_flag_off_keeps_original_last_tie(self):
        v311c.CFG.update(sme2017=True)
        smeshared.CTX.update(tie_uniform=False)
        tr = [SimpleNamespace(scene=SimpleNamespace(graph_id=s), written_at=1) for s in ('b', 'a')]
        state = SimpleNamespace(prototype=SimpleNamespace(traces=tr), c_trace_tags={})
        mapping = SimpleNamespace(alignment=SimpleNamespace(total_score=1))
        with patch('abm.sme.map_graphs', return_value=mapping), patch('smeshared.choose_trace') as choose:
            out = v311c.choose_partner(state, 'target', None, 'A')
        self.assertEqual(out[0].scene.graph_id, 'a'); choose.assert_not_called()

    def test_sme_snapshot_restores_caches_choices_and_rng(self):
        v311c.CFG.update(sme2017=True)
        smeshared.ENGINE = Matcher(tie_seed=123, tie_uniform=True)
        smeshared.CHOICES.clear(); smeshared.LOG.update(diagnostic=False)
        before = smeshared.snapshot()
        snap = v311c._snapshot_modules()
        smeshared.ENGINE.rng.random(); smeshared.ENGINE.cache['new'] = 1
        smeshared.ENGINE.self_cache['new'] = 2; smeshared.ENGINE.cache_rng['new'] = (3,)
        smeshared.CHOICES['new'] = Fraction(2, 3)
        smeshared.CTX['trial'] = 999; smeshared.LOG['diagnostic'] = True
        v311c._restore_modules(snap)
        self.assertEqual(canonical_text(before), canonical_text(smeshared.snapshot()))
        self.assertFalse(smeshared.LOG['diagnostic'])

    def test_probe_restores_sme_and_global_rng(self):
        from abm.domains import Abstain
        v311c.CFG.update(sme2017=True, audit=True, run=1)
        smeshared.ENGINE = Matcher(tie_seed=1, tie_uniform=True)
        before = smeshared.snapshot(); rng = random.getstate()
        def predict(*args):
            self.assertTrue(smeshared.LOG['diagnostic'])
            smeshared.ENGINE.rng.random(); smeshared.CHOICES['probe-only'] = 1
            return SimpleNamespace(prediction=Abstain('probe')), None
        v311c.CFG['inner_predict'] = predict
        with patch('v311c.plain_to_graph', return_value='scene'), patch('v311c._check_dictionary_guard'):
            # 表示側の型だけを置き、未知の正解を予測器へ渡さない。
            scene = SimpleNamespace(relations=())
            out = v311c.probe(('learner',), [{'scene': scene}], None)
        self.assertEqual(out, [None]); self.assertEqual(random.getstate(), rng)
        self.assertEqual(canonical_text(before), canonical_text(smeshared.snapshot()))

    def test_collective_state_codec_roundtrip(self):
        import v39
        cls = v311c._state_class()
        state = cls()
        state = replace(state, c_tags={'R': {'tag': 2}}, c_trace_tags={'g': 'tag'})
        self.assertEqual(smereplay.decode(smereplay.encode(state)), state)
        self.assertEqual(type(smereplay.decode(smereplay.encode(state))), cls)

    def test_phase_journal_replay_and_mismatch(self):
        stream = io.StringIO(); smereplay.ST.update(f=stream, replay=None)
        state = ('state', Fraction(1, 2))
        # 模型の状態の通常の記録に無いFractionは指紋で扱い、journalは既存の型を使う。
        state = ('state', 2)
        smereplay.collective_phase('received', 7, state, deliveries=({'sender': 1},))
        saved = stream.getvalue(); smereplay.ST.update(f=io.StringIO(), replay=io.StringIO(saved))
        smereplay.collective_phase('received', 7, state, deliveries=({'sender': 1},))
        smereplay.ST.update(f=io.StringIO(), replay=io.StringIO(saved))
        with self.assertRaises(RuntimeError):smereplay.collective_phase('received', 7, ('different',), deliveries=({'sender': 1},))

    def test_fingerprint_keeps_order_but_sorts_sets(self):
        self.assertEqual(fingerprint({'names': {'a', 'b'}, 'ratio': Fraction(1, 2)}), fingerprint({'names': {'b', 'a'}, 'ratio': Fraction(1, 2)}))
        self.assertNotEqual(fingerprint([1, 2]), fingerprint([2, 1]))
        self.assertNotEqual(fingerprint({'a': 1, 'b': 2}), fingerprint({'b': 2, 'a': 1}))


if __name__ == '__main__':unittest.main()

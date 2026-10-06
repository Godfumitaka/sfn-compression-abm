"""各段が期待点を使う候補探索と、最終の固定Mの点の関門。"""
from pathlib import Path
from dataclasses import replace
import random
import sys
import unittest
sys.path[:0] = [str(Path(__file__).resolve().parent), str(Path(__file__).resolve().parents[1])]
from sme2017 import Graph, Node, Settings
from cstar_matcher import CstarMatcher, validate
from cstar_score import exhaustive_score
from test_cstar_fixed import toy


class MatcherGates(unittest.TestCase):
    def test_toy_candidates_and_points(self):
        scene = toy()
        memory = Graph(tuple(replace(n, state="U", names=frozenset()) if n.key == "seal" else n for n in scene.nodes))
        matcher = CstarMatcher(Settings(), tie_uniform=True)
        for p, wanted in [(0, .1175), (.1, .2052), (.5, .556), (.9, .9068), (1, .9945)]:
            dist = {n.key: {next(iter(n.names)): 1.0} for n in scene.nodes if n.kind == "relation"}
            dist["seal"] = {"sig_e": p, "other": 1-p}
            result = matcher.match(memory, scene, probabilities=dist, tie_seed=4107)
            self.assertTrue(validate(memory, scene, result))
            self.assertAlmostEqual(result.best.score, wanted, places=12)
            for candidate in result.candidates:
                mapping = dict(candidate.relation_mapping + candidate.entity_mapping)
                q = {a: dist[a].get(next(iter(scene.by_id[b].names)), 0.0)
                     for a, b in mapping.items() if scene.by_id[b].kind == "relation"}
                self.assertAlmostEqual(candidate.score, exhaustive_score(memory, scene, mapping.items(), q), delta=1e-12)

    def test_positive_probability_is_not_thresholded(self):
        scene = toy()
        dist = {n.key: {next(iter(n.names)): 1.0} for n in scene.nodes if n.kind == "relation"}
        dist["seal"] = {"sig_e": 1e-9, "other": 1-1e-9}
        result = CstarMatcher(tie_uniform=True).match(scene, scene, probabilities=dist, tie_seed=4107)
        self.assertTrue(any(h.left == "seal" and h.right == "seal" for h in result.hypotheses))
        self.assertTrue(any(h.left == "link" and h.right == "link" for h in result.hypotheses))

    def test_probability_key_changes_with_history_or_background(self):
        g = toy()
        dist = {n.key: {next(iter(n.names)): 1.0} for n in g.nodes if n.kind == "relation"}
        m = CstarMatcher(tie_uniform=True)
        old = m.match_key(g, g, 1, probabilities=dist)
        changed = {**dist, "seal": {"sig_e": .9, "other": .1}}
        self.assertNotEqual(old, m.match_key(g, g, 1, probabilities=changed))
        first = m.match(g, g, probabilities=dist, tie_seed=1)
        second = m.match(g, g, probabilities=changed, tie_seed=1)
        self.assertNotEqual(first.best.score, second.best.score)
        self.assertEqual(first, m.match(g, g, probabilities=dist, tie_seed=1))

    def test_unknown_name_marginalized_and_no_hidden_arguments(self):
        memory = toy()
        scene = Graph(tuple(Node(n.key, "unknown", args=None) if n.key == "seal" else n for n in memory.nodes))
        dist = {n.key: {next(iter(n.names)): 1.0} for n in memory.nodes if n.kind == "relation"}
        matcher = CstarMatcher(tie_uniform=True)
        a = matcher.match(memory, scene, probabilities=dist, tie_seed=2)
        b = matcher.match(memory, scene, probabilities={**dist, "seal": {"hidden_a": .2, "hidden_b": .8}}, tie_seed=2)
        self.assertEqual(a.best.score, b.best.score)
        hidden = [h for h in a.hypotheses if h.right == "seal"]
        self.assertTrue(hidden)
        self.assertTrue(all(not h.children and h.local == 0 for h in hidden))

    def test_random_candidates_are_consistent_and_exhaustive_scores_match(self):
        rng = random.Random(4108)
        for case in range(40):
            nodes = [Node("e", "entity")]
            dist = {}
            for i in range(rng.randint(1, 6)):
                key = "r" + str(i)
                args = tuple(rng.choice(nodes).key for _ in range(rng.randint(1, 2)))
                nodes.append(Node(key, "relation", frozenset({"p" + str(i)}), args))
                p = rng.choice((.1, .3, .5, .7, .9, 1))
                dist[key] = {"p" + str(i): p, "other": 1-p}
            g = Graph(tuple(nodes))
            result = CstarMatcher(tie_uniform=True).match(g, g, probabilities=dist, tie_seed=case)
            self.assertTrue(validate(g, g, result))
            for candidate in result.candidates:
                mapping = dict(candidate.relation_mapping + candidate.entity_mapping)
                q = {a: dist[a][next(iter(g.by_id[b].names))] for a, b in mapping.items() if g.by_id[b].kind == "relation"}
                self.assertAlmostEqual(candidate.score, exhaustive_score(g, g, mapping.items(), q), delta=1e-11)


if __name__ == "__main__":
    unittest.main()

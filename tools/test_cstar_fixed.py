"""固定Mの全列挙を独立の基準にした、C*の部品の関門。"""
from dataclasses import replace
from pathlib import Path
import json
import random
import sys
import unittest

sys.path[:0] = [str(Path(__file__).resolve().parent), str(Path(__file__).resolve().parents[1])]
from sme2017 import Graph, Node, Settings
from cstar_score import expected_score, exhaustive_score, structural_self_score


def toy():
    return Graph((Node("d", "entity"), Node("s", "entity"),
                  Node("seal", "relation", frozenset({"sig_e"}), ("d",)),
                  Node("at", "relation", frozenset({"at"}), ("d", "s")),
                  Node("open", "relation", frozenset({"open"}), ("d",)),
                  Node("top", "relation", frozenset({"implies"}), ("at", "open")),
                  Node("link", "relation", frozenset({"attach"}), ("seal", "top"))))


class FixedGates(unittest.TestCase):
    def test_five_toy_values(self):
        g = toy()
        pairs = tuple((n.key, n.key) for n in g.nodes)
        for p, wanted in [(0, .1175), (.1, .2052), (.5, .556), (.9, .9068), (1, .9945)]:
            q = {n.key: 1.0 for n in g.nodes if n.kind == "relation"}
            q["seal"] = p
            self.assertAlmostEqual(expected_score(g, g, pairs, q).total, wanted, places=13)
            self.assertAlmostEqual(exhaustive_score(g, g, pairs, q), wanted, places=13)

    def test_shared_child_and_independent_children(self):
        # 親rootは、pとqに共有された一席childだけに名前の不確かさがある。
        g = Graph((Node("e", "entity"),
                   Node("child", "relation", frozenset({"x"}), ("e",)),
                   Node("p", "relation", frozenset({"p"}), ("child",)),
                   Node("q", "relation", frozenset({"q"}), ("child",)),
                   Node("root", "relation", frozenset({"r"}), ("p", "q"))))
        pairs = tuple((n.key, n.key) for n in g.nodes)
        q = {n.key: 1.0 for n in g.nodes if n.kind == "relation"}
        q["child"] = .4
        got = expected_score(g, g, pairs, q)
        self.assertEqual(dict(got.dependencies)["root"], frozenset({"root", "p", "q", "child"}))
        self.assertAlmostEqual(got.total, .4 * structural_self_score(g).total, places=13)
        self.assertAlmostEqual(got.total, exhaustive_score(g, g, pairs, q), places=13)
        separate = Graph((Node("e", "entity"),
                          Node("a", "relation", frozenset({"a"}), ("e",)),
                          Node("b", "relation", frozenset({"b"}), ("e",)),
                          Node("root", "relation", frozenset({"r"}), ("a", "b"))))
        q2 = {"a": .2, "b": .3, "root": 1.0}
        result = expected_score(separate, separate, tuple((n.key, n.key) for n in separate.nodes), q2)
        self.assertAlmostEqual(dict((a, local) for a, _, local, _ in result.breakdown)["root"],
                               Settings().same_functor * .2 * .3)

    def test_independent_branch_survives(self):
        g = toy()
        q = {n.key: 1.0 for n in g.nodes if n.kind == "relation"}
        q["seal"] = 0
        result = expected_score(g, g, tuple((n.key, n.key) for n in g.nodes), q)
        local = {a: l for a, _, l, _ in result.breakdown}
        self.assertEqual(local["link"], 0)
        self.assertEqual(local["top"], Settings().same_functor)

    def test_random_fixed_mappings_240(self):
        rng = random.Random(4107)
        for _ in range(240):
            nodes = [Node("e0", "entity"), Node("e1", "entity")]
            q = {}
            for i in range(rng.randint(1, 7)):
                key = "r" + str(i)
                args = tuple(rng.choice(nodes).key for _ in range(rng.randint(1, 3)))
                nodes.append(Node(key, "relation", frozenset({"p" + str(i)}), args))
                q[key] = rng.choice((0, .1, .2, .4, .6, .8, .9, 1))
            g = Graph(tuple(nodes))
            pairs = tuple((n.key, n.key) for n in nodes)
            self.assertAlmostEqual(expected_score(g, g, pairs, q).total,
                                   exhaustive_score(g, g, pairs, q), delta=1e-11)

    def test_self_tags_and_unknown_invariance(self):
        g = toy()
        full = structural_self_score(g).total
        for state in ("F", "H", "U"):
            changed = Graph(tuple(replace(n, state=state, names=frozenset() if state == "U" else n.names)
                                  if n.kind == "relation" else n for n in g.nodes))
            self.assertEqual(structural_self_score(changed).total, full)
        hidden = Graph(tuple(Node(n.key, "unknown", args=None) if n.key == "seal" else n for n in g.nodes))
        q = {n.key: 1.0 for n in hidden.nodes if n.kind == "relation"}
        pairs = tuple((n.key, n.key) for n in hidden.nodes)
        self.assertAlmostEqual(expected_score(hidden, hidden, pairs, q).total,
                               exhaustive_score(hidden, hidden, pairs, q), places=13)

    def test_invalid_order_and_double_mapping_are_rejected(self):
        g = toy()
        pairs = tuple((n.key, n.key) for n in g.nodes)
        q = {n.key: 1.0 for n in g.nodes if n.kind == "relation"}
        reverse = Graph(tuple(replace(n, args=tuple(reversed(n.args))) if n.key == "at" else n for n in g.nodes))
        with self.assertRaises(ValueError):
            expected_score(g, reverse, pairs, q)
        with self.assertRaises(ValueError):
            expected_score(g, g, pairs + (("d", "s"),), q)


if __name__ == "__main__":
    unittest.main()

"""分布と誕生の手計算。予測前の入力だけを使う部品の検査。"""
from pathlib import Path
import math
import sys
import unittest
sys.path[:0] = [str(Path(__file__).resolve().parent), str(Path(__file__).resolve().parents[1])]
from cstar_probability import dirichlet_history, value_distributions, birth_distributions, most_probable


class ProbabilityGates(unittest.TestCase):
    def test_dirichlet_empty_and_limit(self):
        b = {"sig_n": .11, "sig_e": .89}
        self.assertEqual(dirichlet_history(b, {}), b)
        for n in (1, 2, 100, 10000):
            q = dirichlet_history(b, {"sig_n": n})
            self.assertAlmostEqual(q["sig_n"], (n + .11)/(n + 1))
            self.assertAlmostEqual(sum(q.values()), 1)
        self.assertGreater(dirichlet_history(b, {"sig_n": 10000})["sig_n"], .9999)

    def test_same_distribution_same_cost(self):
        b = {"a": .8, "b": .2}
        p = value_distributions(b, {"a": 1}, "a")
        self.assertEqual(p["F"], p["H"])
        self.assertEqual(-math.log2(p["F"]["a"]), -math.log2(p["H"]["a"]))

    def test_fit_and_seq_hand_values_four_epsilons(self):
        b = {"sig_n": .11, "sig_e": .89}
        for eps in (.005, .01, .02, .5):
            old, current = birth_distributions(b, "sig_n", "sig_n", mode="fit", epsilon=eps)
            wanted_fit = {"F": (1 - eps) + eps * .11,
                          "H": (1 - eps) * (2 + .11)/3 + eps * .11,
                          "U": .11}
            for seat, probability in wanted_fit.items():
                self.assertAlmostEqual(old[seat]["sig_n"], probability)
                self.assertEqual(old[seat], current[seat])
            before, after_first = birth_distributions(b, "sig_n", "sig_n", mode="seq", epsilon=eps)
            for seat in ("F", "H", "U"):
                self.assertEqual(before[seat], b)
            self.assertAlmostEqual(after_first["F"]["sig_n"], (1 - eps) + eps * .11)
            self.assertAlmostEqual(after_first["H"]["sig_n"], (1 - eps) * (1 + .11)/2 + eps * .11)
            self.assertEqual(after_first["U"], b)
        fit, _ = birth_distributions(b, "sig_n", "sig_n", mode="fit")
        before, sequential = birth_distributions(b, "sig_n", "sig_n", mode="seq")
        for seat, rounded in {"F": .849, "H": 1.298, "U": 3.184}.items():
            self.assertAlmostEqual(-math.log2(fit[seat]["sig_n"]), rounded, delta=.0005)
        self.assertAlmostEqual(-math.log2(sequential["H"]["sig_n"]), 1.589, delta=.0005)
        self.assertAlmostEqual(-math.log2(before["F"]["sig_n"]), 3.184, delta=.0005)

    def test_no_names_and_argmax_tie(self):
        self.assertEqual(most_probable({None: 1}), (None, "候補名なし"))
        self.assertEqual(most_probable({"a": .5, "b": .5}), (None, "同点"))
        self.assertEqual(most_probable({"a": .6, "b": .4}), ("a", None))

    def test_fit_nonunique_does_not_choose_name(self):
        with self.assertRaisesRegex(ValueError, "一意でない"):
            birth_distributions({"a": .5, "b": .5}, "a", "b", mode="fit")

    def test_seq_does_not_read_second_name(self):
        b = {'a':.11,'b':.89}
        for eps in (.005,.01,.02,.5):
            self.assertEqual(birth_distributions(b,'a','a',mode='seq',epsilon=eps),
                             birth_distributions(b,'a','b',mode='seq',epsilon=eps))
            first,second = birth_distributions(b,None,'a',mode='seq',epsilon=eps)
            self.assertEqual(first,{s:b for s in ('F','H','U')})
            self.assertEqual(second,first)
            # 一つ目の損は同じbであり、状態の差では消える。
            p,_ = birth_distributions(b,'a','b',mode='seq',epsilon=eps)
            self.assertEqual(-math.log2(p['F']['a'])+math.log2(p['H']['a']),0)


if __name__ == "__main__":
    unittest.main()

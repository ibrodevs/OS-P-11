"""Запуск: python -m unittest discover -s tests -v"""
import unittest
from random import Random

from replace import ALGORITHMS, BELADY_REFS, CONTROL_REFS, clock, fifo, lru, optimal
from experiments import generate_locality, generate_uniform


class ReplacementTests(unittest.TestCase):
    def test_control_three_frames(self):
        expected = {"FIFO": 15, "LRU": 12, "Optimal": 9, "Clock": 14}
        self.assertEqual({name: fn(CONTROL_REFS, 3).faults for name, fn in ALGORITHMS.items()}, expected)

    def test_belady_anomaly(self):
        self.assertEqual((fifo(BELADY_REFS, 3).faults, fifo(BELADY_REFS, 4).faults), (9, 10))
        for fn in (lru, optimal):
            self.assertLessEqual(fn(BELADY_REFS, 4).faults, fn(BELADY_REFS, 3).faults)

    def test_all_hits_after_loading_single_page(self):
        for fn in ALGORITHMS.values():
            result = fn([2, 2, 2, 2], 3)
            self.assertEqual(result.faults, 1)
            self.assertEqual(result.hits, 3)

    def test_empty_and_one_frame(self):
        for fn in ALGORITHMS.values():
            self.assertEqual(fn([], 2).faults, 0)
            self.assertEqual(fn([1, 2, 1, 2], 1).faults, 4)

    def test_invalid_inputs(self):
        for fn in ALGORITHMS.values():
            for n in (0, -1):
                with self.assertRaises(ValueError):
                    fn([1, 2], n)
            with self.assertRaises(ValueError):
                fn([-1], 3)

    def test_hit_does_not_change_fifo_order(self):
        self.assertEqual(fifo([1, 2, 1, 3, 1], 2).faults, 4)

    def test_lru_hits_update_recency(self):
        result = lru([1, 2, 1, 3], 2)
        self.assertEqual(result.steps[-1].evicted, 2)

    def test_optimal_future(self):
        result = optimal([1, 2, 3, 1, 4], 3)
        self.assertEqual(result.steps[-1].evicted, 1)  # три старых страницы больше не встречаются; tie = первый

    def test_clock_bit_and_hand(self):
        result = clock([0, 1, 0, 2, 3], 2)
        self.assertEqual(result.faults, 4)
        self.assertEqual(result.steps[2].bits[0], 1)
        self.assertEqual(result.steps[-1].hand, 0)

    def test_stack_property_random_samples(self):
        rng = Random(2026)
        for _ in range(40):
            refs = [rng.randrange(9) for _ in range(40)]
            for fn in (lru, optimal):
                faults = [fn(refs, n).faults for n in range(1, 9)]
                self.assertEqual(faults, sorted(faults, reverse=True))

    def test_deterministic_generators(self):
        self.assertEqual(generate_locality(seed=42), generate_locality(seed=42))
        self.assertEqual(generate_uniform(seed=42), generate_uniform(seed=42))
        self.assertEqual(len(generate_locality()), 2000)


if __name__ == "__main__":
    unittest.main()

"""Запуск: python -m unittest discover -s tests -v"""
import unittest
from functools import lru_cache
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

    def test_step_invariants_on_random_references(self):
        rng = Random(11011)
        for _ in range(70):
            refs = [rng.randrange(6) for _ in range(rng.randrange(0, 35))]
            n = rng.randrange(1, 7)
            for algorithm in ALGORITHMS.values():
                result = algorithm(refs, n)
                self.assertEqual(len(result.steps), len(refs))
                self.assertEqual(result.faults, sum(not s.hit for s in result.steps))
                self.assertEqual(result.faults + result.hits, len(refs))
                prior = set()
                for step in result.steps:
                    current = {x for x in step.frames if x is not None}
                    self.assertEqual(len(current), len([x for x in step.frames if x is not None]))
                    self.assertLessEqual(len(current), n)
                    self.assertEqual(step.hit, step.page in prior)
                    self.assertIn(step.page, current)
                    if step.hit:
                        self.assertEqual(current, prior)
                        self.assertIsNone(step.evicted)
                    else:
                        self.assertEqual(current - {step.page}, prior - ({step.evicted} if step.evicted is not None else set()))
                    prior = current

    def test_optimal_matches_independent_dynamic_programming(self):
        def exhaustive_optimum(refs, n):
            @lru_cache(None)
            def solve(i, resident):
                if i == len(refs):
                    return 0
                page = refs[i]
                if page in resident:
                    return solve(i + 1, resident)
                if len(resident) < n:
                    return 1 + solve(i + 1, tuple(sorted((*resident, page))))
                return 1 + min(solve(i + 1, tuple(sorted((set(resident) - {v}) | {page}))) for v in resident)
            return solve(0, ())

        rng = Random(730)
        for _ in range(120):
            refs = tuple(rng.randrange(5) for _ in range(rng.randrange(1, 11)))
            frames = rng.randrange(1, 5)
            self.assertEqual(optimal(refs, frames).faults, exhaustive_optimum(refs, frames))

    def test_deterministic_generators(self):
        self.assertEqual(generate_locality(seed=42), generate_locality(seed=42))
        self.assertEqual(generate_uniform(seed=42), generate_uniform(seed=42))
        self.assertEqual(len(generate_locality()), 2000)


if __name__ == "__main__":
    unittest.main()

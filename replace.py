#!/usr/bin/env python3
"""Практическая №11: FIFO, LRU, Optimal, Clock для строк обращений."""
from __future__ import annotations

import argparse
from collections import deque
from dataclasses import dataclass
from typing import Callable, Sequence

CONTROL_REFS = (7, 0, 1, 2, 0, 3, 0, 4, 2, 3, 0, 3, 2, 1, 2, 0, 1, 7, 0, 1)
BELADY_REFS = (1, 2, 3, 4, 1, 2, 5, 1, 2, 3, 4, 5)


@dataclass(frozen=True)
class Step:
    index: int
    page: int
    hit: bool
    frames: tuple[int | None, ...]
    evicted: int | None = None
    bits: tuple[int, ...] | None = None
    hand: int | None = None


@dataclass(frozen=True)
class Result:
    algorithm: str
    n_frames: int
    references: int
    faults: int
    steps: tuple[Step, ...]

    @property
    def hits(self) -> int:
        return self.references - self.faults

    @property
    def fault_rate(self) -> float:
        return self.faults / self.references if self.references else 0.0


def _validate(refs: Sequence[int], n_frames: int) -> tuple[int, ...]:
    if not isinstance(n_frames, int) or n_frames < 1:
        raise ValueError("Количество кадров должно быть положительным целым числом")
    pages = tuple(refs)
    if any(not isinstance(p, int) or isinstance(p, bool) or p < 0 for p in pages):
        raise ValueError("Номера страниц должны быть неотрицательными целыми")
    return pages


def fifo(refs: Sequence[int], n_frames: int) -> Result:
    pages = _validate(refs, n_frames)
    frames: list[int] = []
    order: deque[int] = deque()
    steps: list[Step] = []
    faults = 0
    for i, page in enumerate(pages):
        hit, evicted = page in frames, None
        if not hit:
            faults += 1
            if len(frames) == n_frames:
                evicted = order.popleft()
                frames[frames.index(evicted)] = page
            else:
                frames.append(page)
            order.append(page)
        steps.append(Step(i, page, hit, tuple(frames), evicted))
    return Result("FIFO", n_frames, len(pages), faults, tuple(steps))


def lru(refs: Sequence[int], n_frames: int) -> Result:
    pages = _validate(refs, n_frames)
    frames: list[int] = []
    last_used: dict[int, int] = {}
    steps: list[Step] = []
    faults = 0
    for i, page in enumerate(pages):
        hit, evicted = page in frames, None
        if not hit:
            faults += 1
            if len(frames) == n_frames:
                evicted = min(frames, key=lambda current: last_used[current])
                frames[frames.index(evicted)] = page
                del last_used[evicted]
            else:
                frames.append(page)
        # Время обращения обновляется и при попадании, и при промахе!
        last_used[page] = i
        steps.append(Step(i, page, hit, tuple(frames), evicted))
    return Result("LRU", n_frames, len(pages), faults, tuple(steps))


def optimal(refs: Sequence[int], n_frames: int) -> Result:
    pages = _validate(refs, n_frames)
    frames: list[int] = []
    steps: list[Step] = []
    faults = 0
    for i, page in enumerate(pages):
        hit, evicted = page in frames, None
        if not hit:
            faults += 1
            if len(frames) == n_frames:
                # Чем дальше следующее использование (или никогда), тем лучше жертва.
                future = pages[i + 1:]
                next_use = {p: future.index(p) if p in future else float("inf") for p in frames}
                evicted = max(frames, key=lambda current: next_use[current])
                frames[frames.index(evicted)] = page
            else:
                frames.append(page)
        steps.append(Step(i, page, hit, tuple(frames), evicted))
    return Result("Optimal", n_frames, len(pages), faults, tuple(steps))


def clock(refs: Sequence[int], n_frames: int) -> Result:
    pages = _validate(refs, n_frames)
    frames: list[int | None] = [None] * n_frames
    bits = [0] * n_frames
    hand = 0
    steps: list[Step] = []
    faults = 0
    for i, page in enumerate(pages):
        hit, evicted = page in frames, None
        if hit:
            bits[frames.index(page)] = 1
        else:
            faults += 1
            # Пустой слот используется сразу; для битов 1 даётся второй шанс.
            while frames[hand] is not None and bits[hand] == 1:
                bits[hand] = 0
                hand = (hand + 1) % n_frames
            evicted = frames[hand]
            frames[hand] = page
            bits[hand] = 1
            hand = (hand + 1) % n_frames
        steps.append(Step(i, page, hit, tuple(frames), evicted, tuple(bits), hand))
    return Result("Clock", n_frames, len(pages), faults, tuple(steps))


ALGORITHMS: dict[str, Callable[[Sequence[int], int], Result]] = {
    "FIFO": fifo, "LRU": lru, "Optimal": optimal, "Clock": clock
}


def run_all(refs: Sequence[int], n_frames: int) -> dict[str, Result]:
    return {name: algorithm(refs, n_frames) for name, algorithm in ALGORITHMS.items()}


def print_trace(result: Result) -> None:
    print(f"\n{result.algorithm}, кадры={result.n_frames}")
    print("№ | стр. | исход | кадры | жертва | Clock: биты, hand")
    for step in result.steps:
        values = " ".join("-" if f is None else str(f) for f in step.frames)
        details = "" if step.bits is None else f"{step.bits}, hand={step.hand}"
        evicted = "-" if step.evicted is None else str(step.evicted)
        print(f"{step.index + 1:2} | {step.page:4} | {'HIT' if step.hit else 'FAULT':5} | [{values}] | {evicted:6} | {details}")
    print(f"Отказов: {result.faults}; попаданий: {result.hits}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Симулятор алгоритмов замещения страниц")
    parser.add_argument("--refs", choices=("control", "belady"), default="control")
    parser.add_argument("--frames", type=int, nargs="+", default=[3, 4])
    parser.add_argument("--algorithm", choices=["all", *ALGORITHMS], default="all")
    parser.add_argument("--trace", action="store_true", help="Показать каждое обращение")
    args = parser.parse_args()
    refs = CONTROL_REFS if args.refs == "control" else BELADY_REFS
    names = list(ALGORITHMS) if args.algorithm == "all" else [args.algorithm]
    print(f"Набор: {args.refs}, обращений: {len(refs)}")
    print("Кадры | " + " | ".join(f"{n:>7}" for n in names))
    for n in args.frames:
        values = [ALGORITHMS[name](refs, n) for name in names]
        print(f"{n:5} | " + " | ".join(f"{result.faults:7}" for result in values))
        if args.trace:
            for result in values:
                print_trace(result)


if __name__ == "__main__":
    main()

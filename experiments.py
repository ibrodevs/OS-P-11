#!/usr/bin/env python3
"""Вариант B: воспроизводимые сравнения, CSV и PNG-график."""
from __future__ import annotations

import argparse
import csv
from pathlib import Path
from random import Random
from replace import ALGORITHMS, BELADY_REFS, CONTROL_REFS


def generate_locality(length: int = 2000, seed: int = 42) -> list[int]:
    """85% ссылок на 'горячие' страницы 0..3, остальное — на 4..19."""
    rng = Random(seed)
    return [rng.randrange(4) if rng.random() < 0.85 else rng.randrange(4, 20)
            for _ in range(length)]


def generate_uniform(length: int = 2000, seed: int = 42) -> list[int]:
    rng = Random(seed)
    return [rng.randrange(20) for _ in range(length)]


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def generate(root: Path) -> dict[str, list[dict[str, object]]]:
    results = root / "results"
    assets = root / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    control = [{"frames": n, "FIFO": ALGORITHMS["FIFO"](CONTROL_REFS, n).faults,
                "LRU": ALGORITHMS["LRU"](CONTROL_REFS, n).faults,
                "Optimal": ALGORITHMS["Optimal"](CONTROL_REFS, n).faults,
                "Clock": ALGORITHMS["Clock"](CONTROL_REFS, n).faults}
               for n in range(1, 9)]
    belady = [{"frames": n, **{name: fn(BELADY_REFS, n).faults for name, fn in ALGORITHMS.items()}}
              for n in (3, 4)]
    samples = {"locality_85_percent_hot4": generate_locality(), "uniform_20_pages": generate_uniform()}
    locality = [{"pattern": pattern, "length": len(refs), "frames": n,
                 **{name: fn(refs, n).faults for name, fn in ALGORITHMS.items()}}
                for pattern, refs in samples.items() for n in (3, 4, 8)]
    write_csv(results / "control.csv", control)
    write_csv(results / "belady.csv", belady)
    write_csv(results / "locality.csv", locality)

    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError as e:
        raise SystemExit("Нужен matplotlib: python -m pip install -r requirements.txt") from e

    fig, ax = plt.subplots(figsize=(9, 5.5))
    for name in ALGORITHMS:
        ax.plot([row["frames"] for row in control], [row[name] for row in control], marker="o", label=name)
    ax.set_title("Page faults vs. frame count — Silberschatz reference string")
    ax.set_xlabel("Number of frames")
    ax.set_ylabel("Page faults")
    ax.set_xticks(range(1, 9))
    ax.grid(alpha=0.3)
    ax.legend()
    fig.tight_layout()
    fig.savefig(assets / "page_faults.png", dpi=160)
    fig.savefig(assets / "page_faults.svg")
    plt.close(fig)

    for title, rows in (("Контрольная строка", control), ("Аномалия Белади", belady), ("Локальность", locality)):
        print(f"\n{title}:")
        for row in rows:
            print(row)
    print("\nСозданы: results/*.csv, assets/page_faults.png")
    return {"control": control, "belady": belady, "locality": locality}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parent)
    args = parser.parse_args()
    generate(args.root)

"""The personal-statement story for the Slitherlink project.

Walkthrough:
1. Generate one puzzle of each difficulty tier.
2. Show what technique each tier needs (the grading is by *human
   technique*, not by search depth).
3. Show the generator <=> solver duality: uniqueness is verified by the
   same solver that players use.
4. Show a difficulty distribution over a batch of puzzles.
"""

from __future__ import annotations

import random
import time
from collections import Counter

from difficulty import Difficulty, _tier_of, distribution, grade
from generator import generate
from grid import Slitherlink
from solver import Solver


def _clue_count(p: Slitherlink) -> int:
    return sum(1 for row in p.clues for x in row if x >= 0)


def demo_difficulty_tiers() -> None:
    print("=" * 70)
    print("1. ONE PUZZLE PER DIFFICULTY TIER")
    print("   Grading is by WHICH HUMAN TECHNIQUE IS NEEDED:")
    print("   EASY   = clue rules alone resolve every edge")
    print("   MEDIUM = vertex degree rules also needed")
    print("   HARD   = loop/connectivity rules also needed")
    print("   EXPERT = deduction stalls, search is required")
    print("=" * 70)
    # density floors tuned so the deletion loop lands on each tier
    floors = {
        Difficulty.EASY: 25,
        Difficulty.MEDIUM: 20,
        Difficulty.HARD: 15,
        Difficulty.EXPERT: 0,
    }
    for tier in Difficulty:
        t0 = time.time()
        puzzle, sol = generate(5, 5, seed=int(tier), target=tier,
                               min_clues=floors[tier], max_tries=300)
        d, info = grade(puzzle)
        tiers_needed = sorted({_tier_of(t) for t in info["techniques"].values()})
        print(f"\n--- {d.name} (clues: {_clue_count(puzzle)}, "
              f"gen: {time.time() - t0:.1f}s) ---")
        print(puzzle.render())
        top = Counter(info["techniques"].values())
        print("  techniques that fired:", dict(top))
        print("  technique tiers needed:", tiers_needed)
        print("  guesses required:", info["guesses"])
    print("\n  The solver knows 10 human techniques:")
    print("    clue rules: clue-saturated, clue-count")
    print("    corner rules: corner-1, corner-3 (unconditional), corner-2")
    print("    (conditional pair rule: a clue-2 corner's boundary edges")
    print("    are equal, inner edges equal and opposite - once one edge")
    print("    is decided, the other three follow)")
    print("    vertex rules: vertex-max2, vertex-force-on/off")
    print("    probing: failed-literal detection (MEDIUM-tier)")
    print("    loop rules: no-early-loop (the HARD-tier insight)")


def demo_duality() -> None:
    print("=" * 70)
    print("2. GENERATOR <=> SOLVER DUALITY")
    print("   The generator relies on the solver: a candidate is only")
    print("   accepted when the solver proves EXACTLY ONE solution.")
    print("=" * 70)
    puzzle, sol = generate(5, 5, seed=7, min_clues=0)
    print("\npuzzle:")
    print(puzzle.render())
    n = Solver(puzzle.copy()).count_solutions(cap=3)
    print(f"  solutions (by the same solver): {n}")
    n2 = Solver(puzzle.copy()).count_solutions(cap=3)
    print(f"  re-counted (deterministic, same result): {n2}")
    # the unique solution
    print("  the unique solution:")
    s = puzzle.copy()
    for e, st in sol.items():
        s.set_state(e, st)
    print(s.render())


def demo_distribution() -> None:
    print("=" * 70)
    print("3. DIFFICULTY DISTRIBUTION OVER A BATCH")
    print("   Vary the clue-density floor and watch the difficulty shift.")
    print("=" * 70)
    series = []
    for label, hw, mc, n in [("5x5  dense (mc=25)", 5, 25, 15),
                             ("5x5  mid   (mc=15)", 5, 15, 15),
                             ("5x5  sparse (mc=0)", 5, 0, 6)]:
        puzzles = []
        t0 = time.time()
        for i in range(n):
            p, _ = generate(hw, hw, seed=2000 + i, min_clues=mc, max_tries=50)
            puzzles.append(p)
        d = distribution(puzzles)
        series.append((label, d))
        print(f"\n{label}: {dict(d)}  ({time.time() - t0:.1f}s for {n} puzzles)")
        # every batch puzzle must be unique
        for p in puzzles:
            assert Solver(p.copy()).count_solutions(cap=3) == 1
        print("  all unique OK")
    _plot_distribution(series)


def _plot_distribution(series) -> None:
    """Grouped bar chart of difficulty vs clue density, saved to out/."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("\n  (matplotlib not installed; skipping chart)")
        return
    import os
    out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")
    os.makedirs(out_dir, exist_ok=True)
    labels = ["EASY", "MEDIUM", "HARD", "EXPERT"]
    colors = ["#4caf50", "#ffc107", "#ff9800", "#f44336"]
    fig, ax = plt.subplots(figsize=(8, 4.5))
    n_series = len(series)
    width = 0.22
    for si, (label, d) in enumerate(series):
        x = [i + si * width for i in range(4)]
        ax.bar(x, [d[l] for l in labels], width, label=label, color=colors)
    ax.set_xticks([i + width for i in range(4)])
    ax.set_xticklabels(labels)
    ax.set_ylabel("puzzles")
    ax.set_title("Difficulty vs clue density (5x5 batch)")
    ax.legend()
    path = os.path.join(out_dir, "difficulty.png")
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)
    print(f"\n  chart saved -> {path}")


def main() -> None:
    random.seed(42)
    demo_difficulty_tiers()
    demo_duality()
    demo_distribution()
    print("\nDone.")


if __name__ == "__main__":
    main()

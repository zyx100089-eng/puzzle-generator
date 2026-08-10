"""Verification suite for the puzzle generator.

Checks:
1. generated puzzles have exactly one solution (independent count)
2. generated puzzles are minimal (removing any remaining clue breaks
   uniqueness)  [on a sample]
3. every generated puzzle is solvable by the solver
4. difficulty distribution over a batch is sane (some easy, some hard)
"""

from __future__ import annotations

import random

from difficulty import distribution, grade
from generator import _unique, generate
from grid import Slitherlink
from solver import Solver

VERIFY_BUDGET = 100_000


def check_unique(puzzle: Slitherlink, tag: str) -> None:
    n = Solver(puzzle).count_solutions(cap=3)
    assert n == 1, f"{tag}: expected 1 solution, found {n}"


def check_minimal(puzzle: Slitherlink, tag: str, floor: int = 0) -> None:
    """Every clue is necessary: removing any one must destroy the unique
    solution — either by creating multiple solutions (>= 2) or by making
    the puzzle unsolvable (0).  Uses the same bounded predicate as the
    generator, with a generous budget (VERIFY_BUDGET), so the guarantee
    matches exactly what generation asserts.

    With a density floor, only clues that may legally be removed (count
    above the floor) are checked: the floor itself forces clues to stay
    regardless of necessity."""
    n_clues = sum(1 for row in puzzle.clues for x in row if x >= 0)
    for r in range(puzzle.h):
        for c in range(puzzle.w):
            if puzzle.clues[r][c] < 0:
                continue
            if n_clues <= floor:
                continue  # all remaining clues are forced by the floor
            trial = Slitherlink(puzzle.h, puzzle.w, [row[:] for row in puzzle.clues])
            trial.clues[r][c] = -1
            removable = _unique(trial, VERIFY_BUDGET)
            assert not removable, (
                f"{tag}: clue ({r},{c}) removable but kept (still 1 solution)"
            )


def main() -> None:
    random.seed(42)
    puzzles = []
    # a mix of clue densities: sparse (minimal, hard) and dense (easy).
    # sparse generation is the expensive part (exhaustive uniqueness
    # proofs), so sparse jobs are weighted toward 5x5.
    jobs = ([(5, 5, 0)] * 8 + [(5, 5, 25)] * 6
            + [(6, 6, 0)] * 2 + [(6, 6, 30)] * 3
            + [(4, 8, 24)] * 3)
    for i, (h, w, mc) in enumerate(jobs):
        puzzle, _ = generate(h, w, seed=1000 + i, min_clues=mc)
        puzzles.append(puzzle)
        check_unique(puzzle, f"puzzle {i} ({h}x{w})")
        print(f"  [{i}] {h}x{w} mc={mc} unique OK")

    # minimality: unfloored puzzles are fully minimal (every clue
    # necessary); floored puzzles are minimal above the floor (clues
    # below it are forced to stay by the density floor).
    for i, (h, w, mc) in enumerate(jobs):
        check_minimal(puzzles[i], f"puzzle {i}", floor=mc)
    print("  minimality OK on all puzzles (above their density floors)")

    d = distribution(puzzles)
    print("difficulty distribution:", d)
    assert d["EASY"] > 0 or d["MEDIUM"] > 0, "expected some low-difficulty puzzles"
    assert d["EXPERT"] > 0, "expected some search-requiring puzzles"

    for i, p in enumerate(puzzles):
        dg, info = grade(p)
        assert info["guesses"] != -1, f"puzzle {i} graded as contradiction at root!"
        assert Solver(p).solve_one() is not None, f"puzzle {i} unsolvable"
    print("  all puzzles solvable, grades consistent")

    print("\nAll verification passed.")


if __name__ == "__main__":
    main()

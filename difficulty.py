"""Difficulty grading: which human techniques, and how much search.

Grading protocol (auditable, deterministic):

1. Run the deduction rules **without** search, tracking which technique
   first decided each edge.
2. If deduction alone solves it -> difficulty by technique tier:
       tier 0: clue saturation / clue counting       -> EASY
       tier 1: vertex degree rules                   -> MEDIUM
       tier 2: loop-closure rules                    -> HARD
       (first tier needed dominates)
3. If search is needed -> count the number of branching guesses the
   solver needed after a full deduction pass (with tracking).  More
   guesses = harder.  If no deduction rules fire at all, it's a "brute
   force" puzzle: EXPERT.

Tiers (for the demo and the personal-statement writeup):
    EASY   - only clue rules needed
    MEDIUM - vertex rules needed
    HARD   - loop-closure / no-early-loop rules needed
    EXPERT - guessing required
"""

from __future__ import annotations

from enum import IntEnum

from grid import OFF, ON, Edge, Slitherlink
from solver import Contradiction, Solver


class Difficulty(IntEnum):
    EASY = 0
    MEDIUM = 1
    HARD = 2
    EXPERT = 3


_TIER = {
    "clue-saturated": 0,
    "clue-count": 0,
    "corner-1": 0,
    "corner-3": 0,
    "corner-2": 1,  # conditional pair rule: reasons from other edges' state
    "vertex-max2": 1,
    "vertex-force-on": 1,
    "vertex-force-off": 1,
    "probe": 1,
    "no-early-loop": 2,
}


def _tier_of(technique: str) -> int:
    return _TIER.get(technique, 2)


def grade(puzzle: Slitherlink, max_guesses: int = 8,
          budget: int | None = 4000) -> tuple[Difficulty, dict]:
    """Grade a puzzle.  Returns (difficulty, details) where details has
    'techniques' (dict technique -> count) and 'guesses' (int).  budget
    is passed to the guess-counting search; the guess count is bounded
    by the recursion depth cap (cap+2), and the budget is not consulted
    during deduction-only grading (pass 1 is pure deduction, which
    terminates by rule exhaustion or contradiction).  max_guesses caps
    the reported guess count (cap+1 means 'needs more than cap')."""
    # pass 1: deduction only, track techniques (the solver works on a
    # private copy, so the caller's puzzle is never mutated)
    s = Solver(puzzle, track=True, budget=budget)
    try:
        s.deduce()
    except Contradiction:
        return Difficulty.EXPERT, {"techniques": {}, "guesses": -1, "reason": "contradiction at root"}

    solved = s.p.is_solved()
    techniques = dict(s.technique_used)

    if not solved:
        # pass 2: how many guesses are needed?  (guesses == 0 is
        # unreachable here: _count_guesses returns 0 only when its root
        # deduction solves the puzzle, which pass 1 already ruled out.)
        guesses = _count_guesses(puzzle, max_guesses, budget)
        return Difficulty.EXPERT, {
            "techniques": techniques,
            "guesses": guesses,
            "reason": "search required",
        }

    # deduction solved it: difficulty = highest tier needed
    tier = max((_tier_of(t) for t in techniques.values()), default=0)
    return Difficulty(tier), {"techniques": techniques, "guesses": 0,
                              "reason": "deduction only"}


def _count_guesses(puzzle: Slitherlink, cap: int,
                   budget: int | None = 4000) -> int:
    """How many branching guesses are needed to solve, capped at cap.

    Runs a depth-bounded DFS; the guess count is the minimum number of
    branching decisions along a solution path.  Returns -1 if the puzzle
    is contradictory at the root, or cap+1 if it needs more than cap
    guesses.  The recursion is bounded by depth (cap + 2); the budget
    is passed through but is not consulted by the deduction steps."""
    p = puzzle.copy()
    s = Solver(p, budget=budget, copy=False)
    try:
        s.deduce()
    except Contradiction:
        return -1
    if s.p.is_solved():
        return 0
    best = _min_guesses(p, cap, 0, budget)
    return best


def _min_guesses(p: Slitherlink, cap: int, depth: int,
                 budget: int | None = 4000) -> int:
    """Minimum guesses needed in the subtree rooted at p, or cap+1.

    The recursion is bounded by depth (cap + 2), which is the real
    termination guarantee; the budget is passed through for the child
    deduce steps."""
    if depth > cap + 2:
        return cap + 1
    eid = Solver(p, copy=False)._mrv_eid()
    if eid is None:
        return 0 if p.is_solved() else cap + 1
    best = cap + 1
    for state in (ON, OFF):
        child = p.copy()
        child._s[eid] = state
        try:
            s = Solver(child, budget=budget, copy=False)
            s.deduce()
        except Contradiction:
            continue
        if child.is_solved():
            best = min(best, 1)
            continue
        need = _min_guesses(child, cap, depth + 1, budget) + 1
        best = min(best, need)
        if best <= 1:
            return best
    return best


def distribution(puzzles: list[Slitherlink]) -> dict[str, int]:
    """Difficulty histogram over a list of puzzles."""
    out = {d.name: 0 for d in Difficulty}
    for p in puzzles:
        d, _ = grade(p)
        out[d.name] += 1
    return out

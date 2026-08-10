"""Slitherlink puzzle generator with a provable uniqueness guarantee.

Strategy (generating is the reverse of solving):

1. **Start from a solution.**  Pick a random simple cycle on the grid graph
   (fundamental cycle of a random spanning tree - long, winding loops with
   a rich clue distribution).
2. **Clue it.**  For every cell, the clue is the number of loop edges
   around it.
3. **Delete clues** in a random order, keeping each deletion only if the
   puzzle still has exactly one solution.  This produces a sparse,
   uniquely-solvable puzzle.

Uniqueness is *verified* by a brute-force solution count (cap 2), never
assumed.  The random loop variety drives the difficulty: loops that weave
through the grid give many 2-clues, and their puzzles need deeper
deductions.
"""

from __future__ import annotations

import random

from grid import Edge, Slitherlink
from solver import Solver
from difficulty import Difficulty, grade


def random_loop(puzzle: Slitherlink, rng: random.Random | None = None) -> dict[Edge, int]:
    """A random simple cycle on the grid graph, as an edge-state dict.

    Two sources of loop shapes, chosen with probability 1/2 each:

    1. Fundamental cycle of a random spanning tree (random DFS): long,
       winding loops that weave through the whole grid, giving a rich
       clue distribution (many 1s and 2s) — the default shape.
    2. Random rectangle (in vertex coordinates): flat regions of
       0-clues produce a different difficulty profile (more
       EASY/MEDIUM puzzles).

    rng: if given, used for all randomness so generation is
    reproducible; otherwise the global random module is used.
    """
    rng = rng or random
    if rng.random() < 0.5:
        return _fundamental_cycle_loop(puzzle, rng)
    return _rectangle_loop(puzzle, rng)


def _fundamental_cycle_loop(puzzle: Slitherlink, rng: random.Random) -> dict[Edge, int]:
    h, w = puzzle.h, puzzle.w
    vertices = [(r, c) for r in range(h + 1) for c in range(w + 1)]

    def neighbors(v):
        r, c = v
        for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nr, nc = r + dr, c + dc
            if 0 <= nr <= h and 0 <= nc <= w:
                yield (nr, nc)

    for _ in range(200):
        start = rng.choice(vertices)
        parent: dict[tuple[int, int], tuple[int, int]] = {}
        seen = {start}
        stack = [start]
        while stack:
            cur = stack.pop()
            ns = list(neighbors(cur))
            rng.shuffle(ns)
            for nxt in ns:
                if nxt not in seen:
                    seen.add(nxt)
                    parent[nxt] = cur
                    stack.append(nxt)
        if len(seen) != len(vertices):
            continue
        non_tree = []
        for v in vertices:
            for nxt in neighbors(v):
                if v < nxt and parent.get(nxt) != v and parent.get(v) != nxt:
                    non_tree.append((v, nxt))
        if not non_tree:
            continue
        a, b = rng.choice(non_tree)
        path_a = []
        cur = a
        while cur != start:
            path_a.append(cur)
            cur = parent[cur]
        path_a.append(start)
        anc = set(path_a)
        path_b = []
        cur = b
        while cur not in anc:
            path_b.append(cur)
            cur = parent[cur]
        lca = cur
        idx = path_a.index(lca)
        cycle = path_a[: idx + 1] + list(reversed(path_b))
        if len(cycle) < 4:
            continue
        return _edges_from_cycle(cycle)
    raise RuntimeError("could not find a random cycle")


def _rectangle_loop(puzzle: Slitherlink, rng: random.Random) -> dict[Edge, int]:
    """A random rectangle in vertex coordinates (simple cycle)."""
    h, w = puzzle.h, puzzle.w
    if h < 2 or w < 2:
        return _fundamental_cycle_loop(puzzle, rng)
    for _ in range(50):
        r1, r2 = sorted(rng.sample(range(h + 1), 2))
        c1, c2 = sorted(rng.sample(range(w + 1), 2))
        if r2 - r1 < 1 or c2 - c1 < 1:
            continue
        if r2 - r1 == 1 and c2 - c1 == 1:
            continue  # a 1x1 square: degenerate for our clue families
        cycle = _rectangle_vertices(r1, c1, r2, c2)
        return _edges_from_cycle(cycle)
    return _fundamental_cycle_loop(puzzle, rng)


def _rectangle_vertices(r1, c1, r2, c2) -> list[tuple[int, int]]:
    return [(r1, c) for c in range(c1, c2)] + \
           [(r, c2) for r in range(r1, r2)] + \
           [(r2, c) for c in range(c2, c1, -1)] + \
           [(r, c1) for r in range(r2, r1, -1)]


def _edges_from_cycle(cycle: list[tuple[int, int]]) -> dict[Edge, int]:
    on: dict[Edge, int] = {}
    pts = cycle + [cycle[0]]
    for x, y in zip(pts, pts[1:]):
        ex, ey = (x, y) if x < y else (y, x)
        on[Edge(ex, ey)] = 1
    return on


def clues_from_loop(h: int, w: int, on: dict[Edge, int]) -> list[list[int]]:
    puzzle = Slitherlink(h, w)
    clues = [[0] * w for _ in range(h)]
    for r in range(h):
        for c in range(w):
            n = sum(1 for e in puzzle.edges_around((r, c)) if e in on)
            clues[r][c] = n
    return clues


def _unique(p: Slitherlink, budget: int | None = None) -> bool:
    """True iff the puzzle has exactly one solution within the node budget.

    A search that exceeds the budget is treated as inconclusive (returns
    False): the generator then keeps the clue, so the minimality
    guarantee is 'no clue removable while keeping uniqueness, as proven
    within the budget'."""
    s = Solver(p, budget=budget)
    n = s.count_solutions(cap=2)
    if budget is not None and getattr(s, "aborted", False):
        return False  # inconclusive: treat as not provably unique
    return n == 1


def generate(h: int, w: int, seed: int | None = None,
             min_clues: int = 0,
             target: Difficulty | None = None,
             budget: int | None = 100_000,
             max_tries: int = 100) -> tuple[Slitherlink, dict[Edge, int]]:
    """Generate a unique-solution Slitherlink puzzle.

    min_clues bounds how sparse the puzzle may get.  If target is given,
    puzzles are rejected unless they grade exactly that difficulty
    (rejection sampling over random loops and deletion orders).
    budget bounds each uniqueness search; aborted searches are treated
    conservatively (the clue is kept).

    Returns (puzzle, unique solution).  Raises after max_tries failed
    attempts.
    """
    rng = random.Random(seed)
    for _ in range(max_tries):
        dummy = Slitherlink(h, w)
        sol = random_loop(dummy, rng)
        puzzle = Slitherlink(h, w, clues_from_loop(h, w, sol))
        if not _unique(puzzle, budget):
            continue

        cells = [(r, c) for r in range(h) for c in range(w)]
        rng.shuffle(cells)
        for (r, c) in cells:
            if puzzle.clues[r][c] < 0:
                continue
            if sum(1 for row in puzzle.clues for x in row if x >= 0) <= min_clues:
                break
            trial = Slitherlink(h, w, [row[:] for row in puzzle.clues])
            trial.clues[r][c] = -1
            if _unique(trial, budget):
                puzzle.clues[r][c] = -1

        # fixed-point cleanup: a clue kept early may later become
        # redundant after other clues are removed; loop until stable.
        # Uses the same bounded predicate as the main pass, so the
        # minimality guarantee is consistent: every clue is necessary
        # as proven within the search budget.
        while True:
            removed = False
            for r in range(h):
                for c in range(w):
                    if puzzle.clues[r][c] < 0:
                        continue
                    if sum(1 for row in puzzle.clues for x in row if x >= 0) <= min_clues:
                        break
                    trial = Slitherlink(h, w, [row[:] for row in puzzle.clues])
                    trial.clues[r][c] = -1
                    if _unique(trial, budget):
                        puzzle.clues[r][c] = -1
                        removed = True
                if sum(1 for row in puzzle.clues for x in row if x >= 0) <= min_clues:
                    break
            if not removed:
                break
        if target is not None:
            d, _ = grade(puzzle)
            if d != target:
                continue
        return puzzle, sol
    raise RuntimeError(f"could not generate a {target.name if target else 'puzzle'} in {max_tries} tries")

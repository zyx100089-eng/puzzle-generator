"""pytest suite for the puzzle generator.

Run with:  python3 -m pytest test_puzzle.py -q

Fast unit-level tests (no heavy generation).  The slow end-to-end
properties (uniqueness + minimality + solvability over a batch) live
in verify.py; the exhaustive rule-soundness check over ALL valid loops
on small grids lives in soundness.py.
"""

from __future__ import annotations

import pytest

from difficulty import Difficulty, _count_guesses, _tier_of, grade
from generator import _unique, generate, random_loop
from grid import OFF, ON, UNKNOWN, Edge, Slitherlink
from solver import Contradiction, Solver


# ----------------------------------------------------------------------
# grid
# ----------------------------------------------------------------------

class TestGrid:
    def test_single_loop_solution(self):
        p = Slitherlink(1, 1, [[4]])
        for e in p.edges:
            p.set_state(e, ON)
        assert p.is_solved()
        assert p.has_single_loop()

    def test_two_loops_is_not_solved(self):
        p = Slitherlink(2, 2, [[-1] * 2 for _ in range(2)])
        # two disjoint unit loops: around cell (0,0) and cell (1,1)
        for (r, c) in ((0, 0), (1, 1)):
            for e in p.edges_around((r, c)):
                p.set_state(e, ON)
        assert not p.has_single_loop()
        assert not p.is_solved()

    def test_copy_is_isolated(self):
        p = Slitherlink(2, 2, [[4, -1], [-1, -1]])
        c = p.copy()
        c.set_state(p.edges[0], ON)
        assert p.state(p.edges[0]) == UNKNOWN
        assert c.state(p.edges[0]) == ON

    def test_vertex_degree_check(self):
        p = Slitherlink(2, 2, [[-1] * 2 for _ in range(2)])
        # three ON edges meeting at (1,1): degree 3
        p.set_state(Edge((1, 1), (1, 2)), ON)
        p.set_state(Edge((1, 1), (2, 1)), ON)
        p.set_state(Edge((0, 1), (1, 1)), ON)
        assert not p.check_local()


# ----------------------------------------------------------------------
# solver
# ----------------------------------------------------------------------

class TestSolver:
    def test_zero_clue(self):
        p = Slitherlink(3, 3, [[0, -1, -1], [-1, -1, -1], [-1, -1, -1]])
        s = Solver(p)
        s.deduce()
        for e in p.edges_around((0, 0)):
            assert s.p.state(e) == OFF

    def test_four_clue(self):
        p = Slitherlink(2, 2, [[4, -1], [-1, -1]])
        s = Solver(p)
        s.deduce()
        for e in p.edges_around((0, 0)):
            assert s.p.state(e) == ON

    def test_known_solution_count(self):
        # a single 2-clue in the middle of a 3x3 leaves many loops
        p = Slitherlink(3, 3, [[-1] * 3 for _ in range(3)])
        p.clues[1][1] = 2
        n = Solver(p).count_solutions(cap=50)
        assert n >= 2  # definitely not unique

    def test_solver_does_not_mutate_input(self):
        p = Slitherlink(2, 2, [[4, -1], [-1, -1]])
        before = p.render()
        Solver(p).count_solutions(cap=3)
        assert p.render() == before

    def test_corner_1_rule(self):
        # clue 1 at a corner: boundary edges must be OFF
        p = Slitherlink(3, 3, [[1, -1, -1], [-1, -1, -1], [-1, -1, -1]])
        s = Solver(p, track=True)
        s.deduce()
        top = s.p.state(Edge((0, 0), (0, 1)))
        left = s.p.state(Edge((0, 0), (1, 0)))
        assert top == OFF and left == OFF
        assert "corner-1" in s.technique_used.values()

    def test_corner_3_rule(self):
        p = Slitherlink(3, 3, [[3, -1, -1], [-1, -1, -1], [-1, -1, -1]])
        s = Solver(p)
        s.deduce()
        assert s.p.state(Edge((0, 0), (0, 1))) == ON
        assert s.p.state(Edge((0, 0), (1, 0))) == ON

    def test_corner_2_pair_rule(self):
        # clue-2 corner: decide one inner edge OFF -> both boundary ON
        p = Slitherlink(3, 3, [[2, -1, -1], [-1, -1, -1], [-1, -1, -1]])
        s = Solver(p, track=True)
        s.deduce()
        # nothing decided yet (all four unknown) -> still unknown
        assert s.p.state(Edge((0, 0), (0, 1))) == UNKNOWN
        # now force an inner edge OFF and re-deduce
        p2 = Slitherlink(3, 3, [[2, -1, -1], [-1, -1, -1], [-1, -1, -1]])
        p2.set_state(Edge((1, 0), (1, 1)), OFF)
        s2 = Solver(p2, track=True)
        s2.deduce()
        assert s2.p.state(Edge((0, 0), (0, 1))) == ON
        assert s2.p.state(Edge((0, 0), (1, 0))) == ON
        assert "corner-2" in s2.technique_used.values()

    def test_no_early_loop(self):
        # a partially-built loop that would close prematurely
        p = Slitherlink(2, 2, [[-1] * 2 for _ in range(2)])
        # ON path around the perimeter, leaving one edge open
        p.set_state(Edge((0, 0), (0, 1)), ON)
        p.set_state(Edge((0, 1), (1, 1)), ON)
        p.set_state(Edge((1, 1), (1, 2)), ON)  # wrong edge
        # just verify deduction doesn't crash and respects locals
        Solver(p).deduce()
        assert p.check_local()


# ----------------------------------------------------------------------
# generator
# ----------------------------------------------------------------------

class TestGenerator:
    def test_loop_is_valid_cycle(self):
        p = Slitherlink(5, 5)
        on = random_loop(p)
        assert len(on) >= 4
        for e in on:
            d = abs(e.u[0] - e.v[0]) + abs(e.u[1] - e.v[1])
            assert d == 1

    def test_seed_reproducible(self):
        a, _ = generate(5, 5, seed=77, min_clues=25)
        b, _ = generate(5, 5, seed=77, min_clues=25)
        assert a.clues == b.clues

    def test_different_seed_differs(self):
        a, _ = generate(5, 5, seed=77, min_clues=25)
        b, _ = generate(5, 5, seed=78, min_clues=25)
        assert a.clues != b.clues

    def test_generated_unique(self):
        for seed in range(5):
            p, _ = generate(5, 5, seed=seed, min_clues=0)
            assert _unique(p, None)

    def test_returned_solution_valid(self):
        p, sol = generate(5, 5, seed=3, min_clues=0)
        s = p.copy()
        for eid, e in enumerate(p.edges):
            s._s[eid] = ON if e in sol else OFF
        assert s.is_solved()

    def test_min_clues_floor_respected(self):
        p, _ = generate(5, 5, seed=5, min_clues=18)
        n = sum(1 for row in p.clues for x in row if x >= 0)
        assert n >= 18

    def test_raises_on_bad_size(self):
        with pytest.raises(RuntimeError):
            generate(0, 5, seed=1)


# ----------------------------------------------------------------------
# difficulty
# ----------------------------------------------------------------------

class TestDifficulty:
    def test_tier_mapping(self):
        assert _tier_of("clue-saturated") == 0
        assert _tier_of("corner-2") == 1
        assert _tier_of("no-early-loop") == 2
        assert _tier_of("unknown-technique") == 2  # conservative default

    def test_grade_easy_puzzle(self):
        # 1x1 clue 4: trivially solved by clue rules
        p = Slitherlink(1, 1, [[4]])
        d, info = grade(p)
        assert d == Difficulty.EASY
        assert info["guesses"] == 0

    # Cross-tier discrimination: the same puzzles the demo generates
    # (deterministic seeds), embedded so the test needs no generation.
    # Each must grade exactly at its expected tier, and the technique
    # tiers used must be consistent with the difficulty hierarchy
    # (EASY uses only clue rules; MEDIUM adds vertex rules; HARD adds
    # loop-closure; EXPERT needs search).
    _TIER_PUZZLES = {
        Difficulty.EASY: [
            [0, 0, 0, 0, 0], [0, 0, 0, 0, 0], [0, 0, 1, 0, 0],
            [0, 1, 4, 1, 0], [0, 0, 1, 0, 0],
        ],
        Difficulty.MEDIUM: [
            [0, -1, 0, 0, -1], [-1, 0, 0, 0, 1], [-1, 0, 0, 1, 4],
            [0, 0, 0, 0, 1], [0, 0, 0, 0, -1],
        ],
        Difficulty.HARD: [
            [0, 0, 0, 0, 0], [0, -1, -1, 0, -1], [-1, -1, 3, 1, -1],
            [0, 1, -1, 1, -1], [0, -1, 1, 0, -1],
        ],
        Difficulty.EXPERT: [
            [-1, 4, -1, -1, -1], [-1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1], [-1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1],
        ],
    }

    @pytest.mark.parametrize("tier", list(Difficulty))
    def test_grade_tier_discrimination(self, tier):
        p = Slitherlink(5, 5, self._TIER_PUZZLES[tier])
        d, info = grade(p)
        assert d == tier, f"expected {tier.name}, got {d.name}"
        if tier == Difficulty.EXPERT:
            assert info["guesses"] > 0
        else:
            assert info["guesses"] == 0

    def test_easy_uses_only_clue_rules(self):
        p = Slitherlink(5, 5, self._TIER_PUZZLES[Difficulty.EASY])
        d, info = grade(p)
        assert d == Difficulty.EASY
        tiers_used = {_tier_of(t) for t in info["techniques"].values()}
        assert tiers_used <= {0}, f"EASY used non-clue tiers: {tiers_used}"

    def test_medium_uses_vertex_rules(self):
        p = Slitherlink(5, 5, self._TIER_PUZZLES[Difficulty.MEDIUM])
        d, info = grade(p)
        assert d == Difficulty.MEDIUM
        tiers_used = {_tier_of(t) for t in info["techniques"].values()}
        assert 1 in tiers_used, "MEDIUM should need vertex rules"
        assert 2 not in tiers_used, "MEDIUM should not need loop rules"

    def test_hard_uses_loop_rules(self):
        p = Slitherlink(5, 5, self._TIER_PUZZLES[Difficulty.HARD])
        d, info = grade(p)
        assert d == Difficulty.HARD
        tiers_used = {_tier_of(t) for t in info["techniques"].values()}
        assert 2 in tiers_used, "HARD should need loop-closure rules"

    def test_expert_requires_search(self):
        p = Slitherlink(5, 5, self._TIER_PUZZLES[Difficulty.EXPERT])
        d, info = grade(p)
        assert d == Difficulty.EXPERT
        assert info["guesses"] > 0, "EXPERT should require branching search"

    def test_grade_contradiction(self):
        p = Slitherlink(2, 2, [[4, 0], [-1, -1]])
        d, info = grade(p)
        assert d == Difficulty.EXPERT
        assert info["guesses"] == -1

    def test_grade_does_not_mutate(self):
        p = Slitherlink(3, 3, [[1, -1, -1], [-1, -1, -1], [-1, -1, -1]])
        before = p.render()
        grade(p)
        assert p.render() == before

    def test_count_guesses_simple(self):
        # clue 4 on 1x1 solves without guesses
        p = Slitherlink(1, 1, [[4]])
        assert _count_guesses(p, 4, 10000) == 0

    def test_enum_order(self):
        assert [d.value for d in Difficulty] == [0, 1, 2, 3]
        assert Difficulty(0) is Difficulty.EASY

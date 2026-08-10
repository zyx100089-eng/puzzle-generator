# Puzzle Generator with Difficulty Grading

Constraint satisfaction project: generate Slitherlink puzzles with **provably unique
solutions** and a **human-technique-based difficulty rating**. The reverse problem:
everyone writes solvers, almost nobody writes generators.

## The maths

- Constraint satisfaction problems (CSP), backtracking search
- Inference techniques: singles, pairs, loops, graph theory of the grid
- Uniqueness verification (the generator's core guarantee)
- Fundamental cycles of random spanning trees + random rectangles as
  loop-shape sources

## The CS

- Generator <=> solver duality: uniqueness is proven by the same solver
  players use (bounded exhaustive search with a node budget)
- MRV heuristic (clued cells before unclued), probing (failed-literal
  detection), propagation
- Difficulty = which human techniques are needed to solve
- Minimality: clues are deleted to a fixed point, so every remaining
  clue is necessary above the density floor (verified against a
  generous search budget)

## Files

- `grid.py` - Slitherlink grid model (cells with clue numbers, edges),
  index-based fast internals
- `solver.py` - constraint solver with a technique hierarchy:
  clue rules (saturation, count), corner rules (corner-1 / corner-3
  unconditional; corner-2 conditional pair rule — all sound by the
  corner-vertex degree argument, brute-force verified), vertex degree
  rules, loop/connectivity rules (no-early-loop), and probing
  (failed-literal detection) when deduction stalls.  Works on a
  private copy: never mutates the caller's puzzle.
- `generator.py` - random-loop generation (fundamental cycles +
  rectangles), clue deletion with per-step uniqueness verification,
  fixed-point minimality cleanup, difficulty-targeted rejection
  sampling
- `difficulty.py` - difficulty grading: EASY (clue rules only),
  MEDIUM (+ vertex rules), HARD (+ loop rules), EXPERT (search needed,
  with a guess-count sub-metric capped at 8)
- `cli.py` - play / generate / grade from the terminal; play mode has
  a `hint` command that explains which human technique decides the
  next edge
- `verify.py` - generate a batch, check uniqueness, minimality
  (above density floors), solvability, and that the difficulty
  distribution is non-trivial
- `soundness.py` - exhaustive rule-soundness check: for EVERY valid
  loop on small grids (1275 loops on 2x2/3x3/3x4), deduce must never
  contradict the loop
- `test_puzzle.py` - pytest unit suite (25 tests)
- `demo.py` - the personal-statement story: one puzzle per tier, the
  generator<=>solver duality, a difficulty distribution demo, and a
  saved difficulty chart (`out/difficulty.png`)

## Running

```
python3 -m pytest test_puzzle.py -q   # fast unit tests (~30 s)
python3 soundness.py                  # exhaustive rule soundness
python3 verify.py                     # full verification (minutes)
python3 demo.py                       # personal-statement walkthrough
python3 cli.py --h 6 --w 6 --seed 3 --grade
python3 cli.py --play                 # play with hints
```

## Design notes

- Difficulty is controlled through clue density: dense puzzles (high
  `min_clues`) solve by local rules (EASY/MEDIUM); sparse minimal
  puzzles stall deduction and need search (EXPERT). `generate(...,
  target=...)` uses rejection sampling to hit a specific tier.
- The node budget bounds every uniqueness proof; a search that exceeds
  it is treated as "not provably unique", so the minimality guarantee
  is: no clue is removable while keeping uniqueness, as proven within
  the budget.
- The difficulty tiers are a *model* of human difficulty (not
  calibrated against human solvers) — the rationale and this honest
  caveat are discussed in INTERVIEW_GUIDE.md.
- Performance: the loop-closure rule is O(E) per call (ON-edge clue
  counts computed once, early exit with no ON edges); uniqueness
  checks on near-minimal 6x6 cost ~5 s each, so sparse 6x6 generation
  is ~75 s.

## References

- Slitherlink rules: https://en.wikipedia.org/wiki/Slitherlink
- Norvig's Sudoku solver write-up (solver philosophy)

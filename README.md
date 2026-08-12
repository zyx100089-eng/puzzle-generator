# Slitherlink Puzzle Generator

A constraint satisfaction project: generate Slitherlink puzzles with provably unique solutions and grade their difficulty using human solving techniques. Whereas most related work focuses on solvers, this project addresses the inverse problem of generating puzzles.

## Background

Slitherlink is a loop-construction puzzle played on a grid of cells, some of which contain clue numbers 0–3. A solution is a single closed loop along the grid edges that passes exactly the number of edges around each clued cell. Generating a puzzle requires three things:

1. a valid underlying loop,
2. enough clues to determine that loop uniquely, and
3. control over how hard the puzzle is to solve.

Uniqueness is the core requirement: a puzzle with multiple solutions is defective. This project proves uniqueness by construction, using the same solver that a player would use, bounded by a node budget.

## Approach

### Generation

A loop is generated from random spanning trees: taking the fundamental cycles of a spanning tree and combining them with random rectangles produces valid loop shapes. Clues are then deleted one at a time, with uniqueness re-verified after each deletion, until no further clue can be removed without losing uniqueness (a fixed point). The result is a minimal puzzle in which every clue is necessary.

Difficulty is controlled through clue density. Dense puzzles solve with local rules only; sparse minimal puzzles stall deduction and require search. `generate(..., target=...)` uses rejection sampling to hit a specific difficulty tier.

### Solving

The solver (`solver.py`) applies a hierarchy of human techniques in order:

- clue rules (saturation, edge count),
- corner rules (corner-1 / corner-3 unconditional; corner-2 conditional pair rule),
- vertex degree rules,
- loop and connectivity rules (no-early-loop),
- probing (failed-literal detection) when deduction stalls.

All rules are sound by the corner-vertex degree argument and were verified exhaustively: on every valid loop of small grids (1275 loops on 2x2, 3x3, and 3x4 grids), the deduction never contradicts the loop. The solver operates on a private copy of the puzzle and never mutates the caller's state.

### Difficulty grading

Difficulty is graded as a function of which technique tiers are needed:

- EASY: clue rules only
- MEDIUM: clue rules + vertex rules
- HARD: clue rules + vertex rules + loop rules
- EXPERT: search required (guess-count sub-metric, capped at 8)

The tiers model human difficulty but are not calibrated against human solvers.

### Uniqueness guarantees

Uniqueness proofs are bounded by a node budget. A search that exceeds the budget is treated as "not provably unique", so the minimality guarantee is precise: no clue is removable while keeping uniqueness, as proven within the budget.

## Files

| File | Purpose |
|---|---|
| `grid.py` | Slitherlink grid model (cells, clue numbers, edges) with index-based internals |
| `solver.py` | Constraint solver with the technique hierarchy described above |
| `generator.py` | Random-loop generation, clue deletion with uniqueness verification, fixed-point minimality, difficulty-targeted rejection sampling |
| `difficulty.py` | Difficulty grading into four tiers |
| `cli.py` | Terminal interface: play, generate, grade; play mode has a `hint` command explaining the technique that decides the next edge |
| `verify.py` | Batch verification: uniqueness, minimality, solvability, difficulty distribution |
| `soundness.py` | Exhaustive rule-soundness check over all valid loops on small grids |
| `demo.py` | Demonstration: one puzzle per tier, the generator/solver duality, difficulty distribution, saved chart (`out/difficulty.png`) |
| `test_puzzle.py` | Unit test suite (25 tests) |

## Performance

The loop-closure rule is O(E) per call: ON-edge clue counts are computed once, with early exit when there are no ON edges. Uniqueness checks on near-minimal 6x6 puzzles cost approximately 5 s each, so generating sparse 6x6 puzzles takes about 75 s.

## Running

```
python3 -m pytest test_puzzle.py -q   # unit tests (~30 s)
python3 soundness.py                  # exhaustive rule soundness
python3 verify.py                     # full verification (minutes)
python3 demo.py                       # difficulty tiers walkthrough
python3 cli.py --h 6 --w 6 --seed 3 --grade
python3 cli.py --play                 # play with hints
```

## References

- Slitherlink rules: https://en.wikipedia.org/wiki/Slitherlink
- Norvig's Sudoku solver write-up (solver philosophy)

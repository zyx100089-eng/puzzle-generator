"""Terminal UI for the Slitherlink generator: play, generate, grade."""

from __future__ import annotations

import argparse

from difficulty import grade
from generator import generate
from grid import OFF, ON, UNKNOWN, Edge, Slitherlink
from solver import Solver


def parse_edge(s: str, h: int, w: int) -> Edge:
    """Parse 'r,c-dir' where dir is h or v, e.g. '2,1-h' = horizontal edge
    at row 2 starting col 1; '1,3-v' = vertical edge at col 3 starting row 1."""
    cell, d = s.strip().split("-")
    r, c = map(int, cell.split(","))
    if d == "h":
        if not (0 <= r <= h and 0 <= c < w):
            raise ValueError("edge out of range")
        return Edge((r, c), (r, c + 1))
    if d == "v":
        if not (0 <= r < h and 0 <= c <= w):
            raise ValueError("edge out of range")
        return Edge((r, c), (r + 1, c))
    raise ValueError("direction must be h or v")


def play(h: int, w: int, seed: int | None) -> None:
    puzzle, sol = generate(h, w, seed)
    print("Generated puzzle:")
    print(puzzle.render())
    print()
    print("Toggle edges with 'r,c-h' / 'r,c-v', 'hint' for a hint,"
          " 'done' to finish, 'quit' to quit.")
    while True:
        cmd = input("> ").strip().lower()
        if cmd in ("quit", "q"):
            return
        if cmd in ("done", "d"):
            break
        if cmd in ("hint", "h"):
            _give_hint(puzzle)
            print(puzzle.render())
            continue
        try:
            e = parse_edge(cmd, h, w)
        except ValueError as ex:
            print("bad input:", ex)
            continue
        cur = puzzle.state(e)
        puzzle.set_state(e, {UNKNOWN: ON, ON: OFF, OFF: UNKNOWN}[cur])
        print(puzzle.render())
    if puzzle.is_solved():
        print("Solved!")
    else:
        d, info = grade(puzzle)
        print(f"Not solved yet (grade so far: {d.name}). The unique solution is:")
        for e, st in sol.items():
            puzzle.set_state(e, st)
        print(puzzle.render())


_HINT_TECHNIQUE = {
    "clue-saturated": "cell ({0},{1}) already has its clue count on: "
                      "the remaining edges must be OFF",
    "clue-count": "cell ({0},{1}) can still reach its clue only by "
                  "taking every remaining edge: they must be ON",
    "corner-1": "corner cell ({0},{1}) has clue 1: the boundary edges "
                "must be OFF (a corner vertex has degree 0 or 2)",
    "corner-2": "clue-2 corner ({0},{1}): its boundary edges are equal "
                "and its inner edges are equal and opposite - one "
                "decided edge forces the other three",
    "corner-3": "corner cell ({0},{1}) has clue 3: the boundary edges "
                "must be ON (a corner vertex has degree 0 or 2)",
    "vertex-max2": "vertex ({0},{1}) already has two ON edges: the rest "
                   "must be OFF (a loop never branches)",
    "vertex-force-on": "vertex ({0},{1}) needs one more ON edge to be "
                       "on the loop: the last unknown is ON",
    "vertex-force-off": "vertex ({0},{1}) is off the loop: the last "
                        "unknown edge is OFF",
    "no-early-loop": "edge ({0},{1}) would close a premature loop: "
                     "setting it ON strands other ON edges",
    "probe": "try both states of the edge ({0},{1}) on a copy: one "
             "contradicts, so the other is forced",
}


def _give_hint(puzzle) -> None:
    """Show the next edge the human-technique deduction would decide."""
    work = puzzle.copy()
    s = Solver(work, track=True, copy=False)
    try:
        s.deduce()
    except Exception:
        print("  (the puzzle as-is seems inconsistent)")
        return
    for e, technique in s.technique_used.items():
        if work.state(e) != puzzle.state(e):
            cell = (e.u[0], e.u[1])
            text = _HINT_TECHNIQUE.get(technique)
            if text:
                print(f"  hint: {text.format(*cell)}")
            else:
                print(f"  hint: {technique}")
            return
    d, _ = grade(puzzle)
    print(f"  no deduction rule applies (grade would be {d.name});"
          " you must reason ahead / guess.")


def main() -> None:
    ap = argparse.ArgumentParser(description="Slitherlink generator / player")
    ap.add_argument("--h", type=int, default=5)
    ap.add_argument("--w", type=int, default=5)
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--play", action="store_true",
                    help="play a generated puzzle (with hints)")
    ap.add_argument("--grade", action="store_true",
                    help="generate and print the difficulty grade")
    args = ap.parse_args()

    if args.play:
        play(args.h, args.w, args.seed)
        return

    puzzle, _ = generate(args.h, args.w, args.seed)
    print(puzzle.render())
    if args.grade:
        d, info = grade(puzzle)
        print(f"\nDifficulty: {d.name}")
        print(f"  techniques used: {info['techniques']}")
        print(f"  guesses needed:  {info['guesses']}")
        print(f"  reason:          {info['reason']}")


if __name__ == "__main__":
    main()

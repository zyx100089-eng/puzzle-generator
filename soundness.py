"""Soundness suite: every deduction rule must never contradict a
valid loop.

Method: enumerate ALL valid Slitherlink loops on small grids (every
simple cycle of the grid graph, via DFS with canonicalisation), build
the full clue set each loop implies, run the solver's deduction on it,
and assert every edge the solver decides matches the loop.  Any
violation means a deduction rule is unsound — it can force an edge the
true solution disagrees with, silently destroying valid puzzles.

This suite is what caught the corner-rule edge-lookup bug (27 of 213
valid 3x3 loops contradicted before the fix, 0 after).
"""

from __future__ import annotations

import sys

from grid import Edge, OFF, ON, UNKNOWN, Slitherlink
from solver import Contradiction, Solver


def all_loops(h: int, w: int) -> list[list[int]]:
    """Every simple cycle of the (h x w)-cell grid graph, as edge-state
    lists (ON on the cycle, OFF elsewhere)."""
    p = Slitherlink(h, w)
    verts = p._vertices
    adj = {v: [] for v in verts}
    for e in p.edges:
        adj[e.u].append(e.v)
        adj[e.v].append(e.u)
    cycles = set()
    for start in verts:
        stack = [(start, [start], {start})]
        while stack:
            cur, path, seen = stack.pop()
            for nxt in adj[cur]:
                if nxt == start and len(path) >= 4:
                    m = min(path)
                    i = path.index(m)
                    rot = path[i:] + path[:i]
                    rev = [rot[0]] + list(reversed(rot[1:]))
                    cycles.add(tuple(min(rot, rev)))
                elif nxt not in seen and nxt > start:
                    stack.append((nxt, path + [nxt], seen | {nxt}))
    loops = []
    for cyc in cycles:
        s = [OFF] * len(p.edges)
        pts = list(cyc) + [cyc[0]]
        for x, y in zip(pts, pts[1:]):
            e = Edge(x, y) if x < y else Edge(y, x)
            s[p._eid[e]] = ON
        loops.append(s)
    return loops


def check_soundness(h: int, w: int, use_loop_rules: bool = True) -> tuple[int, int]:
    """Returns (loops_checked, violations)."""
    loops = all_loops(h, w)
    p = Slitherlink(h, w)
    viol = 0
    for s in loops:
        clues = [[0] * w for _ in range(h)]
        for idx, cell in enumerate(p._cells):
            clues[cell[0]][cell[1]] = sum(
                1 for e in p._cell_edges[idx] if s[e] == ON)
        trial = Slitherlink(h, w, clues)
        solver = Solver(trial)
        try:
            solver.deduce(use_loop_rules=use_loop_rules)
        except Contradiction:
            viol += 1
            continue
        for eid, st in enumerate(solver.p._s):
            if st != UNKNOWN and st != s[eid]:
                viol += 1
                break
    return len(loops), viol


def main() -> None:
    total_loops = 0
    total_viol = 0
    for (h, w) in [(2, 2), (3, 3), (3, 4)]:
        n, v = check_soundness(h, w, use_loop_rules=True)
        total_loops += n
        total_viol += v
        print(f"  {h}x{w}: {n} loops, deduction violations: {v}")
        assert v == 0, f"UNSOUND rules on {h}x{w}"
    # also verify the pre-search rules alone (no loop closure)
    n, v = check_soundness(3, 3, use_loop_rules=False)
    print(f"  3x3 without loop rules: {n} loops, violations: {v}")
    assert v == 0
    print(f"\nAll soundness checks passed ({total_loops} loops, "
          f"{total_viol} violations).")
    return 0


if __name__ == "__main__":
    sys.exit(main())

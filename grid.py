"""Slitherlink grid model.

Slitherlink: an h x w grid of cells, each containing a clue (0-4, or -1 for
empty).  The task is to draw a single closed loop along the grid edges such
that the number of loop edges around each clue cell equals its clue, and the
loop does not cross or branch.

Model:
    vertices v = (r, c) with 0 <= r <= h, 0 <= c <= w
    edges e = (u, w) - horizontal edges between (r, c)-(r, c+1)
                      vertical edges between (r, c)-(r+1, c)

State of each edge: UNKNOWN / ON (in the loop) / OFF (not in the loop).

Performance design: internal state lives in a flat list `_s` indexed by edge
id, with precomputed incidence tables (_cell_edges, _vertex_edges,
_edge_cells).  The public API (edges, edges_around, state, set_state,
render) still speaks in Edge objects, but the solver's hot loops use the
flat lists and integer ids directly.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator

UNKNOWN = 0
ON = 1
OFF = 2


@dataclass(frozen=True)
class Edge:
    """A grid edge.  u < v lexicographically for a canonical representation."""

    u: tuple[int, int]  # (row, col) of first endpoint
    v: tuple[int, int]  # (row, col) of second endpoint

    def __lt__(self, other: "Edge") -> bool:
        return (self.u, self.v) < (other.u, other.v)


class Slitherlink:
    def __init__(self, h: int, w: int, clues: list[list[int]] | None = None):
        self.h = h
        self.w = w
        self.clues = [row[:] for row in clues] if clues else [[-1] * w for _ in range(h)]
        self.edges: list[Edge] = list(self._all_edges())
        self._eid: dict[Edge, int] = {e: i for i, e in enumerate(self.edges)}
        self._s: list[int] = [UNKNOWN] * len(self.edges)

        self._cells: list[tuple[int, int]] = [(r, c) for r in range(h) for c in range(w)]
        self._vertices: list[tuple[int, int]] = [
            (r, c) for r in range(h + 1) for c in range(w + 1)
        ]
        # precomputed incidence tables (integer ids)
        self._cell_edges: list[list[int]] = [
            [self._eid[e] for e in self._edges_around(cell)] for cell in self._cells
        ]
        self._vertex_edges: list[list[int]] = [
            [self._eid[e] for e in self._edges_incident(v)] for v in self._vertices
        ]
        self._edge_cells: list[list[int]] = [
            [self._ci(c) for c in self._cells_around(e)] for e in self.edges
        ]

    # ---- index helpers ---------------------------------------------------

    def _ci(self, cell: tuple[int, int]) -> int:
        return cell[0] * self.w + cell[1]

    def _vi(self, v: tuple[int, int]) -> int:
        return v[0] * (self.w + 1) + v[1]

    # ---- geometry ---------------------------------------------------------

    def _all_edges(self) -> Iterator[Edge]:
        h, w = self.h, self.w
        for r in range(h + 1):
            for c in range(w):
                yield Edge((r, c), (r, c + 1))
        for r in range(h):
            for c in range(w + 1):
                yield Edge((r, c), (r + 1, c))

    def _edges_around(self, cell: tuple[int, int]) -> list[Edge]:
        r, c = cell
        return [
            Edge((r, c), (r, c + 1)),
            Edge((r, c), (r + 1, c)),
            Edge((r + 1, c), (r + 1, c + 1)),
            Edge((r, c + 1), (r + 1, c + 1)),
        ]

    def _edges_incident(self, v: tuple[int, int]) -> list[Edge]:
        r, c = v
        out = []
        if c < self.w:
            out.append(Edge((r, c), (r, c + 1)))
        if c > 0:
            out.append(Edge((r, c - 1), (r, c)))
        if r < self.h:
            out.append(Edge((r, c), (r + 1, c)))
        if r > 0:
            out.append(Edge((r - 1, c), (r, c)))
        return out

    def _cells_around(self, e: Edge) -> list[tuple[int, int]]:
        (r1, c1), (r2, c2) = e.u, e.v
        cells = []
        if r1 == r2:  # horizontal
            if r1 - 1 >= 0:
                cells.append((r1 - 1, min(c1, c2)))
            if r1 < self.h:
                cells.append((r1, min(c1, c2)))
        else:  # vertical
            if c1 - 1 >= 0:
                cells.append((min(r1, r2), c1 - 1))
            if c1 < self.w:
                cells.append((min(r1, r2), c1))
        return cells

    # ---- state --------------------------------------------------------------

    def state(self, e: Edge) -> int:
        return self._s[self._eid[e]]

    def set_state(self, e: Edge, state: int) -> None:
        self._s[self._eid[e]] = state

    def clue(self, cell: tuple[int, int]) -> int:
        return self.clues[cell[0]][cell[1]]

    def edges_around(self, cell: tuple[int, int]) -> list[Edge]:
        return [self.edges[i] for i in self._cell_edges[self._ci(cell)]]

    def cells_around(self, e: Edge) -> list[tuple[int, int]]:
        return [self._cells[i] for i in self._edge_cells[self._eid[e]]]

    def count_around(self, cell: tuple[int, int]) -> int:
        s, ci = self._s, self._ci(cell)
        return sum(s[i] == ON for i in self._cell_edges[ci])

    def unknown_around(self, cell: tuple[int, int]) -> int:
        s, ci = self._s, self._ci(cell)
        return sum(s[i] == UNKNOWN for i in self._cell_edges[ci])

    def copy(self) -> "Slitherlink":
        other = Slitherlink.__new__(Slitherlink)
        other.h, other.w = self.h, self.w
        other.clues = [row[:] for row in self.clues]
        other.edges = self.edges
        other._eid = self._eid
        other._s = self._s[:]
        other._cells = self._cells
        other._vertices = self._vertices
        other._cell_edges = self._cell_edges
        other._vertex_edges = self._vertex_edges
        other._edge_cells = self._edge_cells
        return other

    # ---- validation ----------------------------------------------------------

    def check_local(self) -> bool:
        """Clue constraints + max-degree-2 on ON edges.  All precomputed, no
        object allocation."""
        s, h, w = self._s, self.h, self.w
        for idx, cell in enumerate(self._cells):
            clue = self.clues[cell[0]][cell[1]]
            if clue < 0:
                continue
            es = self._cell_edges[idx]
            n = 0
            unk = 0
            for eid in es:
                st = s[eid]
                if st == ON:
                    n += 1
                elif st == UNKNOWN:
                    unk += 1
            if n > clue or n + unk < clue:
                return False
        for es in self._vertex_edges:
            n = 0
            for eid in es:
                if s[eid] == ON:
                    n += 1
                    if n > 2:
                        return False
        return True

    def all_vertices(self) -> Iterator[tuple[int, int]]:
        return iter(self._vertices)

    def is_solved(self) -> bool:
        if UNKNOWN in self._s:
            return False
        return self.check_local() and self.has_single_loop()

    def has_single_loop(self) -> bool:
        """ON edges form exactly one cycle (a single closed loop)."""
        s = self._s
        w1 = self.w + 1  # vertex row stride
        on_vertices: set[int] = set()
        adj: dict[int, list[int]] = {}
        for eid, st in enumerate(s):
            if st != ON:
                continue
            e = self.edges[eid]
            u = e.u[0] * w1 + e.u[1]
            v = e.v[0] * w1 + e.v[1]
            on_vertices.add(u)
            on_vertices.add(v)
            adj.setdefault(u, []).append(v)
            adj.setdefault(v, []).append(u)
        if not on_vertices:
            return False
        for ns in adj.values():
            if len(ns) != 2:
                return False
        start = next(iter(on_vertices))
        seen = {start}
        stack = [start]
        while stack:
            cur = stack.pop()
            for nxt in adj.get(cur, ()):
                if nxt not in seen:
                    seen.add(nxt)
                    stack.append(nxt)
        return len(seen) == len(on_vertices)

    # ---- display --------------------------------------------------------------

    def render(self) -> str:
        s, h, w = self._s, self.h, self.w
        rows = []
        for r in range(2 * h + 1):
            line = []
            for c in range(2 * w + 1):
                if r % 2 == 0 and c % 2 == 0:
                    line.append("+")
                elif r % 2 == 0:
                    eid = self._eid[Edge((r // 2, c // 2), (r // 2, c // 2 + 1))]
                    st = s[eid]
                    line.append("-" if st == ON else ("x" if st == OFF else " "))
                elif c % 2 == 0:
                    eid = self._eid[Edge((r // 2, c // 2), (r // 2 + 1, c // 2))]
                    st = s[eid]
                    line.append("|" if st == ON else ("x" if st == OFF else " "))
                else:
                    clue = self.clues[r // 2][c // 2]
                    line.append(str(clue) if clue >= 0 else " ")
            rows.append("".join(line))
        return "\n".join(rows)

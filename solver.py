"""Slitherlink solver with a human-technique hierarchy.

Three layers, mirroring how a human solves:

1. **Deduction (techniques)** - deterministic rules that fix edges:
   - clue saturation: clue 0 -> all four edges off; clue 3 -> all on;
     clue n with n on -> rest off; clue n with n unknown left -> all on
   - max-degree: a vertex with 2 on-edges -> remaining incident edges off;
     a vertex with (2 - k) on-edges and exactly k unknown edges left -> all on
   - loop-closure prevention: an edge whose two endpoints are already
     connected by ON edges would close a premature loop (unless the puzzle
     would then be complete) -> the "no-early-loop" rule

2. **Search** - backtracking with MRV (fewest unknowns), used both to
   *find* solutions and to *count* them (for the generator's uniqueness
   guarantee).

3. **Difficulty grading** - which techniques are needed, and how much
   search was required (in difficulty.py).

Design: hot loops operate on the flat edge-state list `p._s` and integer
edge ids via the precomputed incidence tables; the technique tracker still
records Edge objects for the difficulty grader.
"""

from __future__ import annotations

from typing import Optional

from grid import OFF, ON, UNKNOWN, Edge, Slitherlink


class Contradiction(Exception):
    pass


class Solver:
    def __init__(self, puzzle: Slitherlink, track: bool = False,
                 budget: int | None = None, copy: bool = True):
        # By default the solver works on a private copy: solving or
        # deducing never mutates the caller's puzzle.  Internal call
        # sites that already pass a fresh copy use copy=False.
        self.p = puzzle.copy() if copy else puzzle
        self.track = track
        self.budget = budget
        self.nodes = 0
        self.aborted = False
        self.technique_used: dict[Edge, str] = {}
        # probing (failed-literal detection): a total probe cap shared
        # through the search, so deduce() stays cheap on hard puzzles
        self._probe_limit = 200
        self._probe_state = {"count": 0}

    # ------------------------------------------------------------------
    # Deduction rules (flat-list fast paths)
    # ------------------------------------------------------------------

    def _note(self, e: Edge, technique: str) -> None:
        if self.track:
            self.technique_used.setdefault(e, technique)

    def _set(self, eid: int, state: int, technique: str) -> None:
        if self.p._s[eid] == UNKNOWN:
            self.p._s[eid] = state
            if self.track:
                self.technique_used.setdefault(self.p.edges[eid], technique)

    def _deduce_clues(self) -> bool:
        p, s = self.p, self.p._s
        changed = False
        for idx, cell in enumerate(p._cells):
            clue = p.clues[cell[0]][cell[1]]
            if clue < 0:
                continue
            es = p._cell_edges[idx]
            on = 0
            for eid in es:
                if s[eid] == ON:
                    on += 1
            if on == clue:
                for eid in es:
                    if s[eid] == UNKNOWN:
                        s[eid] = OFF
                        changed = True
                        if self.track:
                            self.technique_used.setdefault(p.edges[eid],
                                                           "clue-saturated")
            elif on + sum(1 for eid in es if s[eid] == UNKNOWN) == clue:
                for eid in es:
                    if s[eid] == UNKNOWN:
                        s[eid] = ON
                        changed = True
                        if self.track:
                            self.technique_used.setdefault(p.edges[eid], "clue-count")
        # clue 0 / clue 3 are subsumed by the two branches above.
        return changed

    def _deduce_corners(self) -> bool:
        """Corner-cell rules (sound by the corner-vertex argument).

        A corner vertex has exactly two incident edges (top + left),
        and in a valid loop every vertex has degree 0 or 2, so those
        two edges are both ON or both OFF.

          - clue 1 at a corner cell: the two boundary edges must be OFF
            (if they were ON the cell would already have 2 ON edges).
          - clue 3 at a corner cell: the two boundary edges must be ON
            (if they were OFF the cell could have at most 2 ON edges).
          - clue 2 at a corner cell (the conditional pair rule): the
            two boundary edges are EQUAL, and the two inner edges are
            equal and OPPOSITE to the boundary pair.  So once any of
            the four edges is decided, the other three follow:

                boundary edge ON  -> other boundary ON,  both inner OFF
                boundary edge OFF -> other boundary OFF, both inner ON
                inner edge ON     -> other inner ON,     both boundary OFF
                inner edge OFF    -> other inner OFF,    both boundary ON

            (unconditional 'clue-2 corner => boundary ON' is UNSOUND:
            the loop may cut across the inner edges — brute-force
            verified.)
        """
        p, s = self.p, self.p._s
        changed = False
        for (r, c) in ((0, 0), (0, p.w - 1), (p.h - 1, 0), (p.h - 1, p.w - 1)):
            clue = p.clues[r][c]
            if clue < 0:
                continue
            # the four edges of the corner cell
            es = p._cell_edges[p._ci((r, c))]
            top, left, bottom, right = es
            boundary, inner = [], []
            if r == 0:
                boundary.append(p._eid[Edge((0, c), (0, c + 1))])
            if c == 0:
                boundary.append(p._eid[Edge((r, 0), (r + 1, 0))])
            if r == p.h - 1:
                boundary.append(p._eid[Edge((p.h, c), (p.h, c + 1))])
            if c == p.w - 1:
                boundary.append(p._eid[Edge((r, p.w), (r + 1, p.w))])
            for eid in es:
                if eid not in boundary:
                    inner.append(eid)

            for eid in boundary:
                if s[eid] != UNKNOWN:
                    continue
                if clue == 1:
                    s[eid] = OFF
                    changed = True
                    if self.track:
                        self.technique_used.setdefault(p.edges[eid], "corner-1")
                elif clue == 3:
                    s[eid] = ON
                    changed = True
                    if self.track:
                        self.technique_used.setdefault(p.edges[eid], "corner-3")
                elif clue == 2 and len(boundary) == 2 and len(inner) == 2:
                    # conditional pair rule: look at the OTHER boundary
                    # edge and the inner edges for anything decided.
                    # boundary is opposite of inner (ON <-> OFF).
                    other_b = boundary[0] if boundary[1] == eid else boundary[1]
                    decided = None
                    if s[other_b] != UNKNOWN:
                        decided = s[other_b]
                    else:
                        for ie in inner:
                            if s[ie] != UNKNOWN:
                                decided = 3 - s[ie]  # 1<->2, i.e. ON<->OFF
                                break
                    if decided is not None:
                        s[eid] = decided
                        changed = True
                        if self.track:
                            self.technique_used.setdefault(p.edges[eid], "corner-2")
        return changed

    def _deduce_vertices(self) -> bool:
        """Max-degree / loop-degree rules at every grid vertex.

        In a solution every vertex has degree 0 (off the loop) or 2 (on it).
        Valid forced moves:
          - on == 2        -> remaining incident edges OFF
          - on == 1, unk==1 -> the last unknown must be ON (degree 0 impossible)
          - on == 0, unk==1 -> the last unknown must be OFF (degree 1 impossible)
        A vertex with on == 0 and unk == 2 is genuinely ambiguous (0 or 2 on).
        """
        p, s = self.p, self.p._s
        changed = False
        for es in p._vertex_edges:
            on = 0
            unk = 0
            for eid in es:
                st = s[eid]
                if st == ON:
                    on += 1
                elif st == UNKNOWN:
                    unk += 1
            if on == 2:
                for eid in es:
                    if s[eid] == UNKNOWN:
                        s[eid] = OFF
                        changed = True
                        if self.track:
                            self.technique_used.setdefault(p.edges[eid],
                                                           "vertex-max2")
            elif on == 1 and unk == 1:
                for eid in es:
                    if s[eid] == UNKNOWN:
                        s[eid] = ON
                        changed = True
                        if self.track:
                            self.technique_used.setdefault(p.edges[eid],
                                                           "vertex-force-on")
            elif on == 0 and unk == 1:
                for eid in es:
                    if s[eid] == UNKNOWN:
                        s[eid] = OFF
                        changed = True
                        if self.track:
                            self.technique_used.setdefault(p.edges[eid],
                                                           "vertex-force-off")
        return changed

    def _deduce_loop_closure(self) -> bool:
        """No-early-loop rule.

        If an UNKNOWN edge (u,v) has endpoints already joined by an ON
        path P, then setting it ON closes a loop L = P + (u,v).  L can be
        the final solution only if:
          - the ON graph is exactly the component containing u (no ON
            edges outside L), and
          - L satisfies every clue.
        Otherwise (u,v) must be OFF: either L violates a clue, or the
        solution's single loop would have to contain both L and the
        outside ON edges, which is impossible.

        Connectivity is computed once per call with union-find over the ON
        edges (O(V + E)), instead of BFS from every vertex.
        """
        p, s = self.p, self.p._s
        n_vertices = len(p._vertices)
        parent = list(range(n_vertices))

        def find(a: int) -> int:
            while parent[a] != a:
                parent[a] = parent[parent[a]]
                a = parent[a]
            return a

        on_edges = []
        for eid, st in enumerate(s):
            if st == ON:
                on_edges.append(eid)
        if not on_edges:
            return False  # no ON edges, nothing to close

        for eid in on_edges:
            e = p.edges[eid]
            u = e.u[0] * (p.w + 1) + e.u[1]
            v = e.v[0] * (p.w + 1) + e.v[1]
            ru, rv = find(u), find(v)
            if ru != rv:
                parent[ru] = rv

        # is the ON graph a single connected component?
        on_connected = True
        e0 = p.edges[on_edges[0]]
        root0 = find(e0.u[0] * (p.w + 1) + e0.u[1])
        for eid in on_edges:
            e = p.edges[eid]
            if find(e.u[0] * (p.w + 1) + e.u[1]) != root0:
                on_connected = False
                break

        # When the ON graph is one component, the clue counts are the
        # same for every candidate edge; compute them once (O(E) total
        # instead of O(E) per candidate).
        base_counts = None
        if on_connected:
            base_counts = [0] * len(p._cells)
            for eid, st in enumerate(s):
                if st == ON:
                    for ci in p._edge_cells[eid]:
                        base_counts[ci] += 1

        changed = False
        for eid, st in enumerate(s):
            if st != UNKNOWN:
                continue
            e = p.edges[eid]
            u = e.u[0] * (p.w + 1) + e.u[1]
            v = e.v[0] * (p.w + 1) + e.v[1]
            if find(u) != find(v):
                continue
            # endpoints already joined by an ON path
            if on_connected and self._loop_satisfies_clues(base_counts, eid):
                continue  # closing this loop IS the solution; leave unknown
            s[eid] = OFF
            changed = True
            if self.track:
                self.technique_used.setdefault(e, "no-early-loop")
        return changed

    def _loop_satisfies_clues(self, base_counts, eid: int) -> bool:
        """True iff the loop formed by all ON edges plus edge eid satisfies
        every clue (i.e. it is a complete valid solution loop).  base_counts
        is the clue contribution of the ON edges, computed once per call."""
        p = self.p
        for ci in p._edge_cells[eid]:
            base_counts[ci] += 1
        ok = True
        for idx, cell in enumerate(p._cells):
            clue = p.clues[cell[0]][cell[1]]
            if clue >= 0 and base_counts[idx] != clue:
                ok = False
                break
        for ci in p._edge_cells[eid]:
            base_counts[ci] -= 1
        return ok

    def _deduce_probe(self) -> bool:
        """Probing / failed-literal detection (from SAT solving).

        When the other rules stall, tentatively set the MRV edge to ON
        and then to OFF, each followed by a cheap bounded deduction.
        If one assignment contradicts, the other is forced — the branch
        becomes a deduction.  This prunes the search tree dramatically
        on puzzles whose ambiguity is only a few edges deep.

        The total probe count is capped by _probe_limit, shared through
        the search (self._probe_state), so probing never explodes the
        runtime.  Each probe runs a bounded deduction (deduce's own
        pass limit), which is what keeps a single probe cheap.
        """
        st = self._probe_state
        if st["count"] >= self._probe_limit:
            return False
        eid = self._mrv_eid()
        if eid is None:
            return False
        outcomes = {}
        for state in (ON, OFF):
            st["count"] += 1
            child = self.p.copy()
            child._s[eid] = state
            s = Solver(child, copy=False)
            s._probe_limit = 0  # no recursive probing inside a probe
            try:
                s.deduce()
                outcomes[state] = not child.check_local()
            except Contradiction:
                outcomes[state] = True  # contradiction -> state impossible
        if outcomes[ON] and not outcomes[OFF]:
            self._set(eid, OFF, "probe")
            return True
        if outcomes[OFF] and not outcomes[ON]:
            self._set(eid, ON, "probe")
            return True
        return False

    def deduce(self, max_passes: int = 64, use_loop_rules: bool = True) -> None:
        for _ in range(max_passes):
            changed = False
            changed |= self._deduce_clues()
            changed |= self._deduce_corners()
            changed |= self._deduce_vertices()
            if use_loop_rules:
                changed |= self._deduce_loop_closure()
            if not changed:
                # cheap rule set stalled: try probing the MRV edge
                changed = self._deduce_probe()
            if not self.p.check_local():
                raise Contradiction("local constraints violated after deduction")
            if not changed:
                return
        raise Contradiction("deduction did not converge")

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def _mrv_eid(self) -> Optional[int]:
        """Pick the UNKNOWN edge with the fewest consistent choices."""
        p = self.p
        best_eid: Optional[int] = None
        best_score = None
        for eid, st in enumerate(p._s):
            if st != UNKNOWN:
                continue
            score = self._score(eid)
            if best_score is None or score < best_score:
                best_eid, best_score = eid, score
        return best_eid

    def _score(self, eid: int) -> int:
        """MRV score: lower = better branch candidate.

        Edges in clued cells are preferred over edges in unclued cells
        (branching on an unconstrained edge is pure waste).  Among
        clued cells, edges in cells closest to saturation score best:
        they either finish the cell or fail fast.
        """
        p = self.p
        s = 0
        clued = False
        for ci in p._edge_cells[eid]:
            clue = p.clues[p._cells[ci][0]][p._cells[ci][1]]
            if clue < 0:
                continue
            clued = True
            n = 0
            unk = 0
            for e2 in p._cell_edges[ci]:
                st = p._s[e2]
                if st == ON:
                    n += 1
                elif st == UNKNOWN:
                    unk += 1
            if n == clue or n + unk == clue:
                s -= 2
            elif n + unk - 1 == clue:
                s -= 1
        if not clued:
            s += 4  # unclued edges branch last
        return s

    def solve_all(self, limit: int | None = None) -> list[dict[Edge, int]]:
        ctx = {"solutions": [], "nodes": 0, "aborted": False}
        self._search(ctx, limit)
        self.nodes = ctx["nodes"]
        self.aborted = ctx["aborted"]
        return ctx["solutions"]

    def _search(self, ctx: dict, limit: int | None) -> None:
        """DFS with a shared budget across recursion.  ctx = {"solutions",
        "nodes", "aborted"}.  When the node budget is exhausted, "aborted"
        is set and the search stops; callers treat an aborted search as
        inconclusive."""
        if limit is not None and len(ctx["solutions"]) >= limit:
            return
        if ctx["aborted"]:
            return
        ctx["nodes"] += 1
        if self.budget is not None and ctx["nodes"] > self.budget:
            ctx["aborted"] = True
            return
        p = self.p
        try:
            self.deduce()
        except Contradiction:
            return
        if p.is_solved():
            ctx["solutions"].append({e: p._s[i] for i, e in enumerate(p.edges)})
            return
        eid = self._mrv_eid()
        if eid is None:
            return
        for state in (ON, OFF):
            if limit is not None and len(ctx["solutions"]) >= limit:
                return
            if ctx["aborted"]:
                return
            child = p.copy()
            child._s[eid] = state
            cs = Solver(child, track=self.track, budget=self.budget,
                        copy=False)  # child is already a fresh copy
            cs._probe_state = self._probe_state  # share the probe budget
            cs._search(ctx, limit)

    def solve_one(self) -> Optional[dict[Edge, int]]:
        sols = self.solve_all(limit=1)
        return sols[0] if sols else None

    def count_solutions(self, cap: int = 3) -> int:
        return len(self.solve_all(limit=cap))

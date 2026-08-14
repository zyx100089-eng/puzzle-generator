"""Render a generated Slitherlink puzzle as a clean image (docs/puzzle.png).

Shows the puzzle grid with clues, plus the unique solution loop
overlaid in blue. Used in the README so the project is understandable
at a glance.
"""

from __future__ import annotations

import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from generator import generate
from grid import ON, Slitherlink


def render_puzzle_image(h: int, w: int, seed: int, path: str) -> None:
    puzzle, sol = generate(h, w, seed)
    fig, ax = plt.subplots(figsize=(4.2, 4.2))
    ax.set_aspect("equal")
    ax.axis("off")

    # grid lines
    for r in range(h + 1):
        ax.plot([0, w], [r, r], color="#bbbbbb", lw=1, zorder=1)
    for c in range(w + 1):
        ax.plot([c, c], [0, h], color="#bbbbbb", lw=1, zorder=1)

    # solution loop in blue
    for e, st in sol.items():
        if st == ON:
            (r1, c1), (r2, c2) = e.u, e.v
            ax.plot([c1, c2], [r1, r2], color="#1f77b4", lw=3.5,
                    solid_capstyle="round", zorder=3)

    # clues
    for r in range(h):
        for c in range(w):
            clue = puzzle.clues[r][c]
            if clue >= 0:
                ax.text(c + 0.5, r + 0.5, str(clue), ha="center",
                        va="center", fontsize=15, fontweight="bold",
                        color="#333333", zorder=4)

    ax.set_xlim(-0.3, w + 0.3)
    ax.set_ylim(h + 0.3, -0.3)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fig.tight_layout(pad=0.2)
    fig.savefig(path, dpi=150)
    plt.close(fig)
    print(f"saved {path}")


if __name__ == "__main__":
    render_puzzle_image(6, 6, 3, os.path.join("docs", "puzzle.png"))

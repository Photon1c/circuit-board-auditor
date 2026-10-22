"""Netlist model: components, jumper wires, and the nets they form on a board."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from .board import Board

NC = "nc"  # pin intentionally left unconnected


class _UnionFind:
    def __init__(self) -> None:
        self._parent: dict[str, str] = {}

    def add(self, x: str) -> None:
        self._parent.setdefault(x, x)

    def find(self, x: str) -> str:
        self.add(x)
        while self._parent[x] != x:
            self._parent[x] = self._parent[self._parent[x]]
            x = self._parent[x]
        return x

    def union(self, a: str, b: str) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self._parent[rb] = ra


@dataclass(frozen=True)
class Component:
    ref: str                      # e.g. "R1", "D1", "P1"
    kind: str                     # resistor, led, pot, source, ic, ...
    pins: dict[str, str]          # pin name -> hole name, or NC
    value: str = ""


@dataclass
class Netlist:
    board: Board
    components: list[Component] = field(default_factory=list)
    wires: list[tuple[str, str]] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.wires = [(self.board.normalize(a), self.board.normalize(b)) for a, b in self.wires]
        self._uf = _UnionFind()
        members: dict[str, list[str]] = {}
        for hole in self.board.holes():
            self._uf.add(hole)
            members.setdefault(self.board.strip_id(hole), []).append(hole)
        for group in members.values():
            for other in group[1:]:
                self._uf.union(group[0], other)
        for a, b in self.wires:
            self._uf.union(a, b)

    # ----- queries -------------------------------------------------------
    def net_of(self, hole: str) -> str:
        return self._uf.find(self.board.normalize(hole))

    def continuity(self, a: str, b: str) -> bool:
        """True if the two holes are electrically connected (multimeter beep)."""
        return self.net_of(a) == self.net_of(b)

    def placed_pins(self) -> Iterable[tuple[Component, str, str]]:
        """Yield (component, pin, canonical hole) for pins that sit on the board.

        Pins with off-board hole names are skipped here; run_checks reports them.
        """
        for comp in self.components:
            for pin, hole in comp.pins.items():
                if hole != NC and self.board.has_hole(hole):
                    yield comp, pin, self.board.normalize(hole)

    def nets_with_pins(self) -> dict[str, list[tuple[str, str]]]:
        """Map each net to the (ref, pin) pairs sitting on it."""
        out: dict[str, list[tuple[str, str]]] = {}
        for comp, pin, hole in self.placed_pins():
            out.setdefault(self._uf.find(hole), []).append((comp.ref, pin))
        return out


def _occupied_rows(components: Iterable[Component], wires: Iterable[tuple[str, str]]) -> list[int]:
    rows: list[int] = []
    for comp in components:
        for hole in comp.pins.values():
            if hole != NC:
                rows.append(int(hole[1:]))
    for a, b in wires:
        rows.append(int(a[1:]))
        rows.append(int(b[1:]))
    return rows


def breadvolt_lift(board: Board, components: Iterable[Component], wires: Iterable[tuple[str, str]]) -> int:
    """Rows to add so the lowest occupied hole sits on the first row above a BreadVolt."""
    spec = board.breadvolt
    if spec is None:
        return 0
    rows = _occupied_rows(components, wires)
    if not rows or min(rows) > spec.covered_rows:
        return 0
    return spec.covered_rows - min(rows) + 1


def shift_placement(
    board: Board,
    components: list[Component],
    wires: list[tuple[str, str]],
    delta: int,
) -> tuple[list[Component], list[tuple[str, str]]]:
    """Return a copy of the placement moved by delta rows. delta 0 returns the same lists."""
    if delta == 0:
        return components, wires
    try:
        moved = [
            Component(
                ref=comp.ref,
                kind=comp.kind,
                value=comp.value,
                pins={
                    pin: hole if hole == NC else board.shift_hole(hole, delta)
                    for pin, hole in comp.pins.items()
                },
            )
            for comp in components
        ]
        moved_wires = [(board.shift_hole(a, delta), board.shift_hole(b, delta)) for a, b in wires]
    except ValueError as ex:
        raise ValueError(f"The circuit does not fit on the board ({ex})") from ex
    return moved, moved_wires


def netlist_from_dict(board: Board, data: dict) -> Netlist:
    comps = [
        Component(
            ref=c["ref"],
            kind=c["kind"],
            pins={k: str(v) for k, v in c["pins"].items()},
            value=c.get("value", ""),
        )
        for c in data.get("components", [])
    ]
    wires = [(w[0], w[1]) for w in data.get("wires", [])]
    return Netlist(board, comps, wires)

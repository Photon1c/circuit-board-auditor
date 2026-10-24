"""Board geometry: load a board JSON and map hole names to electrical strips."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

_HOLE_RE = re.compile(r"^([A-Za-z])(\d+)$")
_KINDS = {"breadboard", "stripboard", "perfboard"}


@dataclass(frozen=True)
class Rail:
    id: str
    name: str
    holes: int
    segments: tuple[tuple[int, int], ...]
    skip: tuple[int, ...] = ()


@dataclass(frozen=True)
class BreadVolt:
    """Rows covered by a BreadVolt module, and how many rail holes its pins use."""
    covered_rows: int
    pin_rows: int


def _parse_breadvolt(raw: dict | None) -> BreadVolt | None:
    if not raw:
        return None
    return BreadVolt(covered_rows=int(raw["covered_rows"]), pin_rows=int(raw["pin_rows"]))


def _parse_rails(raw_rails: list) -> tuple[Rail, ...]:
    parsed: list[Rail] = []
    for raw in raw_rails:
        if not isinstance(raw, dict) or "id" not in raw:
            label = raw.get("name", raw) if isinstance(raw, dict) else raw
            raise ValueError(f"Rail {label!r} is missing an id")
        holes = int(raw["holes"])
        if "segments" in raw:
            segments = tuple((int(pair[0]), int(pair[1])) for pair in raw["segments"])
        elif holes >= 1:
            segments = ((1, holes),)
        else:
            segments = ()
        parsed.append(Rail(
            id=str(raw["id"]).upper(),
            name=str(raw.get("name", raw["id"])),
            holes=holes,
            segments=segments,
            skip=tuple(int(n) for n in raw.get("skip", [])),
        ))
    return tuple(parsed)


@dataclass(frozen=True)
class Board:
    name: str
    kind: str
    rows: int
    columns: tuple[str, ...]
    origin: str = ""
    strips: tuple[tuple[str, ...], ...] = ()       # breadboard: column groups shared per row
    strip_orientation: str = "vertical"            # stripboard: "vertical" or "horizontal"
    breaks: tuple[tuple[str, int, int], ...] = ()  # stripboard: (column, row_a, row_b) cuts
    column_direction: str = "left_to_right"        # or "right_to_left"
    row_direction: str = "top_to_bottom"           # or "bottom_to_top"
    right_row_numbers: str = "same"                # or "inverted" on the far side of a split board
    rails: tuple[Rail, ...] = ()
    breadvolt: BreadVolt | None = None

    # ----- construction -------------------------------------------------
    @classmethod
    def from_dict(cls, data: dict) -> "Board":
        kind = data["type"]
        if kind not in _KINDS:
            raise ValueError(f"Unknown board type: {kind!r}")
        breaks = tuple(
            (b["column"].upper(), int(b["between_rows"][0]), int(b["between_rows"][1]))
            for b in data.get("breaks", [])
        )
        board = cls(
            name=data["name"],
            kind=kind,
            rows=int(data["rows"]),
            columns=tuple(c.upper() for c in data["columns"]),
            origin=data.get("origin", ""),
            strips=tuple(tuple(c.upper() for c in g) for g in data.get("strips", [])),
            strip_orientation=data.get("strip_orientation", "vertical"),
            breaks=breaks,
            column_direction=data.get("column_direction", "left_to_right"),
            row_direction=data.get("row_direction", "top_to_bottom"),
            right_row_numbers=data.get("right_row_numbers", "same"),
            rails=_parse_rails(list(data.get("rails", []))),
            breadvolt=_parse_breadvolt(data.get("breadvolt")),
        )
        board._validate()
        return board

    @classmethod
    def load(cls, path: str | Path) -> "Board":
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))

    def _validate(self) -> None:
        if self.column_direction not in {"left_to_right", "right_to_left"}:
            raise ValueError(f"Bad column_direction: {self.column_direction!r}")
        if self.row_direction not in {"top_to_bottom", "bottom_to_top"}:
            raise ValueError(f"Bad row_direction: {self.row_direction!r}")
        if self.right_row_numbers not in {"same", "inverted"}:
            raise ValueError(f"Bad right_row_numbers: {self.right_row_numbers!r}")
        cols = set(self.columns)
        if self.kind == "breadboard":
            seen: set[str] = set()
            for group in self.strips:
                for c in group:
                    if c not in cols:
                        raise ValueError(f"Strip column {c} is not on the board")
                    if c in seen:
                        raise ValueError(f"Column {c} appears in two strips")
                    seen.add(c)
        if self.kind == "stripboard":
            if self.strip_orientation not in {"vertical", "horizontal"}:
                raise ValueError(f"Bad strip_orientation: {self.strip_orientation!r}")
            if self.strip_orientation == "horizontal" and self.breaks:
                raise ValueError("Breaks are only supported on vertical strips for now")
            for c, a, b in self.breaks:
                if c not in cols:
                    raise ValueError(f"Break column {c} is not on the board")
                if b != a + 1:
                    raise ValueError(f"Break in column {c} must join adjacent rows, got {a}-{b}")
        seen_ids: set[str] = set()
        for rail in self.rails:
            rid = rail.id
            if len(rid) != 1 or not rid.isalpha():
                raise ValueError(f"Rail id {rid!r} must be a single letter")
            if rid in seen_ids:
                raise ValueError(f"Rail id {rid} is duplicated")
            if rid in cols:
                raise ValueError(f"Rail id {rid} matches a column letter")
            seen_ids.add(rid)
            if rail.holes < 1:
                raise ValueError(f"Rail {rid} holes must be at least 1")
            covered: list[tuple[int, int]] = []
            for first, last in rail.segments:
                if first < 1 or last > rail.holes or first > last:
                    raise ValueError(
                        f"Rail {rid} segment [{first}, {last}] is outside 1..{rail.holes}"
                    )
                for start, end in covered:
                    if first <= end and last >= start:
                        raise ValueError(f"Rail {rid} has overlapping segments")
                covered.append((first, last))
            seen_skip: set[int] = set()
            for n in rail.skip:
                if not 1 <= n <= rail.holes:
                    raise ValueError(f"Rail {rid} skip {n} is outside 1..{rail.holes}")
                if n in seen_skip:
                    raise ValueError(f"Rail {rid} skip {n} is repeated")
                seen_skip.add(n)
        if self.breadvolt is not None:
            if not 1 <= self.breadvolt.pin_rows <= self.breadvolt.covered_rows:
                raise ValueError(
                    f"BreadVolt pin rows must be inside 1..{self.breadvolt.covered_rows}"
                )
            if self.breadvolt.covered_rows > self.rows:
                raise ValueError(
                    f"BreadVolt covers {self.breadvolt.covered_rows} rows but {self.name} has {self.rows}"
                )

    # ----- hole names ----------------------------------------------------
    def normalize(self, name: str) -> str:
        """Return the canonical hole name ('e1' -> 'E1'), or raise ValueError."""
        m = _HOLE_RE.match(name.strip())
        if not m:
            raise ValueError(f"Bad hole name: {name!r}")
        col, row = m.group(1).upper(), int(m.group(2))
        rail = self._rail(col)
        if rail is not None:
            if row in rail.skip or not 1 <= row <= rail.holes:
                raise ValueError(f"Hole {name!r} is not on {self.name}")
            return f"{col}{row}"
        if col not in self.columns or not 1 <= row <= self.rows:
            raise ValueError(f"Hole {name!r} is not on {self.name}")
        return f"{col}{row}"

    def _rail(self, col: str) -> Rail | None:
        for rail in self.rails:
            if rail.id == col:
                return rail
        return None

    def has_hole(self, name: str) -> bool:
        try:
            self.normalize(name)
            return True
        except ValueError:
            return False

    def holes(self) -> Iterator[str]:
        for c in self.columns:
            for r in range(1, self.rows + 1):
                yield f"{c}{r}"
        for rail in self.rails:
            for n in self._rail_numbers(rail):
                yield f"{rail.id}{n}"

    # ----- layout --------------------------------------------------------
    def positions(self) -> dict[str, tuple[float, float]]:
        """Screen grid position (x to the right, y down) for every hole.

        Breadboards get an extra step at each strip boundary, which draws the center gap.
        """
        cols = list(self.columns)
        if self.column_direction == "right_to_left":
            cols.reverse()
        col_x: dict[str, float] = {}
        x = 0.0
        prev_group: int | None = None
        for i, col in enumerate(cols):
            group = self._group_index(col)
            if i > 0:
                x += 1.0
                if self.kind == "breadboard" and group != prev_group:
                    x += 1.0
            col_x[col] = x
            prev_group = group
        out: dict[str, tuple[float, float]] = {}
        for row in range(1, self.rows + 1):
            y = float(row - 1) if self.row_direction == "top_to_bottom" else float(self.rows - row)
            for col in self.columns:
                out[f"{col}{row}"] = (col_x[col], y)
        left = [rail for rail in self.rails if "left" in rail.name.lower()]
        right = [rail for rail in self.rails if rail not in left]
        for i, rail in enumerate(left):
            self._place_rail(out, rail, float(-(len(left) - i)))
        last_x = max(col_x.values()) if col_x else 0.0
        for i, rail in enumerate(right):
            self._place_rail(out, rail, last_x + 2.0 + i)
        return out

    def _rail_numbers(self, rail: Rail) -> Iterator[int]:
        skipped = set(rail.skip)
        for n in range(1, rail.holes + 1):
            if n not in skipped:
                yield n

    def _place_rail(self, out: dict[str, tuple[float, float]], rail: Rail, x: float) -> None:
        for n in self._rail_numbers(rail):
            y = float(n - 1) if self.row_direction == "top_to_bottom" else float(self.rows - n)
            out[f"{rail.id}{n}"] = (x, y)

    def shift_hole(self, hole: str, delta: int) -> str:
        """Move a hole by delta rows. Raises ValueError if the result is not on the board."""
        canon = self.normalize(hole)
        number = int(canon[1:]) + delta
        return self.normalize(f"{canon[0]}{number}")

    def breadvolt_zone(self, hole: str) -> str | None:
        """'pin' for a rail hole the module plugs into, 'covered' for the rest of its body."""
        if self.breadvolt is None:
            return None
        canon = self.normalize(hole)
        number = int(canon[1:])
        if number > self.breadvolt.covered_rows:
            return None
        if self._rail(canon[0]) is not None and number <= self.breadvolt.pin_rows:
            return "pin"
        return "covered"

    def _group_index(self, col: str) -> int | None:
        for i, group in enumerate(self.strips):
            if col in group:
                return i
        return None

    # ----- strips --------------------------------------------------------
    def strip_id(self, name: str) -> str:
        """Holes with the same strip id are electrically connected."""
        canon = self.normalize(name)
        col, row = canon[0], int(canon[1:])

        rail = self._rail(col)
        if rail is not None:
            for k, (first, last) in enumerate(rail.segments):
                if first <= row <= last:
                    return f"rail:{rail.id}:seg{k}"
            return f"rail:{rail.id}:hole{row}"

        if self.kind == "perfboard":
            return f"hole:{canon}"

        if self.kind == "breadboard":
            for group in self.strips:
                if col in group:
                    return f"row{row}:{group[0]}-{group[-1]}"
            return f"hole:{canon}"

        # stripboard
        if self.strip_orientation == "vertical":
            segment = sum(1 for c, a, _ in self.breaks if c == col and a < row)
            return f"col{col}:seg{segment}"
        return f"row{row}"

"""Plain-text layout of a placement: parts, jumpers, and connected groups.

The drawing alone forces the reader to trace lines, so this module turns
the same netlist into words. Each connected group is one electrical node;
the text says which part pins and analyzer clips sit on it, in which holes.
"""
from __future__ import annotations

from core.board import Board
from core.nets import NC, Netlist


def strip_label(board: Board, hole: str) -> str:
    """'row 22 A-E strip', '+ rail', 'hole C22', ... for one hole."""
    canon = board.normalize(hole)
    sid = board.strip_id(canon)
    if sid.startswith("row"):
        _row, cols = sid[3:].split(":", 1)
        return f"row {_row} {cols} strip"
    if sid.startswith("rail:"):
        rail_id = sid.split(":")[1]
        for rail in board.rails:
            if rail.id == rail_id:
                return f"{rail.name.strip()} rail ({rail_id})"
        return f"rail {rail_id}"
    if sid.startswith("col"):
        return f"column {sid[3:].split(':')[0]} strip"
    return f"hole {canon}"


def _hole_sort(board: Board, hole: str) -> tuple[float, float, str]:
    x, y = board.positions()[board.normalize(hole)]
    return (y, x, board.normalize(hole))


def legend_lines(board: Board) -> list[str]:
    """How to read the drawing, in words."""
    lines = [
        "Solid colored dot: a part's pin is in that hole. The color "
        "matches the part's name on the drawing.",
        "Open dot: an empty hole. Hover any dot to read its hole name "
        "and what sits in it.",
        "A part's outline joins its own legs so you can see the part. "
        "The checker does not treat a part as connecting its pins: a "
        "resistor or LED stands between them.",
        "Straight line between two holes: a jumper wire. Red lands on "
        "a + rail, black on a ground rail, dark grey is a plain signal.",
        "Colored ring with a CH label: a logic-analyzer clip on that "
        "hole. View only; it changes no connections.",
        "Shaded area: hardware sitting on the board (a module, an "
        "expansion board). View only; not a connection.",
    ]
    if board.kind == "breadboard" and board.strips:
        groups = " and ".join(f"{group[0]}-{group[-1]}" for group in board.strips)
        lines.append(
            f"On this board, holes {groups} in the same row are one "
            "connected strip; the center gap keeps the two sides apart. "
            "A jumper is how a signal crosses rows or the gap."
        )
    return lines


def describe_layout(board: Board, netlist: Netlist, *,
                    analyzer: dict[str, str] | None = None,
                    covers: tuple[tuple[str, str, str], ...] = ()) -> str:
    """The placement as ASCII text: parts, jumpers, groups, extras."""
    out: list[str] = []

    out.append("PARTS (REF PIN=HOLE)")
    if not netlist.components:
        out.append("  (none placed)")
    for comp in netlist.components:
        head = f"{comp.ref} {comp.kind} {comp.value}".strip()
        placed = [(pin, board.normalize(hole)) for pin, hole in comp.pins.items()
                  if hole != NC and board.has_hole(hole)]
        out.append(f"  {head}")
        if placed:
            out.append("    " + "  ".join(f"{pin}={hole}" for pin, hole in placed))
        open_pins = [pin for pin, hole in comp.pins.items() if hole == NC]
        if open_pins:
            out.append(f"    not placed (nc): {' '.join(open_pins)}")

    out.append("")
    out.append("JUMPERS")
    if not netlist.wires:
        out.append("  (none)")
    for a, b in netlist.wires:
        la, lb = strip_label(board, a), strip_label(board, b)
        joins = f"joins {la} to {lb}" if la != lb else f"within the {la}"
        out.append(f"  {a}-{b}  ({joins})")

    # Connected groups: pins and clips sharing one electrical node.
    members: dict[str, list[tuple[str, str]]] = {}
    for comp, pin, hole in netlist.placed_pins():
        members.setdefault(netlist.net_of(hole), []).append(
            (hole, f"{comp.ref} {pin}"))
    for ch, hole in sorted((analyzer or {}).items()):
        if board.has_hole(hole):
            canon = board.normalize(hole)
            members.setdefault(netlist.net_of(canon), []).append(
                (canon, f"clip {ch}"))
    out.append("")
    out.append("CONNECTED GROUPS (one group = one electrical node)")
    if not members:
        out.append("  (no pins placed)")
    groups = sorted(
        members.values(),
        key=lambda entries: min(_hole_sort(board, hole) for hole, _ in entries),
    )
    for i, entries in enumerate(groups, 1):
        strips = sorted({strip_label(board, hole) for hole, _ in entries})
        via = " + ".join(strips)
        if len(strips) > 1:
            via += " (jumper-joined)"
        out.append(f"  [{i}] {via}")
        for hole, what in sorted(entries, key=lambda e: _hole_sort(board, e[0])):
            out.append(f"      {hole:<5} {what}")

    if covers:
        out.append("")
        out.append("SITTING ON THE BOARD (view only, not connections)")
        for label, corner_a, corner_b in covers:
            out.append(f"  {label}: covers {corner_a}-{corner_b}")
    return "\n".join(out)

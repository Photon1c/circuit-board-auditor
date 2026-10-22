"""Draw a board, its wires, and its components as an SVG string."""
from __future__ import annotations

from html import escape

from core.board import Board, Rail
from core.nets import NC, Netlist

PITCH = 22
MARGIN = 40
HOLE_R = 4
PALETTE = [
    "#e6194b", "#3cb44b", "#4363d8", "#f58231", "#911eb4", "#42d4f4",
    "#f032e6", "#9a6324", "#469990", "#800000", "#808000", "#000075",
]


def _rail_label(rail: Rail) -> str:
    """Rail letter plus polarity, for example 'L+' or 'K-'."""
    name = rail.name.strip()
    if name.startswith("+"):
        return f"{rail.id}+"
    if name.startswith("-"):
        return f"{rail.id}-"
    return rail.id


def render_svg(board: Board, netlist: Netlist | None = None, *, breadvolt: bool = False) -> str:
    netlist = netlist or Netlist(board)
    pos = board.positions()
    xs = [x for x, _ in pos.values()]
    ys = [y for _, y in pos.values()]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    width = 2 * MARGIN + (max_x - min_x) * PITCH
    height = 2 * MARGIN + (max_y - min_y) * PITCH

    def pt_xy(x: float, y: float) -> tuple[float, float]:
        return MARGIN + (x - min_x) * PITCH, MARGIN + (y - min_y) * PITCH

    def pt(hole: str) -> tuple[float, float]:
        x, y = pos[board.normalize(hole)]
        return pt_xy(x, y)

    comp_color: dict[str, str] = {}
    hole_color: dict[str, str] = {}
    for i, comp in enumerate(netlist.components):
        color = PALETTE[i % len(PALETTE)]
        comp_color[comp.ref] = color
        for hole in comp.pins.values():
            if hole != NC and board.has_hole(hole):
                hole_color[board.normalize(hole)] = color

    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width:g} {height:g}" '
        f'width="{width:g}" height="{height:g}">'
    ]

    # Column letters and rail ids above the top of the board.
    # A split breadboard prints rows 1..n again on the right half.
    for col in board.columns:
        x, _ = pos[f"{col}1"]
        sx, sy = pt_xy(x, min_y)
        out.append(
            f'<text x="{sx:g}" y="{sy - 14:g}" '
            f'text-anchor="middle" font-size="12" fill="#555">{escape(col)}</text>'
        )
    for rail in board.rails:
        x, _ = pos[f"{rail.id}1"]
        sx, sy = pt_xy(x, min_y)
        out.append(
            f'<text x="{sx:g}" y="{sy - 14:g}" '
            f'text-anchor="middle" font-size="12" fill="#555">{escape(_rail_label(rail))}</text>'
        )
    split = board.kind == "breadboard" and len(board.strips) > 1
    row_x_left = MARGIN - 18
    row_x_right = MARGIN + (max_x - min_x) * PITCH + 18
    for row in range(1, board.rows + 1):
        _, y = pos[f"{board.columns[0]}{row}"]
        _, sy = pt_xy(min_x, y)
        out.append(
            f'<text x="{row_x_left:g}" y="{sy + 4:g}" '
            f'text-anchor="middle" font-size="11" fill="#555">{row}</text>'
        )
        if split:
            out.append(
                f'<text x="{row_x_right:g}" y="{sy + 4:g}" '
                f'text-anchor="middle" font-size="11" fill="#555">{row}</text>'
            )

    # Jumper wires.
    for a, b in netlist.wires:
        (x1, y1), (x2, y2) = pt(a), pt(b)
        out.append(
            f'<line x1="{x1:g}" y1="{y1:g}" x2="{x2:g}" y2="{y2:g}" '
            f'stroke="#333" stroke-width="3" stroke-linecap="round"/>'
        )

    # Component pins joined in order, plus a label at the first pin.
    for comp in netlist.components:
        pins = [pt(h) for h in comp.pins.values() if h != NC and board.has_hole(h)]
        color = comp_color[comp.ref]
        if len(pins) >= 2:
            points = " ".join(f"{x:g},{y:g}" for x, y in pins)
            out.append(
                f'<polyline points="{points}" fill="none" stroke="{color}" '
                f'stroke-width="3" opacity="0.7"/>'
            )
        if pins:
            x, y = pins[0]
            label = escape(f"{comp.ref} {comp.value}".strip())
            out.append(
                f'<text x="{x + 8:g}" y="{y - 8:g}" font-size="12" fill="{color}" '
                f'font-weight="bold">{label}</text>'
            )

    # Holes, colored by component when used. A BreadVolt shades the rows it covers.
    if breadvolt and board.breadvolt is not None:
        covered = board.breadvolt.covered_rows
        ys = [pos[f"{board.columns[0]}{row}"][1] for row in range(1, covered + 1)]
        x0, y0 = pt_xy(min_x - 0.7, min(ys) - 0.55)
        x1, y1 = pt_xy(max_x + 0.7, max(ys) + 0.55)
        rx, ry = min(x0, x1), min(y0, y1)
        out.append(
            f'<rect x="{rx:g}" y="{ry:g}" width="{abs(x1 - x0):g}" height="{abs(y1 - y0):g}" '
            f'fill="#f0b429" opacity="0.28" rx="8"/>'
        )
        out.append(
            f'<text x="{(rx + abs(x1 - x0) / 2):g}" y="{ry + 16:g}" text-anchor="middle" '
            f'font-size="13" fill="#8a5a00" font-weight="bold">BreadVolt</text>'
        )
    for hole in board.holes():
        x, y = pt(hole)
        used = hole in hole_color
        fill = hole_color.get(hole, "#c8c8c8")
        if breadvolt and board.breadvolt_zone(hole) == "pin" and not used:
            fill = "#e09f3e"
        radius = HOLE_R + (1 if used else 0)
        out.append(
            f'<circle cx="{x:g}" cy="{y:g}" r="{radius}" fill="{fill}">'
            f"<title>{hole}</title></circle>"
        )

    out.append("</svg>")
    return "".join(out)

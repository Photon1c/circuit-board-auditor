"""Draw a board, its wires, and its components as an SVG string."""
from __future__ import annotations

from html import escape

from core.board import Board, Rail
from core.nets import NC, Component, Netlist

PITCH = 22
MARGIN = 40
HOLE_R = 4
MARK_ARM = 3  # plus and minus sit inside the colored hole
DRAW_RESISTOR_BODY = False  # zigzag beside a resistor; off until the placement is settled
POSITIVE = "#d01212"  # positive rail and the jumpers that land on it
GROUND = "#1a1a1a"    # negative rail and the jumpers that land on it
SIGNAL = "#333333"    # a jumper that does not touch a supply rail
PALETTE = [
    "#e6194b", "#3cb44b", "#4363d8", "#f58231", "#911eb4", "#42d4f4",
    "#f032e6", "#9a6324", "#469990", "#800000", "#808000", "#000075",
]


def _rail_label(rail: Rail) -> str:
    """Rail letter plus polarity, for example 'L+' or 'K-'."""
    supply = _rail_supply(rail)
    if supply == "+":
        return f"{rail.id}+"
    if supply == "-":
        return f"{rail.id}-"
    return rail.id


def _rail_supply(rail: Rail) -> str | None:
    """'+' or '-' when the rail name starts with that sign."""
    name = rail.name.strip()
    if name.startswith("+"):
        return "+"
    if name.startswith("-"):
        return "-"
    return None


def _hole_supply(board: Board, hole: str) -> str | None:
    """'+' or '-' when the hole is on a supply rail, otherwise None."""
    letter = board.normalize(hole)[:1]
    for rail in board.rails:
        if rail.id == letter:
            return _rail_supply(rail)
    return None


def _used_rail_ids(board: Board, netlist: Netlist) -> set[str]:
    """Rail letters that a placed pin or jumper actually lands on."""
    holes: list[str] = []
    for a, b in netlist.wires:
        holes.extend((a, b))
    for comp in netlist.components:
        for hole in comp.pins.values():
            if hole != NC and board.has_hole(hole):
                holes.append(hole)
    used: set[str] = set()
    for hole in holes:
        letter = board.normalize(hole)[:1]
        if any(rail.id == letter for rail in board.rails):
            used.add(letter)
    return used


def _wire_supply(board: Board, a: str, b: str) -> str:
    """How to color a jumper: '+', '-', 'short', or 'signal'."""
    ends = {pole for pole in (_hole_supply(board, a), _hole_supply(board, b)) if pole}
    if ends == {"+"}:
        return "+"
    if ends == {"-"}:
        return "-"
    if len(ends) == 2:
        return "short"
    return "signal"


def _supply_color(supply: str) -> str:
    if supply == "+":
        return POSITIVE
    if supply == "-":
        return GROUND
    return SIGNAL


def _pin_key(name: str) -> str:
    key = name.strip().lower()
    if key.startswith("pin"):
        key = key[3:]
    return key


def polarity_pins(comp: Component) -> tuple[str, str] | None:
    """Return (positive pin, negative pin) when the drawing should mark them.

    LEDs and diodes use anode and cathode. Numbered legs follow pin 1 as the
    anode. Every capacitor uses + and -, or pin 1 as positive and pin 2 as
    negative. A resistor has no positive end.
    """
    kind = comp.kind.strip().lower()
    keyed = {_pin_key(name): name for name in comp.pins}

    def placed(name: str) -> str | None:
        original = keyed.get(name)
        if original is None or comp.pins[original] == NC:
            return None
        return original

    def first(*names: str) -> str | None:
        for name in names:
            found = placed(name)
            if found is not None:
                return found
        return None

    pos = neg = None
    if kind in {"led", "diode"}:
        pos = first("anode", "+", "plus", "pos", "positive", "a")
        neg = first("cathode", "-", "minus", "neg", "negative", "k")
        if pos is None or neg is None:
            pos, neg = first("1"), first("2")
    elif kind in {"capacitor", "cap"}:
        pos = first("+", "plus", "pos", "positive", "anode")
        neg = first("-", "minus", "neg", "negative", "cathode")
        if pos is None or neg is None:
            pos, neg = first("1"), first("2")
    if pos and neg and pos != neg:
        return pos, neg
    return None


def _mark_ink(fill: str) -> str:
    """Ink that stays readable on a component-colored hole."""
    hex_color = fill.lstrip("#")
    red, green, blue = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
    luminance = 0.2126 * red + 0.7152 * green + 0.0722 * blue
    return "#1f1b16" if luminance > 112 else "#fffdf8"


def _resistor_points(x1: float, y1: float, x2: float, y2: float) -> str:
    """A zigzag beside the lead, clear of the holes at each end."""
    dx, dy = x2 - x1, y2 - y1
    length = (dx * dx + dy * dy) ** 0.5
    if length < 1:
        return ""
    ux, uy = dx / length, dy / length
    px, py = -uy, ux
    side, amp = 9.0, 3.2
    half = min(8.0, length * 0.28)
    mid_x, mid_y = (x1 + x2) / 2, (y1 + y2) / 2
    steps = ((-1, 0), (-0.66, 1), (-0.33, -1), (0, 1), (0.33, -1), (0.66, 1), (1, 0))
    coords = []
    for along, wave in steps:
        x = mid_x + ux * half * along + px * (side + amp * wave)
        y = mid_y + uy * half * along + py * (side + amp * wave)
        coords.append(f"{x:g},{y:g}")
    return " ".join(coords)


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
        f'width="{width:g}" height="{height:g}" '
        f'font-family="Segoe UI, Arial, sans-serif">'
        f'<rect width="{width:g}" height="{height:g}" fill="#f4f0e6"/>'
    ]

    # Column letters and rail ids above the top of the board.
    for col in board.columns:
        x, _ = pos[f"{col}1"]
        sx, sy = pt_xy(x, min_y)
        out.append(
            f'<text x="{sx:g}" y="{sy - 14:g}" '
            f'text-anchor="middle" font-size="12" fill="#2a2622">{escape(col)}</text>'
        )
    for rail in board.rails:
        x, _ = pos[f"{rail.id}1"]
        sx, sy = pt_xy(x, min_y)
        supply = _rail_supply(rail)
        fill = _supply_color(supply or "signal") if supply else "#2a2622"
        out.append(
            f'<text x="{sx:g}" y="{sy - 14:g}" '
            f'text-anchor="middle" font-size="12" fill="{fill}">{escape(_rail_label(rail))}</text>'
        )
    # A supply rail is a colored bus: red for positive, black for ground.
    # The missing socket at a skipped hole is not a break, so the bus is one line.
    for rail in board.rails:
        supply = _rail_supply(rail)
        if supply is None:
            continue
        present = [n for n in range(1, rail.holes + 1) if board.has_hole(f"{rail.id}{n}")]
        if len(present) < 2:
            continue
        x1, y1 = pt(f"{rail.id}{present[0]}")
        x2, y2 = pt(f"{rail.id}{present[-1]}")
        out.append(
            f'<line data-rail="{escape(rail.id)}" data-supply="{supply}" '
            f'x1="{x1:g}" y1="{y1:g}" x2="{x2:g}" y2="{y2:g}" '
            f'stroke="{_supply_color(supply)}" stroke-width="8" stroke-linecap="round"/>'
        )
    # A split breadboard prints rows 1..n again on the right half.
    # "inverted" runs that edge the other way: beside row 1 is the last number.
    split = board.kind == "breadboard" and len(board.strips) > 1
    row_x_left = MARGIN - 18
    row_x_right = MARGIN + (max_x - min_x) * PITCH + 18
    for row in range(1, board.rows + 1):
        _, y = pos[f"{board.columns[0]}{row}"]
        _, sy = pt_xy(min_x, y)
        out.append(
            f'<text x="{row_x_left:g}" y="{sy + 4:g}" '
            f'text-anchor="middle" font-size="11" fill="#2a2622">{row}</text>'
        )
        if split:
            shown = board.rows + 1 - row if board.right_row_numbers == "inverted" else row
            out.append(
                f'<text x="{row_x_right:g}" y="{sy + 4:g}" '
                f'text-anchor="middle" font-size="11" fill="#2a2622">{shown}</text>'
            )

    # Jumper wires. A lead that lands on a supply rail takes that rail's color.
    for a, b in netlist.wires:
        (x1, y1), (x2, y2) = pt(a), pt(b)
        supply = _wire_supply(board, a, b)
        out.append(
            f'<line data-holes="{escape(a)}-{escape(b)}" data-supply="{supply}" '
            f'x1="{x1:g}" y1="{y1:g}" x2="{x2:g}" y2="{y2:g}" '
            f'stroke="{_supply_color(supply)}" stroke-width="3" stroke-linecap="round"/>'
        )

    # Component pins joined in order, plus a label at the first pin.
    for comp in netlist.components:
        pins = [pt(h) for h in comp.pins.values() if h != NC and board.has_hole(h)]
        color = comp_color[comp.ref]
        if len(pins) >= 2:
            points = " ".join(f"{x:g},{y:g}" for x, y in pins)
            out.append(
                f'<polyline points="{points}" fill="none" stroke="{color}" '
                f'stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>'
            )
        if pins:
            x, y = pins[0]
            label = escape(f"{comp.ref} {comp.value}".strip())
            out.append(
                f'<text x="{x + 8:g}" y="{y - 8:g}" font-size="12" fill="{color}" '
                f'font-weight="bold">{label}</text>'
            )
        if DRAW_RESISTOR_BODY and comp.kind.strip().lower() in {"resistor", "res"}:
            placed = [hole for hole in comp.pins.values() if hole != NC and board.has_hole(hole)]
            if len(placed) == 2:
                (x1, y1), (x2, y2) = pt(placed[0]), pt(placed[1])
                points = _resistor_points(x1, y1, x2, y2)
                if points:
                    out.append(
                        f'<polyline data-mark="resistor" data-ref="{escape(comp.ref)}" '
                        f'points="{points}" fill="none" stroke="{color}" stroke-width="2" '
                        f'stroke-linecap="round" stroke-linejoin="round">'
                        f"<title>{escape(comp.ref)}</title></polyline>"
                    )

    # The BreadVolt shade covers the terminal strips only. The rails stay visible
    # beside it, because that is where the module feeds power in.
    if breadvolt and board.breadvolt is not None and board.columns:
        covered = board.breadvolt.covered_rows
        col_x = [pos[f"{col}1"][0] for col in board.columns]
        row_y = [pos[f"{board.columns[0]}{row}"][1] for row in range(1, covered + 1)]
        x0, y0 = pt_xy(min(col_x) - 0.55, min(row_y) - 0.55)
        x1, y1 = pt_xy(max(col_x) + 0.55, max(row_y) + 0.55)
        rx, ry = min(x0, x1), min(y0, y1)
        out.append(
            f'<rect x="{rx:g}" y="{ry:g}" width="{abs(x1 - x0):g}" height="{abs(y1 - y0):g}" '
            f'fill="#e8d39a" rx="8"/>'
        )
        out.append(
            f'<text x="{(rx + abs(x1 - x0) / 2):g}" y="{ry + 16:g}" text-anchor="middle" '
            f'font-size="13" fill="#8a5a00" font-weight="bold">BreadVolt</text>'
        )
    for hole in board.holes():
        x, y = pt(hole)
        used = hole in hole_color
        fill = hole_color.get(hole, "#fffdf8")
        stroke = "#1f1b16" if used else "#4a453e"
        stroke_width = 1.4
        if breadvolt and board.breadvolt_zone(hole) == "pin" and not used:
            supply = _hole_supply(board, hole)
            if supply == "+":
                stroke = POSITIVE
                stroke_width = 2.4
            elif supply == "-":
                stroke = GROUND
                stroke_width = 2.4
        radius = HOLE_R + (1 if used else 0)
        out.append(
            f'<circle cx="{x:g}" cy="{y:g}" r="{radius}" fill="{fill}" '
            f'stroke="{stroke}" stroke-width="{stroke_width:g}">'
            f"<title>{hole}</title></circle>"
        )

    # A cross in the positive hole and a bar in the negative hole.
    for comp in netlist.components:
        pins = polarity_pins(comp)
        if pins is None:
            continue
        pos_name, neg_name = pins
        ends = ((pos_name, "plus", "+"), (neg_name, "minus", "-"))
        holes = [comp.pins[name] for name, _, _ in ends]
        if not all(board.has_hole(hole) for hole in holes):
            continue
        if board.normalize(holes[0]) == board.normalize(holes[1]):
            continue
        ink = _mark_ink(comp_color[comp.ref])
        for name, mark, sign in ends:
            hole = board.normalize(comp.pins[name])
            x, y = pt(hole)
            arm = MARK_ARM
            if mark == "plus":
                lines = (
                    f'<line x1="{x - arm:g}" y1="{y:g}" x2="{x + arm:g}" y2="{y:g}"/>'
                    f'<line x1="{x:g}" y1="{y - arm:g}" x2="{x:g}" y2="{y + arm:g}"/>'
                )
            else:
                lines = f'<line x1="{x - arm:g}" y1="{y:g}" x2="{x + arm:g}" y2="{y:g}"/>'
            out.append(
                f'<g data-mark="{mark}" data-hole="{escape(hole)}" stroke="{ink}" '
                f'stroke-width="1.7" stroke-linecap="round">'
                f"<title>{escape(f'{hole} {comp.ref} {sign}')}</title>{lines}</g>"
            )

    # Name the fed end of each rail. A positive rail the circuit never touches
    # reads (off): the battery is on the rail that the jumpers actually use.
    if breadvolt and board.breadvolt is not None:
        fed = [(rail, _rail_supply(rail)) for rail in board.rails]
        fed = [(rail, supply) for rail, supply in fed if supply]
        if fed:
            used = _used_rail_ids(board, netlist)
            located = []
            for rail, supply in fed:
                x, y = pt(f"{rail.id}1")
                located.append((x, y, supply, rail.id))
            mid_x = (min(item[0] for item in located) + max(item[0] for item in located)) / 2
            groups = (
                [item for item in located if item[0] <= mid_x],
                [item for item in located if item[0] > mid_x],
            )
            for group in groups:
                ordered = sorted(group)
                outer = 0 if ordered and ordered[0][0] <= mid_x else len(ordered) - 1
                for index, (x, y, supply, rail_id) in enumerate(ordered):
                    drop = 16 if index == outer else 28
                    sample = f"{rail_id}6" if board.has_hole(f"{rail_id}6") else f"{rail_id}{fed[0][0].holes}"
                    at_bottom = y > pt(sample)[1]
                    y_text = y + drop if at_bottom else y - drop
                    unused = bool(used) and rail_id not in used and supply == "+"
                    word = "(off)" if unused else ("+9V" if supply == "+" else "GND")
                    fill = "#6b6458" if unused else _supply_color(supply)
                    out.append(
                        f'<text data-rail="{escape(rail_id)}" x="{x:g}" y="{y_text:g}" '
                        f'text-anchor="middle" font-size="11" font-weight="bold" '
                        f'fill="{fill}">{word}</text>'
                    )

    out.append("</svg>")
    return "".join(out)

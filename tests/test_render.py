import re
from pathlib import Path

from core.board import Board
from core.entry import parse_components, parse_wires
from core.nets import Component, Netlist, netlist_from_dict
from core.presets import LED_CHASER
from core.render import MARK_ARM, MARGIN, PITCH, _resistor_points, polarity_pins, render_svg

ROOT = Path(__file__).resolve().parents[1]


def breadboard() -> Board:
    return Board.load(ROOT / "boards" / "breadboard_170.json")


def test_svg_draws_every_hole():
    svg = render_svg(breadboard())
    assert svg.count("<circle") == 170
    assert 'width="100%"' not in svg
    assert 'width="' in svg and 'height="' in svg
    assert 'fill="#f4f0e6"' in svg
    assert "opacity=" not in svg


def test_perfboard_svg_draws_every_hole():
    board = Board.load(ROOT / "boards" / "patikil_perfboard_144.json")
    svg = render_svg(board)
    assert svg.count("<circle") == 144
    assert 'fill="#f4f0e6"' in svg
    assert "opacity=" not in svg


def test_component_label_is_escaped():
    b = breadboard()
    nl = netlist_from_dict(b, {"components": [
        {"ref": "R<1>", "kind": "resistor", "value": "1k", "pins": {"1": "A1", "2": "A5"}},
    ]})
    svg = render_svg(b, nl)
    assert "R&lt;1&gt; 1k" in svg
    assert "<R<1>" not in svg


def test_wire_is_drawn():
    b = breadboard()
    nl = netlist_from_dict(b, {"wires": [["E1", "F1"]]})
    assert "<line" in render_svg(b, nl)


def _hole_px(board: Board, hole: str) -> tuple[float, float]:
    pos = board.positions()
    xs = [x for x, _ in pos.values()]
    ys = [y for _, y in pos.values()]
    x, y = pos[board.normalize(hole)]
    return MARGIN + (x - min(xs)) * PITCH, MARGIN + (y - min(ys)) * PITCH


def test_polarity_follows_the_pin_names():
    led = Component("D1", "led", {"anode": "A1", "cathode": "A2"}, "green")
    numbered = Component("D2", "LED", {"PIN1": "A1", "PIN2": "A2"})
    diode = Component("D3", "diode", {"anode": "B1", "cathode": "B2"}, "1N4148")
    named_cap = Component("C1", "capacitor", {"+": "A3", "-": "A6"}, "10n")
    electrolytic = Component("C2", "cap", {"PIN1": "A3", "PIN2": "A2"}, "100µF")
    ceramic = Component("C3", "cap", {"1": "G5", "2": "G6"}, "10n")
    resistor = Component("R1", "resistor", {"1": "A1", "2": "A5"}, "1k")
    assert polarity_pins(led) == ("anode", "cathode")
    assert polarity_pins(numbered) == ("PIN1", "PIN2")
    assert polarity_pins(diode) == ("anode", "cathode")
    assert polarity_pins(named_cap) == ("+", "-")
    assert polarity_pins(electrolytic) == ("PIN1", "PIN2")
    assert polarity_pins(ceramic) == ("1", "2")
    assert polarity_pins(resistor) is None


def test_positive_terminal_holds_a_cross_and_the_negative_a_bar():
    b = breadboard()
    nl = netlist_from_dict(b, {"components": [
        {"ref": "D1", "kind": "led", "value": "green", "pins": {"anode": "A1", "cathode": "A2"}},
    ]})
    svg = render_svg(b, nl)
    x, y = _hole_px(b, "A1")
    block = re.search(r'<g data-mark="plus" data-hole="A1".*?</g>', svg)
    assert block is not None
    plus = block.group(0)
    assert f'x1="{x - MARK_ARM:g}"' in plus and f'y2="{y + MARK_ARM:g}"' in plus
    assert plus.count("<line") == 2
    cx, cy = _hole_px(b, "A2")
    minus = re.search(r'<g data-mark="minus" data-hole="A2".*?</g>', svg)
    assert minus is not None
    assert minus.group(0).count("<line") == 1
    assert f'y1="{cy:g}"' in minus.group(0)
    assert f'x1="{cx - MARK_ARM:g}"' in minus.group(0)
    assert "opacity=" not in svg


def test_resistor_zigzag_is_not_drawn():
    b = breadboard()
    nl = netlist_from_dict(b, {"components": [
        {"ref": "R1", "kind": "resistor", "value": "470", "pins": {"1": "H1", "2": "H3"}},
    ]})
    svg = render_svg(b, nl)
    assert 'data-mark="resistor"' not in svg
    assert 'data-mark="plus"' not in svg
    assert _resistor_points(0, 0, 0, 44)


def test_analyzer_overlay_draws_clips_leads_and_box():
    b = breadboard()
    svg = render_svg(b, analyzer={"CH0": "B5", "CH1": "B11", "GND": "A13"})
    assert svg.count('data-analyzer-clip=') == 3
    assert svg.count('data-analyzer-lead=') == 3
    assert 'data-analyzer-panel="1"' in svg
    assert "LOGIC ANALYZER" in svg
    assert 'data-analyzer-clip="CH0" data-hole="B5"' in svg
    assert 'data-analyzer-clip="GND" data-hole="A13"' in svg


def test_analyzer_overlay_absent_by_default_and_ignores_unknown_holes():
    b = breadboard()
    assert "data-analyzer" not in render_svg(b)
    svg = render_svg(b, analyzer={"CH0": "Z99", "CH1": "B11"})
    assert 'data-analyzer-clip="CH1"' in svg
    assert "CH0" not in svg


def test_covers_shade_named_zones_and_skip_unknown_holes():
    b = breadboard()
    svg = render_svg(b, covers=(("Logic analyzer", "A1", "C3"),
                                ("Module", "E5", "G7"),
                                ("Nowhere", "Z1", "Z9")))
    assert svg.count("data-cover=") == 2
    assert 'data-cover="Logic analyzer"' in svg
    assert 'data-cover="Module"' in svg
    assert "Nowhere" not in svg
    # View only: no shade by default, and holes are unchanged.
    assert "data-cover=" not in render_svg(b)
    assert render_svg(b).count("<circle") == svg.count("<circle")


def test_hover_text_names_holes_wires_parts_clips_and_covers():
    b = breadboard()
    nl = netlist_from_dict(b, {
        "components": [{"ref": "R1", "kind": "resistor", "value": "1k",
                        "pins": {"1": "A5", "2": "A6"}}],
        "wires": [["E6", "F6"]],
    })
    svg = render_svg(b, nl, analyzer={"CH0": "B5"},
                     covers=(("Logic analyzer", "A1", "C3"),))
    # Occupied hole says what sits in it; empty hole says its strip.
    assert "<title>A5 - R1 1 (R1 resistor 1k)</title>" in svg
    assert "empty, row 7 A-E strip" in svg
    assert "<title>jumper J1 E6-F6</title>" in svg
    assert 'data-wire-label="J1"' in svg
    assert "R1 1k: 1=A5, 2=A6" in svg
    assert "analyzer clip CH0 on B5 (view only)" in svg
    assert "Logic analyzer: covers A1-C3" in svg


def test_in_use_strips_are_tinted_ground_strips_black():
    b = breadboard()
    nl = netlist_from_dict(b, {
        "components": [{"ref": "V1", "kind": "source", "value": "5V",
                        "pins": {"+": "A1", "-": "A2"}}],
        "wires": [["A2", "A7"]],
    })
    svg = render_svg(b, nl)
    # Row 2 strip holds the source - pin and the ground jumper end.
    assert 'data-strip="row2 A-E"' in svg
    assert 'data-strip="row7 A-E"' in svg  # jumper's far end strip
    ground_strip = re.search(r'<rect data-strip="row2 A-E"[^>]*fill="#c4c4c4"', svg)
    assert ground_strip, "ground strip should tint grey"
    # An empty board tints nothing.
    assert "data-strip=" not in render_svg(b)


def test_distant_pins_get_no_fake_wire_outline():
    b = breadboard()
    nl = netlist_from_dict(b, {
        "components": [
            {"ref": "M1", "kind": "module", "value": "X",
             "pins": {"D4": "A1", "D5": "A2", "GND": "J7"}},
            {"ref": "V1", "kind": "source", "value": "5V",
             "pins": {"+": "A4", "-": "A10"}},
            {"ref": "R1", "kind": "resistor", "value": "1k",
             "pins": {"1": "C1", "2": "C2"}},
        ],
    })
    svg = render_svg(b, nl)
    # Only the close two-legged resistor keeps its lead line.
    assert svg.count("<polyline") == 1
    assert "R1 1k: 1=C1, 2=C2" in svg


def test_ground_jumper_ends_are_solid_black():
    b = breadboard()
    nl = netlist_from_dict(b, {
        "components": [{"ref": "V1", "kind": "source", "value": "5V",
                        "pins": {"+": "A1", "-": "A2"}}],
        "wires": [["A2", "A7"], ["A1", "A9"]],
    })
    svg = render_svg(b, nl)
    # A7 ends the ground jumper (from the source - pin): solid black.
    assert re.search(r'fill="#1a1a1a"[^>]*><title>A7 - ground jumper end', svg)
    # The source - pin itself (A2) is ground too: black, not part-colored.
    assert re.search(r'fill="#1a1a1a"[^>]*><title>A2 - V1 -', svg)
    # A9 ends a plain signal jumper: stays an open dot.
    assert re.search(r'fill="#fffdf8"[^>]*><title>A9 - empty', svg)


def test_analyzer_does_not_change_the_board_or_netlist():
    b = breadboard()
    nl = netlist_from_dict(b, {"wires": [["E1", "F1"]]})
    plain = render_svg(b, nl)
    with_analyzer = render_svg(b, nl, analyzer={"CH0": "B5"})
    # Same holes and wires; the overlay only adds its own elements and
    # widens the canvas for the analyzer box.
    assert plain.count("<circle") == with_analyzer.count("<circle") - 2
    assert 'data-holes="E1-F1"' in with_analyzer


def test_led_chaser_marks_every_led_and_capacitor():
    board = Board.load(ROOT / "boards" / f"{LED_CHASER.board}.json")
    nl = Netlist(board, parse_components(LED_CHASER.lines), parse_wires(LED_CHASER.wires))
    svg = render_svg(board, nl)
    assert 'data-mark="plus" data-hole="J31"' in svg
    assert 'data-mark="minus" data-hole="J30"' in svg
    assert 'data-mark="plus" data-hole="A3"' in svg
    assert 'data-mark="minus" data-hole="A2"' in svg
    assert 'data-mark="plus" data-hole="G5"' in svg
    assert 'data-mark="minus" data-hole="G6"' in svg
    assert 'data-mark="plus" data-hole="G8"' in svg
    assert 'data-mark="minus" data-hole="G7"' in svg
    assert svg.count('data-mark="plus"') == 6
    assert 'data-mark="resistor"' not in svg

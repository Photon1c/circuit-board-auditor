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

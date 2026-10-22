from pathlib import Path

from core.board import Board
from core.nets import netlist_from_dict
from core.render import render_svg

ROOT = Path(__file__).resolve().parents[1]


def breadboard() -> Board:
    return Board.load(ROOT / "boards" / "breadboard_170.json")


def test_svg_draws_every_hole():
    assert render_svg(breadboard()).count("<circle") == 170


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

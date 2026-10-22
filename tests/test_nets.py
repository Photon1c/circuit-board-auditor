from pathlib import Path

from core.board import Board
from core.nets import Netlist, netlist_from_dict

ROOT = Path(__file__).resolve().parents[1]

# LED + 150 ohm + 1k pot as a rheostat, on the 170-hole breadboard.
# Strips used: row1-left (A1,B1), row2-left (B2,C2), row6-left (C6,D6), row17-left (A17,D17).
EXAMPLE = {
    "components": [
        {"ref": "V1", "kind": "source", "value": "5V", "pins": {"+": "A1", "-": "A17"}},
        {"ref": "P1", "kind": "pot", "value": "1k", "pins": {"A": "B1", "W": "B2", "B": "nc"}},
        {"ref": "R1", "kind": "resistor", "value": "150R", "pins": {"1": "C2", "2": "C6"}},
        {"ref": "D1", "kind": "led", "value": "green", "pins": {"anode": "D6", "cathode": "D17"}},
    ],
    "wires": [],
}


def breadboard() -> Board:
    return Board.load(ROOT / "boards" / "breadboard_170.json")


def test_strip_continuity_on_breadboard():
    nl = Netlist(breadboard())
    assert nl.continuity("A1", "E1")
    assert nl.continuity("F1", "J1")
    assert not nl.continuity("E1", "F1")   # center gap
    assert not nl.continuity("A1", "A2")   # different rows


def test_jumper_wire_joins_strips():
    nl = netlist_from_dict(breadboard(), {"wires": [["E1", "F1"]]})
    assert nl.continuity("E1", "F1")
    assert not nl.continuity("A1", "A2")


def test_example_circuit_nets():
    nl = netlist_from_dict(breadboard(), EXAMPLE)
    assert nl.continuity("A1", "B1")        # +5 V to pot end A
    assert nl.continuity("B2", "C2")        # wiper to R1 pin 1
    assert nl.continuity("C6", "D6")        # R1 pin 2 to LED anode
    assert nl.continuity("A17", "D17")      # GND to LED cathode
    assert not nl.continuity("B2", "C6")    # wiper net is separate from LED net
    assert not nl.continuity("B3", "B2")    # pot end B stays open


def test_pin_lookup_uses_canonical_names():
    nl = netlist_from_dict(breadboard(), EXAMPLE)
    assert nl.net_of("c2") == nl.net_of("B2")

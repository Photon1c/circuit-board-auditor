"""The plain-text layout (core/summary.py) spells the drawing out in words."""
from pathlib import Path

from core.board import Board
from core.nets import Netlist
from core.presets import ULTRASONIC_DEYUE_ANALYZER, place_on
from core.summary import audit_dict, describe_layout, legend_lines, strip_label

ROOT = Path(__file__).resolve().parents[1]


def deyue_netlist():
    board = Board.load(ROOT / "boards" / "deyue_400_solderless.json")
    comps, wires = place_on(board, ULTRASONIC_DEYUE_ANALYZER)
    return board, Netlist(board, comps, wires)


def group_block(text: str, needle: str) -> str:
    """The [n] connected-group block containing needle."""
    blocks = text.split("CONNECTED GROUPS")[1].split("  [")
    for block in blocks:
        if needle in block:
            return block
    raise AssertionError(f"no group contains {needle!r}")


def test_parts_and_jumpers_are_spelled_out():
    board, nl = deyue_netlist()
    text = describe_layout(board, nl)
    assert "M1 module XIAO-ESP32-C6" in text
    assert "D4=C22" in text and "D5=C23" in text
    assert "not placed (nc):" in text  # the unused XIAO pins
    assert "R1 resistor 1k" in text and "1=A25" in text and "2=A26" in text
    assert "E26-A23" in text and "joins row 26 A-E strip to row 23 A-E strip" in text


def test_connected_groups_name_every_pin_on_the_node():
    board, nl = deyue_netlist()
    text = describe_layout(
        board, nl,
        analyzer={"CH0": "F1", "CH1": "F2", "CH2": "F3", "GND": "F11"},
        covers=ULTRASONIC_DEYUE_ANALYZER.covers)
    trig = group_block(text, "M1 D4")
    assert "M2 TRIG" in trig and "clip CH0" in trig
    echo = group_block(text, "M2 ECHO")
    assert "R1 1" in echo and "clip CH1" in echo
    assert "M1 D5" not in echo  # the divider stands between ECHO and D5
    junction = group_block(text, "M1 D5")
    assert "R1 2" in junction and "R2 1" in junction and "clip CH2" in junction
    ground = group_block(text, "M2 GND")
    assert "R2 2" in ground and "M1 GND" in ground and "clip GND" in ground
    assert "Logic analyzer: covers E1-F11" in text
    assert "XIAO ESP32-C6: covers D18-H24" in text
    # The breakout jumpers are spelled out as jumpers too.
    assert "G1-A22" in text and "G11-M10" in text and "M25-E27" in text
    assert "I19-B27" in text  # XIAO GND pin down to the ground row


def test_audit_dict_lists_every_wire_with_its_net():
    board, nl = deyue_netlist()
    audit = audit_dict(
        board, nl,
        analyzer={"CH0": "F1", "CH1": "F2", "CH2": "F3", "GND": "F11"},
        covers=ULTRASONIC_DEYUE_ANALYZER.covers)
    by_id = {w["id"]: w for w in audit["wires"]}
    assert [w["id"] for w in audit["wires"]] == [
        "J1", "J2", "J3", "J4", "J5", "J6", "J7"]
    gnd_wire = by_id["J7"]
    assert (gnd_wire["from"], gnd_wire["to"]) == ("I19", "B27")
    assert gnd_wire["ground"] is True
    assert {"hole": "I19", "what": "M1 GND"} in gnd_wire["net_members"]
    assert by_id["J5"]["ground"] is True  # G11-M10 analyzer ground
    assert by_id["J6"]["ground"] is True  # M25-E27 rail tie
    trig_wire = by_id["J2"]
    assert (trig_wire["from"], trig_wire["to"]) == ("G1", "A22")
    assert trig_wire["ground"] is False
    assert {"hole": "C22", "what": "M1 D4"} in trig_wire["net_members"]
    ground_groups = [g for g in audit["groups"] if g["ground"]]
    assert len(ground_groups) == 1
    assert {"hole": "A27", "what": "M2 GND"} in ground_groups[0]["members"]
    assert {"hole": "F11", "what": "clip GND"} in ground_groups[0]["members"]
    assert audit["covers"][0] == {"label": "Logic analyzer", "from": "E1", "to": "F11"}
    # The text panel numbers jumpers with the same ids.
    text = describe_layout(board, nl)
    assert "J7 I19-B27" in text and "J2 G1-A22" in text


def test_strip_label_and_legend_read_in_words():
    board, _nl = deyue_netlist()
    assert strip_label(board, "C22") == "row 22 A-E strip"
    assert strip_label(board, "H22") == "row 22 F-J strip"
    legend = "\n".join(legend_lines(board))
    assert "Solid colored dot" in legend
    assert "never treats a part as connecting its own pins" in legend
    assert "A-E and F-J" in legend or "A-E" in legend

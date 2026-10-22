from pathlib import Path

import pytest

from core.board import Board
from core.checks import led_current_ma, run_checks
from core.nets import netlist_from_dict
from tests.test_nets import EXAMPLE

ROOT = Path(__file__).resolve().parents[1]


def breadboard() -> Board:
    return Board.load(ROOT / "boards" / "breadboard_170.json")


def codes(issues):
    return {i.code for i in issues}


def test_example_circuit_passes_all_checks():
    nl = netlist_from_dict(breadboard(), EXAMPLE)
    assert run_checks(nl) == []


def test_resistor_with_both_legs_on_one_strip_is_a_short():
    data = {"components": [
        {"ref": "R1", "kind": "resistor", "pins": {"1": "C2", "2": "A2"}},
    ]}
    issues = run_checks(netlist_from_dict(breadboard(), data))
    assert "pin_short" in codes(issues)
    assert any(i.severity == "error" for i in issues)


def test_supply_short_detected():
    data = {"components": [
        {"ref": "V1", "kind": "source", "pins": {"+": "A1", "-": "E1"}},
    ]}
    assert "supply_short" in codes(run_checks(netlist_from_dict(breadboard(), data)))


def test_dangling_pin_is_a_warning():
    data = {"components": [
        {"ref": "R1", "kind": "resistor", "pins": {"1": "A5", "2": "F5"}},
    ]}
    issues = run_checks(netlist_from_dict(breadboard(), data))
    dangling = [i for i in issues if i.code == "dangling_pin"]
    assert len(dangling) == 2
    assert all(i.severity == "warning" for i in dangling)


def test_two_parts_in_one_hole_conflict():
    data = {"components": [
        {"ref": "R1", "kind": "resistor", "pins": {"1": "A1", "2": "A5"}},
        {"ref": "R2", "kind": "resistor", "pins": {"1": "A1", "2": "A9"}},
    ]}
    assert "hole_conflict" in codes(run_checks(netlist_from_dict(breadboard(), data)))


def test_off_board_hole_reported():
    data = {"components": [
        {"ref": "R1", "kind": "resistor", "pins": {"1": "A18", "2": "A5"}},
    ]}
    assert "invalid_hole" in codes(run_checks(netlist_from_dict(breadboard(), data)))


def test_led_current_single_led_example():
    # 5 V, green LED Vf 3.0 V, 150 ohm: about 13.3 mA
    assert led_current_ma(5.0, 3.0, 150) == pytest.approx(13.33, abs=0.05)


def test_led_current_with_uln2003_drop():
    # 5 V, Vf 3.1 V, 100 ohm, ULN2003 drop 1.0 V: about 9 mA
    assert led_current_ma(5.0, 3.1, 100, drop_v=1.0) == pytest.approx(9.0, abs=0.05)


def test_led_current_rejects_zero_resistance():
    with pytest.raises(ValueError):
        led_current_ma(5.0, 3.0, 0)

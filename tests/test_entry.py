import pytest

from core.entry import parse_component, parse_components, parse_wire
from core.nets import NC


def test_component_with_value_and_pins():
    c = parse_component("R1 resistor 470k 1=E1 2=J1")
    assert (c.ref, c.kind, c.value) == ("R1", "resistor", "470k")
    assert c.pins == {"1": "E1", "2": "J1"}


def test_component_without_value_and_with_nc_pin():
    c = parse_component("P1 pot 1=A1 W=B2 B=nc")
    assert c.value == ""
    assert c.pins["B"] == NC


def test_component_rejects_missing_pins():
    with pytest.raises(ValueError):
        parse_component("R1 resistor 470k")


def test_component_rejects_pin_without_equals():
    with pytest.raises(ValueError):
        parse_component("R1 resistor 1E1")


def test_wire_accepts_space_or_hyphen():
    assert parse_wire("E1 F1") == ("E1", "F1")
    assert parse_wire("e1-f1") == ("E1", "F1")


def test_wire_rejects_single_hole():
    with pytest.raises(ValueError):
        parse_wire("E1")


def test_each_line_adds_a_component():
    text = "R1 resistor 1k 1=E1 2=J1\n\nC1 CAP 100u PIN1=A3 PIN2=A2\n"
    comps = parse_components(text)
    assert [(c.ref, c.kind, c.value) for c in comps] == [
        ("R1", "resistor", "1k"),
        ("C1", "cap", "100u"),
    ]
    assert comps[1].pins == {"PIN1": "A3", "PIN2": "A2"}


def test_bad_batch_line_names_its_number():
    with pytest.raises(ValueError, match="Line 2"):
        parse_components("R1 resistor 1k 1=E1 2=J1\nnot-a-component\n")

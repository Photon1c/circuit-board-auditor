import pytest

from core.entry import parse_component, parse_wire
from core.parts import PARTS


def test_every_help_example_parses():
    for part in PARTS:
        if part.kind == "wire":
            assert len(parse_wire(part.example)) == 2
        else:
            comp = parse_component(part.example)
            assert comp.kind == part.kind


def test_help_lists_each_kind_once():
    kinds = [p.kind for p in PARTS]
    assert len(kinds) == len(set(kinds))


def test_bad_example_would_fail():
    with pytest.raises(ValueError):
        parse_component("R1 resistor 470k")

from pathlib import Path

import pytest

from core.board import Board

ROOT = Path(__file__).resolve().parents[1]


def load(name: str) -> Board:
    return Board.load(ROOT / "boards" / name)


def test_breadboard_hole_count_and_bounds():
    b = load("breadboard_170.json")
    assert len(list(b.holes())) == 170
    assert b.has_hole("A17") and b.has_hole("J1")
    assert not b.has_hole("A18")
    assert not b.has_hole("K1")


def test_breadboard_strips_and_center_gap():
    b = load("breadboard_170.json")
    assert b.strip_id("A1") == b.strip_id("E1")
    assert b.strip_id("F1") == b.strip_id("J1")
    assert b.strip_id("E1") != b.strip_id("F1")  # center gap
    assert b.strip_id("A1") != b.strip_id("A2")


def test_names_are_case_insensitive_and_strict():
    b = load("breadboard_170.json")
    assert b.normalize("e1") == "E1"
    with pytest.raises(ValueError):
        b.normalize("A18")
    with pytest.raises(ValueError):
        b.normalize("hello")


def test_gennel_stripboard_vertical_strips():
    b = load("gennel_stripboard_368.json")
    assert len(list(b.holes())) == 368
    assert b.strip_id("A1") == b.strip_id("A16")
    assert b.strip_id("A1") != b.strip_id("B1")


def test_patikil_perfboard_is_isolated():
    b = load("patikil_perfboard_144.json")
    assert len(list(b.holes())) == 144
    assert b.strip_id("A1") != b.strip_id("A2")
    assert b.strip_id("A1") != b.strip_id("B1")


def test_stripboard_break_splits_strip():
    b = Board.from_dict({
        "name": "test", "type": "stripboard", "rows": 10,
        "columns": ["A", "B"], "strip_orientation": "vertical",
        "breaks": [{"column": "A", "between_rows": [4, 5]}],
    })
    assert b.strip_id("A1") == b.strip_id("A4")
    assert b.strip_id("A4") != b.strip_id("A5")
    assert b.strip_id("A5") == b.strip_id("A10")
    assert b.strip_id("B1") == b.strip_id("B10")


def test_bad_board_type_rejected():
    with pytest.raises(ValueError):
        Board.from_dict({"name": "x", "type": "pcb", "rows": 1, "columns": ["A"]})

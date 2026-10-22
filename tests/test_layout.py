from pathlib import Path

from core.board import Board

ROOT = Path(__file__).resolve().parents[1]


def load(name: str) -> Board:
    return Board.load(ROOT / "boards" / name)


def test_breadboard_a17_is_bottom_left_and_row1_is_top():
    pos = load("breadboard_170.json").positions()
    assert pos["A1"] == (0.0, 0.0)
    assert pos["A17"] == (0.0, 16.0)


def test_breadboard_center_gap_is_wider_than_one_column():
    pos = load("breadboard_170.json").positions()
    assert pos["E1"][0] - pos["D1"][0] == 1.0
    assert pos["F1"][0] - pos["E1"][0] == 2.0


def test_gennel_a1_is_top_right():
    pos = load("gennel_stripboard_368.json").positions()
    assert pos["A1"] == (22.0, 0.0)
    assert pos["W1"] == (0.0, 0.0)


def test_patikil_a1_is_bottom_left_and_row1_is_bottom():
    pos = load("patikil_perfboard_144.json").positions()
    assert pos["A1"] == (0.0, 11.0)
    assert pos["A12"] == (0.0, 0.0)

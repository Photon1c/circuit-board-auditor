import re
from pathlib import Path

import pytest

from core.board import Board
from core.checks import run_checks
from core.entry import parse_components, parse_wires
from core.nets import Netlist, netlist_from_dict
from core.presets import LED_CHASER
from core.render import GROUND, POSITIVE, render_svg

ROOT = Path(__file__).resolve().parents[1]
JOS = "california_jos_breadboard_870_solderless.json"


def load(name: str) -> Board:
    return Board.load(ROOT / "boards" / name)


def jos() -> Board:
    return load(JOS)


def _breadboard(rails: list, rows: int = 50) -> Board:
    return Board.from_dict({
        "name": "test",
        "type": "breadboard",
        "rows": rows,
        "columns": ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J"],
        "strips": [["A", "B", "C", "D", "E"], ["F", "G", "H", "I", "J"]],
        "rails": rails,
    })


def test_jos_board_reports_every_row_and_keeps_strip_gaps():
    b = jos()
    assert len(list(b.holes())) == 630 + 4 * 62
    assert b.strip_id("A1") == b.strip_id("E1")
    assert b.strip_id("E1") != b.strip_id("F1")
    assert b.strip_id("K1") == b.strip_id("K63")
    pos = b.positions()
    for n in range(1, 64):
        if n == 5:
            assert f"K{n}" not in pos
            continue
        assert pos[f"K{n}"][1] == pos[f"J{n}"][1]
        assert pos[f"M{n}"][1] == pos[f"A{n}"][1]


def test_jos_columns_read_j_to_a_from_the_left():
    pos = jos().positions()
    letters = list("JIHGFEDCBA")
    xs = [pos[f"{col}1"][0] for col in letters]
    assert xs == sorted(xs)
    assert pos["J1"][0] < pos["A1"][0]
    assert pos["E1"][0] - pos["F1"][0] == 2
    assert pos["L1"][0] < pos["J1"][0]
    assert pos["A1"][0] < pos["M1"][0]


def test_one_segment_connects_the_whole_rail():
    nl = Netlist(jos())
    assert nl.continuity("K1", "K63")
    assert nl.continuity("K1", "K51")
    assert nl.continuity("K4", "K6")
    assert not nl.continuity("K1", "L1")
    assert not nl.continuity("K1", "A1")


def test_split_segments_break_the_rail():
    b = _breadboard([{
        "id": "K",
        "name": "+ left",
        "holes": 50,
        "segments": [[1, 25], [26, 50]],
    }])
    nl = Netlist(b)
    assert nl.continuity("K1", "K25")
    assert not nl.continuity("K25", "K26")


def test_rail_names_normalize_and_reject_out_of_range():
    b = jos()
    assert b.normalize("k1") == "K1"
    assert b.has_hole("K51") and b.has_hole("K63")
    assert not b.has_hole("K5") and not b.has_hole("N5")
    assert not b.has_hole("K64")


def test_rail_id_cannot_match_a_column():
    with pytest.raises(ValueError, match="A"):
        _breadboard([{"id": "A", "name": "+ left", "holes": 10}])


def test_overlapping_segments_rejected():
    with pytest.raises(ValueError, match="K"):
        _breadboard([{
            "id": "K",
            "name": "+ left",
            "holes": 50,
            "segments": [[1, 30], [25, 50]],
        }])


def test_rail_positions_sit_outside_the_main_grid():
    b = jos()
    pos = b.positions()
    last_x = max(pos[f"{col}1"][0] for col in b.columns)
    for rail in b.rails:
        xs = {pos[f"{rail.id}{n}"][0] for n in range(1, rail.holes + 1) if n not in rail.skip}
        assert len(xs) == 1
        x = xs.pop()
        if "left" in rail.name.lower():
            assert x < 0
        else:
            assert x > last_x


def test_svg_draws_main_grid_and_rail_holes():
    assert render_svg(jos()).count("<circle") == 630 + 4 * 62


def test_l_and_n_are_positive_k_and_m_are_negative():
    b = jos()
    by_id = {rail.id: rail.name for rail in b.rails}
    assert by_id["K"].startswith("-")
    assert by_id["L"].startswith("+")
    assert by_id["M"].startswith("-")
    assert by_id["N"].startswith("+")
    svg = render_svg(b)
    for label in ("K-", "L+", "M-", "N+"):
        assert f">{label}</text>" in svg


def test_split_board_inverts_row_numbers_on_the_right():
    svg = render_svg(jos())
    labels = [
        (float(x), float(y), int(row))
        for x, y, row in re.findall(
            r'<text x="([^"]+)" y="([^"]+)" text-anchor="middle" font-size="11"[^>]*>(\d+)</text>',
            svg,
        )
    ]
    by_y: dict[float, list[tuple[float, int]]] = {}
    for x, y, row in labels:
        by_y.setdefault(y, []).append((x, row))
    assert len(by_y) == 63
    for points in by_y.values():
        assert len(points) == 2
        left, right = sorted(points)
        assert left[0] != right[0]
        assert left[1] + right[1] == 64


def test_supply_short_on_one_rail():
    data = {"components": [
        {"ref": "V1", "kind": "source", "pins": {"+": "K1", "-": "K63"}},
    ]}
    issues = run_checks(netlist_from_dict(jos(), data))
    assert "supply_short" in {i.code for i in issues}


def test_jos_skips_rail_hole_five_and_describes_a_breadvolt():
    b = jos()
    assert b.breadvolt is not None
    assert b.breadvolt.covered_rows == 10
    assert b.breadvolt.pin_rows == 4
    assert b.breadvolt_zone("K4") == "pin"
    assert b.breadvolt_zone("A10") == "covered"
    assert b.breadvolt_zone("A11") is None
    assert b.breadvolt_zone("N6") == "covered"


def test_breadvolt_blocks_covered_rows_and_rail_pins():
    data = {"components": [
        {"ref": "R1", "kind": "resistor", "value": "1k", "pins": {"1": "A2", "2": "F2"}},
    ], "wires": [["F11", "N2"]]}
    issues = run_checks(netlist_from_dict(jos(), data), breadvolt=True)
    messages = [i.message for i in issues if i.code == "breadvolt"]
    assert any("A2" in m and "under the BreadVolt" in m for m in messages)
    assert any("N2" in m and "BreadVolt pin" in m for m in messages)
    off = run_checks(netlist_from_dict(jos(), data))
    assert not any(i.code == "breadvolt" for i in off)


def test_svg_shades_the_breadvolt_when_asked():
    svg = render_svg(jos(), breadvolt=True)
    assert "BreadVolt" in svg
    assert ">BreadVolt</text>" not in render_svg(jos())
    assert svg.count(">+9V</text>") == 2
    assert svg.count(">GND</text>") == 2
    assert ">+9V</text>" not in render_svg(jos())


def test_supply_rails_and_their_jumpers_are_red_or_black():
    board = jos()
    bare = render_svg(board)
    assert 'data-rail="L" data-supply="+"' in bare
    assert 'data-rail="N" data-supply="+"' in bare
    assert 'data-rail="K" data-supply="-"' in bare
    assert 'data-rail="M" data-supply="-"' in bare
    assert f'stroke="{POSITIVE}"' in bare
    assert f'stroke="{GROUND}"' in bare
    nl = Netlist(board, [], [("F2", "N2"), ("E2", "K15"), ("K15", "M11"), ("E3", "F4")])
    svg = render_svg(board, nl)
    assert 'data-holes="F2-N2" data-supply="+"' in svg
    assert 'data-holes="E2-K15" data-supply="-"' in svg
    assert 'data-holes="K15-M11" data-supply="-"' in svg
    assert 'data-holes="E3-F4" data-supply="signal"' in svg
    cover = render_svg(board, breadvolt=True)
    rail_x = float(re.search(r'data-rail="K" data-supply="-" x1="([^"]+)"', cover).group(1))
    shade_x = float(re.search(r'<rect x="([^"]+)" [^>]*fill="#e8d39a"', cover).group(1))
    assert shade_x > rail_x


def test_led_chaser_marks_the_unused_left_rail_off():
    board = jos()
    nl = Netlist(board, parse_components(LED_CHASER.lines), parse_wires(LED_CHASER.wires))
    svg = render_svg(board, nl, breadvolt=True)
    assert re.search(r'data-rail="L"[^>]*>\(off\)</text>', svg)
    assert re.search(r'data-rail="N"[^>]*>\+9V</text>', svg)
    assert svg.count(">(off)</text>") == 1
    assert svg.count(">+9V</text>") == 1
    assert svg.count(">GND</text>") == 2

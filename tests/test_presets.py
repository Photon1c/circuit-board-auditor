from pathlib import Path

from core.board import Board
from core.checks import run_checks, run_link_checks
from core.entry import parse_components, parse_wires
from core.nets import Netlist, breadvolt_lift, shift_placement
from core.presets import CIRCUITS, LED_CHASER

ROOT = Path(__file__).resolve().parents[1]

REFS = [
    "U1", "U2", "U3",
    "C1", "C2", "C3",
    "R2", "P1", "R4", "R5", "R6",
    "D1", "D2", "D3",
]


def test_led_chaser_is_selectable_and_fits_the_jos_board():
    assert CIRCUITS["led-chaser"] is LED_CHASER
    board = Board.load(ROOT / "boards" / f"{LED_CHASER.board}.json")
    comps = parse_components(LED_CHASER.lines)
    assert [c.ref for c in comps] == REFS
    for comp in comps:
        for hole in comp.pins.values():
            assert board.has_hole(hole), f"{comp.ref} pin hole {hole}"
    u1 = comps[0]
    assert (u1.kind, u1.pins["PIN1"], u1.pins["PIN8"]) == ("ne555p", "E2", "F2")
    r2 = next(c for c in comps if c.ref == "R2")
    assert r2.pins["PIN2"] == "N3"
    d1 = next(c for c in comps if c.ref == "D1")
    assert (d1.kind, d1.value, d1.pins["anode"], d1.pins["cathode"]) == ("led", "GREEN", "J31", "J30")
    wires = parse_wires(LED_CHASER.wires)
    for a, b in wires:
        assert board.has_hole(a) and board.has_hole(b)
    nl = Netlist(board, comps, wires)
    assert nl.continuity("E3", "F4")       # 555 trigger tied to threshold
    assert nl.continuity("F8", "N8")       # 4017 VDD on the positive rail
    assert nl.continuity("E15", "K15")     # 4017 VSS on the negative rail
    assert nl.continuity("F18", "J30")     # ULN output to LED cathode
    assert not nl.continuity("K15", "N8")  # the two supply rails stay apart


def test_led_chaser_continuity_list():
    board = Board.load(ROOT / "boards" / f"{LED_CHASER.board}.json")
    nl = Netlist(board, parse_components(LED_CHASER.lines), parse_wires(LED_CHASER.wires))
    results = { (r.check.a, r.check.b): r for r in run_link_checks(nl, LED_CHASER.links) }
    assert results[("F2", "N2")].ok
    assert results[("E5", "N2")].ok
    assert results[("F8", "N2")].ok
    assert results[("E4", "F10")].ok
    assert results[("E25", "E15")].ok
    assert results[("J31", "J30")].ok
    assert results[("N2", "K15")].ok
    assert results[("E2", "K15")].ok
    assert results[("K15", "M11")].ok
    assert all(r.ok for r in results.values())


def test_breadvolt_lifts_the_chaser_to_the_row_above_the_cover():
    board = Board.load(ROOT / "boards" / f"{LED_CHASER.board}.json")
    comps = parse_components(LED_CHASER.lines)
    wires = [(board.normalize(a), board.normalize(b)) for a, b in parse_wires(LED_CHASER.wires)]
    delta = breadvolt_lift(board, comps, wires)
    assert delta == 9
    moved, moved_wires = shift_placement(board, comps, wires, delta)
    u1 = moved[0]
    assert (u1.pins["PIN1"], u1.pins["PIN8"]) == ("E11", "F11")
    d3 = next(c for c in moved if c.ref == "D3")
    assert (d3.pins["anode"], d3.pins["cathode"]) == ("J48", "J47")
    assert ("F11", "N11") in moved_wires
    assert ("E11", "K24") in moved_wires
    nl = Netlist(board, moved, moved_wires)
    links = tuple(
        type(check)(board.shift_hole(check.a, delta), board.shift_hole(check.b, delta),
                    check.connected, check.note)
        for check in LED_CHASER.links
    )
    assert all(r.ok for r in run_link_checks(nl, links))
    assert not any(i.code == "breadvolt" for i in run_checks(nl, breadvolt=True))
    assert breadvolt_lift(board, moved, moved_wires) == 0
    back, _back_wires = shift_placement(board, moved, moved_wires, -delta)
    assert back[0].pins["PIN1"] == "E2"

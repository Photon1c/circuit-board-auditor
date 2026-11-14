from pathlib import Path

from core.board import Board
from core.checks import run_checks, run_link_checks
from core.entry import parse_components, parse_wires
from core.nets import Netlist, breadvolt_lift, shift_placement
from core.presets import (
    CIRCUITS,
    LED_CHASER,
    ULTRASONIC_DEYUE_ANALYZER,
    ULTRASONIC_SENSOR_ESP,
    incompatibility,
    place_on,
)

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


def test_ultrasonic_sensor_esp_is_selectable_and_fits_the_170_board():
    assert CIRCUITS["ultrasonic-sensor-esp"] is ULTRASONIC_SENSOR_ESP
    assert ULTRASONIC_SENSOR_ESP.board == "breadboard_170"
    board = Board.load(ROOT / "boards" / f"{ULTRASONIC_SENSOR_ESP.board}.json")
    comps = parse_components(ULTRASONIC_SENSOR_ESP.lines)
    assert [c.ref for c in comps] == ["M1", "M2", "R1", "R2", "V1"]
    for comp in comps:
        for hole in comp.pins.values():
            assert board.has_hole(hole), f"{comp.ref} pin hole {hole}"
    m1 = comps[0]
    assert (m1.pins["D0"], m1.pins["D4"], m1.pins["D5"], m1.pins["D6"]) == ("C1", "C5", "C6", "C7")
    assert (m1.pins["VBUS"], m1.pins["GND"], m1.pins["D7"]) == ("G1", "G2", "G7")
    m2 = next(c for c in comps if c.ref == "M2")
    assert (m2.pins["TRIG"], m2.pins["ECHO"]) == ("B5", "B11")
    wires = parse_wires(ULTRASONIC_SENSOR_ESP.wires)
    for a, b in wires:
        assert board.has_hole(a) and board.has_hole(b)
    nl = Netlist(board, comps, wires)
    assert [i for i in run_checks(nl) if i.severity == "error"] == []
    assert nl.continuity("B5", "C5")        # gray TRIG beside D4
    assert nl.continuity("A12", "C6")       # divider junction to D5
    assert nl.continuity("A13", "G2")       # sensor ground common with XIAO ground
    assert nl.continuity("A15", "C15")      # switched 5 V to the sensor
    assert not nl.continuity("B11", "A12")  # 1k between ECHO and the junction
    assert not nl.continuity("A12", "A13")  # 1.5k between junction and ground
    assert not nl.continuity("B11", "A13")  # ECHO must not be shorted to ground
    assert not nl.continuity("A15", "A13")  # 5 V must not be shorted to ground


def test_ultrasonic_sensor_esp_continuity_list():
    board = Board.load(ROOT / "boards" / f"{ULTRASONIC_SENSOR_ESP.board}.json")
    nl = Netlist(board, parse_components(ULTRASONIC_SENSOR_ESP.lines),
                 parse_wires(ULTRASONIC_SENSOR_ESP.wires))
    results = run_link_checks(nl, ULTRASONIC_SENSOR_ESP.links)
    assert all(r.ok for r in results)


def test_ultrasonic_deyue_analyzer_matches_the_bench_layout():
    assert CIRCUITS["ultrasonic-deyue-analyzer"] is ULTRASONIC_DEYUE_ANALYZER
    board = Board.load(ROOT / "boards" / f"{ULTRASONIC_DEYUE_ANALYZER.board}.json")
    comps = parse_components(ULTRASONIC_DEYUE_ANALYZER.lines)
    assert [c.ref for c in comps] == ["M1", "M2", "R1", "R2", "V1"]
    m1 = comps[0]
    assert (m1.pins["D4"], m1.pins["D5"]) == ("C22", "C23")
    r1 = next(c for c in comps if c.ref == "R1")
    r2 = next(c for c in comps if c.ref == "R2")
    # The divider spans A25-C27: R1 A25-A26, R2 C26-C27, junction row 26.
    assert (r1.pins["1"], r1.pins["2"]) == ("A25", "A26")
    assert (r2.pins["1"], r2.pins["2"]) == ("C26", "C27")
    m2 = comps[1]
    assert (m2.pins["TRIG"], m2.pins["ECHO"]) == ("B22", "B25")
    for comp in comps:
        for hole in comp.pins.values():
            if hole != "nc":
                assert board.has_hole(hole), f"{comp.ref} pin hole {hole}"
    wires = parse_wires(ULTRASONIC_DEYUE_ANALYZER.wires)
    nl = Netlist(board, comps, wires)
    assert [i for i in run_checks(nl) if i.severity == "error"] == []
    assert all(r.ok for r in run_link_checks(nl, ULTRASONIC_DEYUE_ANALYZER.links))
    # The preset carries its analyzer probe map; every probed hole exists.
    probes = dict(token.split("=", 1)
                  for token in ULTRASONIC_DEYUE_ANALYZER.analyzer_map.split())
    assert probes == {"CH0": "B22", "CH1": "B25", "CH2": "B23", "GND": "B27"}
    for hole in probes.values():
        assert board.has_hole(hole)
    # Shaded footprints: analyzer expansion E1-G11, module D18-H24.
    assert ULTRASONIC_DEYUE_ANALYZER.covers == (
        ("Logic analyzer", "E1", "G11"),
        ("XIAO ESP32-C6", "D18", "H24"),
    )
    for _label, corner_a, corner_b in ULTRASONIC_DEYUE_ANALYZER.covers:
        assert board.has_hole(corner_a) and board.has_hole(corner_b)
    # Dropdown labels stay unique (no duplicate-looking entries).
    labels = [c.label for c in CIRCUITS.values()]
    assert len(labels) == len(set(labels))


def test_circuit_places_on_any_selected_board_it_fits():
    small = Board.load(ROOT / "boards" / "breadboard_170.json")
    deyue = Board.load(ROOT / "boards" / "deyue_400_solderless.json")
    jos = Board.load(ROOT / "boards" / f"{ULTRASONIC_SENSOR_ESP.board}.json")
    assert place_on(small, ULTRASONIC_SENSOR_ESP) is not None
    placed = place_on(deyue, ULTRASONIC_SENSOR_ESP)
    assert placed is not None
    comps, wires = placed
    nl = Netlist(deyue, comps, wires)
    assert all(r.ok for r in run_link_checks(nl, ULTRASONIC_SENSOR_ESP.links))
    assert place_on(jos, ULTRASONIC_SENSOR_ESP) is not None
    assert incompatibility(deyue, ULTRASONIC_SENSOR_ESP) is None


def test_circuit_that_does_not_fit_reports_why():
    small = Board.load(ROOT / "boards" / "breadboard_170.json")
    deyue = Board.load(ROOT / "boards" / "deyue_400_solderless.json")
    assert place_on(small, LED_CHASER) is None
    assert incompatibility(small, LED_CHASER) is not None
    assert place_on(deyue, LED_CHASER) is None  # 30 rows, the chaser needs 48
    big = Board.from_dict({
        "name": "big rail-less test board",
        "type": "breadboard",
        "rows": 63,
        "columns": list("ABCDEFGHIJ"),
        "strips": [["A", "B", "C", "D", "E"], ["F", "G", "H", "I", "J"]],
    })
    assert "power rail" in incompatibility(big, LED_CHASER)
    assert place_on(big, ULTRASONIC_SENSOR_ESP) is not None

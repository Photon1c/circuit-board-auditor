"""Named circuits the dashboard can place in one step."""
from __future__ import annotations

from dataclasses import dataclass

from core.board import Board
from core.checks import LinkCheck
from core.entry import parse_components, parse_wires
from core.nets import NC, Component


@dataclass(frozen=True)
class Circuit:
    label: str
    board: str
    lines: str
    wires: str = ""
    links: tuple[LinkCheck, ...] = ()
    # Logic-analyzer probe map ("CH0=B5 ...") the preset is drawn for.
    # Loading the circuit enables the analyzer overlay with this map.
    analyzer_map: str = ""
    # Shaded footprints of hardware that sits ON the board but is not
    # part of the netlist: (label, corner hole, opposite corner hole).
    # Drawn like the BreadVolt shade; view only.
    covers: tuple[tuple[str, str, str], ...] = ()


LED_CHASER = Circuit(
    label="LED chaser",
    board="california_jos_breadboard_870_solderless",
    lines="""\
U1 NE555P PIN1=E2 PIN2=E3 PIN3=E4 PIN4=E5 PIN5=F5 PIN6=F4 PIN7=F3 PIN8=F2
U2 CD4017BE PIN1=E8 PIN2=E9 PIN3=E10 PIN4=E11 PIN5=E12 PIN6=E13 PIN7=E14 PIN8=E15 PIN9=F15 PIN10=F14 PIN11=F13 PIN12=F12 PIN13=F11 PIN14=F10 PIN15=F9 PIN16=F8
U3 ULN2003A PIN1=E18 PIN2=E19 PIN3=E20 PIN4=E21 PIN5=E22 PIN6=E23 PIN7=E24 PIN8=E25 PIN9=F25 PIN10=F24 PIN11=F23 PIN12=F22 PIN13=F21 PIN14=F20 PIN15=F19 PIN16=F18
C1 CAP 100u PIN1=A3 PIN2=A2
C2 CAP 10n PIN1=G5 PIN2=G6
C3 CAP 100n PIN1=G8 PIN2=G7
R2 RESISTOR 1k PIN1=J3 PIN2=N3
P1 POT 1k PIN1=J27 PIN2=J28 PIN3=J29
R4 RESISTOR 470 PIN1=H31 PIN2=H33
R5 RESISTOR 470 PIN1=H35 PIN2=H37
R6 RESISTOR 470 PIN1=H39 PIN2=H41
D1 LED GREEN anode=J31 cathode=J30
D2 LED GREEN anode=J35 cathode=J34
D3 LED GREEN anode=J39 cathode=J38
""",
    wires="""\
E3-F4      (555 pins 2 and 6)
J3-J27     (pot pin 1 to 555 pin 7 node)
J3-J28     (pot wiper to 555 pin 7 node)
J4-J29     (pot pin 3 to timing node)
E4-F10     (555 OUT to 4017 CLK)
F8-N8      (4017 VDD to +9V)
E15-K15    (4017 VSS to GND)
F11-M11    (4017 INH to GND)
F9-M9      (4017 RESET to GND)
G7-M7      (100 nF to GND)
J6-M6      (10 nF to GND)
E9-E19     (4017 Q1 to ULN IN2)
E10-E18    (4017 Q0 to ULN IN1)
E11-E20    (4017 Q2 to ULN IN3)
E25-K25    (ULN GND)
F18-J30    (ULN OUT1 to D1 cathode)
F19-J34    (ULN OUT2 to D2 cathode)
F20-J38    (ULN OUT3 to D3 cathode)
H33-N33    (R4 to +9V)
H37-N37    (R5 to +9V)
H41-N41    (R6 to +9V)
F2-N2      (555 VCC to +9V)
E5-N6      (555 reset to +9V)
E2-K15     (555 ground to the left negative rail)
K15-M11    (join the left and right ground rails)
""",
    links=(
        LinkCheck("F2", "N2", True, "555 VCC to +9V"),
        LinkCheck("E5", "N2", True, "555 reset to +9V"),
        LinkCheck("F8", "N2", True, "4017 VDD to +9V"),
        LinkCheck("E3", "F4", True, "555 trigger tied to threshold"),
        LinkCheck("A3", "F4", True, "timing capacitor on the trigger/threshold node"),
        LinkCheck("A2", "E2", True, "timing capacitor on 555 ground"),
        LinkCheck("E4", "F10", True, "555 output to 4017 clock"),
        LinkCheck("J3", "J28", True, "pot wiper on the 555 discharge node"),
        LinkCheck("J4", "J29", True, "pot end on the timing node"),
        LinkCheck("E15", "K15", True, "4017 ground on the left negative rail"),
        LinkCheck("E25", "E15", True, "ULN ground joined to 4017 ground"),
        LinkCheck("F11", "M11", True, "4017 inhibit on the right negative rail"),
        LinkCheck("F9", "M11", True, "4017 reset on the right negative rail"),
        LinkCheck("E10", "E18", True, "4017 Q0 to ULN input 1"),
        LinkCheck("E9", "E19", True, "4017 Q1 to ULN input 2"),
        LinkCheck("E11", "E20", True, "4017 Q2 to ULN input 3"),
        LinkCheck("F18", "J30", True, "ULN output 1 to D1 cathode"),
        LinkCheck("F19", "J34", True, "ULN output 2 to D2 cathode"),
        LinkCheck("F20", "J38", True, "ULN output 3 to D3 cathode"),
        LinkCheck("J31", "H31", True, "D1 anode shares a strip with R4"),
        LinkCheck("H33", "N33", True, "R4 return to +9V"),
        LinkCheck("G8", "F8", True, "100 nF on 4017 VDD"),
        LinkCheck("G7", "M7", True, "100 nF to the right ground rail"),
        LinkCheck("G5", "F5", True, "10 nF on the 555 control pin"),
        LinkCheck("G6", "M6", True, "10 nF to the right ground rail"),
        LinkCheck("E2", "K15", True, "555 ground to the ground rail"),
        LinkCheck("K15", "M11", True, "left and right ground rails joined"),
        LinkCheck("N2", "K15", False, "+9V stays off the left ground rail"),
        LinkCheck("N2", "M11", False, "+9V stays off the right ground rail"),
        LinkCheck("E4", "F2", False, "555 output stays off VCC"),
        LinkCheck("E4", "E2", False, "555 output stays off ground"),
        LinkCheck("J31", "J30", False, "D1 is not shorted"),
        LinkCheck("J35", "J34", False, "D2 is not shorted"),
        LinkCheck("J39", "J38", False, "D3 is not shorted"),
    ),
)

ULTRASONIC_SENSOR_ESP = Circuit(
    label="Ultrasonic Sensor-ESP (170 test board)",
    board="breadboard_170",
    lines="""\
M1 module XIAO-ESP32-C6 D0=C1 D1=C2 D2=C3 D3=C4 D4=C5 D5=C6 D6=C7 D7=G7 D8=G6 D9=G5 D10=G4 3V3=G3 GND=G2 VBUS=G1
M2 module U098-B2 GND=A13 5V=C15 TRIG=B5 ECHO=B11
R1 resistor 1k 1=A11 2=A12
R2 resistor 1.5k 1=C12 2=C13
V1 source 5V +=A15 -=D13
""",
    wires="""\
B6-D12     (D5 jumper, from B6 beside D5, to the divider junction, board row 12)
H2-B13     (GND jumper, from H2 beside GND, to the ground row, board row 13)
""",
    links=(
        LinkCheck("B5", "C5", True, "gray TRIG plugs in at B5, beside XIAO D4"),
        LinkCheck("B11", "A11", True, "orange ECHO lands on the 1k top row"),
        LinkCheck("A12", "C6", True, "divider junction reaches XIAO D5"),
        LinkCheck("A13", "G2", True, "sensor purple GND is common with XIAO GND"),
        LinkCheck("D13", "G2", True, "supply negative is common with XIAO GND"),
        LinkCheck("A15", "C15", True, "switched 5 V feed (white) reaches the sensor"),
        LinkCheck("B11", "A12", False, "1k stands between ECHO and the D5 junction"),
        LinkCheck("A12", "A13", False, "1.5k stands between the junction and ground"),
        LinkCheck("B11", "A13", False, "ECHO is not shorted to ground; a jumper here forces no_echo"),
        LinkCheck("B5", "A12", False, "TRIG is not tied to the echo junction"),
        LinkCheck("A15", "A13", False, "the 5 V feed is not shorted to ground"),
        LinkCheck("C5", "C6", False, "D4 and D5 are not shorted"),
    ),
)

ULTRASONIC_DEYUE_ANALYZER = Circuit(
    label="Ultrasonic Sensor-ESP (Deyue 400 + analyzer)",
    board="deyue_400_solderless",
    # The bench layout as actually wired (2026-11-14): XIAO D4/D5 land
    # at C22/C23, the divider spans A25-C27 right beside the module
    # (R1 1k A25-A26, R2 1.5k C26-C27, junction on row 26) and is
    # jumpered up to D5, and ground is commoned on row 27. The logic
    # analyzer breakout sits on E1-F11: row 1 = CH0, row 2 = CH1,
    # row 3 = CH2, row 10 = CLK, row 11 = GND. Channels are tapped on
    # the F-side strips (G column: G1/G2/G3, GND at G11 wired to the
    # M- rail), and each tap is jumpered to the signal it watches.
    # The M- rail must be tied back to circuit ground (M25-E27) or
    # the analyzer ground floats relative to the circuit.
    # Power: the sensor is fed directly by its battery module, off
    # the board - battery + to sensor 5V (no breadboard hole, hence
    # 5V=nc), battery - spliced to the sensor GND lead and to a third
    # male plug that lands at A27, commoning battery ground with the
    # board's ground row. Only the XIAO pins in use are placed; the
    # rest are nc in the model (still physically in the board - read
    # D4/D5/GND off the silkscreen).
    lines="""\
M1 module XIAO-ESP32-C6 D4=C22 D5=C23 GND=I19 D0=nc D1=nc D2=nc D3=nc D6=nc D7=nc D8=nc D9=nc D10=nc 3V3=nc VBUS=nc
M2 module U098-B2 GND=A27 5V=nc TRIG=B22 ECHO=B25
R1 resistor 1k 1=A25 2=A26
R2 resistor 1.5k 1=C26 2=C27
""",
    wires="""\
E26-A23     (divider junction, row 26, to the D5 strip, row 23)
G1-A22      (analyzer CH0, tapped at G1 beside breakout F1, to the TRIG strip, row 22)
G2-D25      (analyzer CH1, tapped at G2 beside breakout F2, to the ECHO strip, row 25)
G3-B23      (analyzer CH2, tapped at G3 beside breakout F3, to the D5 strip, row 23)
G11-M10     (analyzer GND, tapped at G11 beside breakout F11, to the right ground rail)
M25-E27     (REQUIRED tie: right ground rail down to circuit ground row 27)
I19-B27     (XIAO GND pin, row 19, down to the ground row 27)
""",
    links=(
        LinkCheck("B22", "C22", True, "TRIG lands on the D4 strip"),
        LinkCheck("B25", "A25", True, "ECHO lands on R1 top"),
        LinkCheck("A26", "A23", True, "divider junction reaches the D5 strip"),
        LinkCheck("A26", "C26", True, "divider junction reaches R2 top"),
        LinkCheck("A23", "C23", True, "junction is on D5 itself"),
        LinkCheck("C27", "A27", True, "R2 bottom and sensor GND share ground row 27"),
        LinkCheck("I19", "B27", True, "XIAO GND pin (I19) is wired to ground row 27"),
        LinkCheck("A27", "E27", True, "ground row 27 is one strip end to end"),
        LinkCheck("B25", "A23", False, "ECHO is not shorted to D5; the divider stands between"),
        LinkCheck("A25", "A26", False, "1k stands between ECHO and the junction"),
        LinkCheck("C26", "C27", False, "1.5k stands between junction and ground"),
        LinkCheck("B22", "B25", False, "TRIG is not tied to ECHO (same part color, different signals)"),
        LinkCheck("G1", "C22", True, "analyzer CH0 (breakout F1, tap G1) reaches TRIG/D4"),
        LinkCheck("G2", "B25", True, "analyzer CH1 (breakout F2, tap G2) reaches raw ECHO"),
        LinkCheck("G3", "C23", True, "analyzer CH2 (breakout F3, tap G3) reaches D5"),
        LinkCheck("G11", "A27", True, "analyzer GND (G11-M10 rail, tied at M25-E27) is common ground"),
        LinkCheck("G1", "G2", False, "analyzer CH0 and CH1 are not tied together"),
    ),
    analyzer_map="CH0=F1 CH1=F2 CH2=F3 GND=F11",
    covers=(
        ("Logic analyzer", "E1", "F11"),
        ("XIAO ESP32-C6", "D18", "H24"),
    ),
)

CIRCUITS: dict[str, Circuit] = {
    "led-chaser": LED_CHASER,
    "ultrasonic-sensor-esp": ULTRASONIC_SENSOR_ESP,
    "ultrasonic-deyue-analyzer": ULTRASONIC_DEYUE_ANALYZER,
}


def missing_hole(board: Board, circuit: Circuit) -> str | None:
    """First hole the circuit references that is not on board, else None."""
    holes = [
        hole
        for comp in parse_components(circuit.lines)
        for hole in comp.pins.values()
        if hole != NC
    ]
    holes += [hole for pair in parse_wires(circuit.wires) for hole in pair]
    for hole in holes:
        if not board.has_hole(hole):
            return hole
    return None


def incompatibility(board: Board, circuit: Circuit) -> str | None:
    """Why the circuit cannot go on board, or None when it fits."""
    hole = missing_hole(board, circuit)
    if hole is None:
        return None
    rail_ids = {rail.id for rail in board.rails}
    if hole[0] not in board.columns and hole[0] not in rail_ids:
        return f"hole {hole} needs a power rail this board does not have"
    return f"hole {hole} is not on {board.name}"


def place_on(
    board: Board, circuit: Circuit
) -> tuple[list[Component], list[tuple[str, str]]] | None:
    """Parse the circuit for board. None when any needed hole is missing."""
    if missing_hole(board, circuit) is not None:
        return None
    comps = parse_components(circuit.lines)
    wires = [(board.normalize(a), board.normalize(b)) for a, b in parse_wires(circuit.wires)]
    return comps, wires

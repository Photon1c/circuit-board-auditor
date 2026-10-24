"""Named circuits the dashboard can place in one step."""
from __future__ import annotations

from dataclasses import dataclass

from core.checks import LinkCheck


@dataclass(frozen=True)
class Circuit:
    label: str
    board: str
    lines: str
    wires: str = ""
    links: tuple[LinkCheck, ...] = ()


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

CIRCUITS: dict[str, Circuit] = {
    "led-chaser": LED_CHASER,
}

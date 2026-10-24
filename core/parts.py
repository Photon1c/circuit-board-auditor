"""Reference data for the help screen: part kinds, pin names, and examples.

Every example here must parse with core.entry; tests/test_parts.py checks that.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PartHelp:
    kind: str
    pins: str
    example: str
    note: str = ""


PARTS: tuple[PartHelp, ...] = (
    PartHelp("resistor", "1, 2", "R1 resistor 470k 1=E1 2=J1",
             "Either pin can go either way round."),
    PartHelp("capacitor", "+, -", "C1 capacitor 100u +=A3 -=A6",
             "Use + and - for polarized (electrolytic) parts. Plain capacitors can use 1 and 2. "
             "A cross is drawn in the positive hole and a bar in the negative hole. "
             "Numbered pins use pin 1 as positive and pin 2 as negative."),
    PartHelp("led", "anode, cathode", "D1 led green anode=J4 cathode=J5",
             "Anode is the longer leg; cathode is the flat side. "
             "A cross is drawn in the anode hole and a bar in the cathode hole. "
             "Numbered legs use pin 1 as the anode."),
    PartHelp("diode", "anode, cathode", "D2 diode 1N4148 anode=C4 cathode=C5",
             "A cross is drawn in the anode hole and a bar in the cathode hole."),
    PartHelp("pot", "A, W, B", "P1 pot 10k A=B1 W=B2 B=nc",
             "Wire as a rheostat: A and W in series, B set to nc."),
    PartHelp("source", "+, -", "V1 source 5V +=A1 -=A17",
             "Power supply. A short between + and - is flagged."),
    PartHelp("ic", "pin numbers", "U1 ic uln2003 1=F5 2=F6 8=F12",
             "Use the chip's own pin numbers, as printed on its datasheet."),
    PartHelp("module", "any names", "M1 module xiao 3V3=A1 GND=A2 D0=A3",
             "Boards and modules: use the pin names printed on the board."),
    PartHelp("wire", "two holes", "E1-F1",
             "Jumper wire between two holes. Enter it in the Wire box, not Component."),
)

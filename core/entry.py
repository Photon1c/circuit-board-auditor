"""Parse the text entry format used by the dashboard.

Components:  REF KIND [VALUE] PIN=HOLE ...     e.g.  R1 resistor 470k 1=E1 2=J1
             One component per line. A batch is several of those lines.
             Use PIN=nc for a pin that stays unconnected, e.g.  P1 pot 1=A1 W=B2 B=nc
Wires:       HOLE HOLE  or  HOLE-HOLE           e.g.  E1-F1
"""
from __future__ import annotations

from core.nets import NC, Component


def parse_component(line: str) -> Component:
    parts = line.split()
    if len(parts) < 3:
        raise ValueError("Expected: REF KIND [VALUE] PIN=HOLE ...")
    ref, kind = parts[0], parts[1].lower()
    rest = parts[2:]
    value = ""
    if rest and "=" not in rest[0]:
        value = rest.pop(0)
    pins: dict[str, str] = {}
    for token in rest:
        if "=" not in token:
            raise ValueError(f"Bad pin entry {token!r}; use PIN=HOLE")
        pin, hole = token.split("=", 1)
        if not pin or not hole:
            raise ValueError(f"Bad pin entry {token!r}; use PIN=HOLE")
        pins[pin] = NC if hole.lower() == NC else hole.upper()
    if not pins:
        raise ValueError("No pins given; use PIN=HOLE, e.g. 1=E1")
    return Component(ref=ref, kind=kind, pins=pins, value=value)


def parse_components(text: str) -> list[Component]:
    """Parse a batch. Each non-blank line is one component."""
    comps: list[Component] = []
    seen: set[str] = set()
    for lineno, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line:
            continue
        try:
            comp = parse_component(line)
        except ValueError as ex:
            raise ValueError(f"Line {lineno}: {ex}") from ex
        if comp.ref in seen:
            raise ValueError(f"Line {lineno}: {comp.ref} is listed twice")
        seen.add(comp.ref)
        comps.append(comp)
    if not comps:
        raise ValueError("No components to add")
    return comps


def parse_wire(line: str) -> tuple[str, str]:
    parts = line.replace("-", " ").split()
    if len(parts) != 2:
        raise ValueError("Expected two holes, e.g. E1-F1")
    return parts[0].upper(), parts[1].upper()


def parse_wires(text: str) -> list[tuple[str, str]]:
    """Parse a batch of jumpers, one HOLE-HOLE per line. A parenthetical note is ignored."""
    wires: list[tuple[str, str]] = []
    for lineno, raw in enumerate(text.splitlines(), start=1):
        line = raw.split("(", 1)[0].strip()
        if not line or line.startswith("#"):
            continue
        try:
            wires.append(parse_wire(line))
        except ValueError as ex:
            raise ValueError(f"Line {lineno}: {ex}") from ex
    return wires

"""Rule checks over a netlist, plus simple LED current estimates."""
from __future__ import annotations

from dataclasses import dataclass

from .nets import NC, Netlist


@dataclass(frozen=True)
class Issue:
    severity: str   # "error" or "warning"
    code: str
    message: str


@dataclass(frozen=True)
class LinkCheck:
    """One probe the continuity button should confirm."""
    a: str
    b: str
    connected: bool
    note: str = ""


@dataclass(frozen=True)
class LinkResult:
    check: LinkCheck
    ok: bool
    measured: str


def run_link_checks(netlist: Netlist, checks: tuple[LinkCheck, ...] | list[LinkCheck]) -> list[LinkResult]:
    """Probe each pair. ok means the board matches connected/open as specified."""
    results: list[LinkResult] = []
    for check in checks:
        try:
            beep = netlist.continuity(check.a, check.b)
        except ValueError as ex:
            results.append(LinkResult(check, False, str(ex)))
            continue
        measured = "connected" if beep else "open"
        results.append(LinkResult(check, beep == check.connected, measured))
    return results


def led_current_ma(v_supply: float, v_forward: float, r_ohm: float, drop_v: float = 0.0) -> float:
    """Estimated LED current in mA. drop_v covers a driver such as a ULN2003 channel."""
    if r_ohm <= 0:
        raise ValueError("Resistance must be positive")
    return max(0.0, v_supply - v_forward - drop_v) / r_ohm * 1000.0


def run_checks(netlist: Netlist, *, breadvolt: bool = False) -> list[Issue]:
    board = netlist.board
    issues: list[Issue] = []

    # 1. Every placed pin must be on the board, with at most one pin per hole.
    occupied: dict[str, tuple[str, str]] = {}
    for comp in netlist.components:
        for pin, hole in comp.pins.items():
            if hole == NC:
                continue
            if not board.has_hole(hole):
                issues.append(Issue("error", "invalid_hole",
                                    f"{comp.ref} pin {pin}: {hole!r} is not on {board.name}"))
                continue
            canon = board.normalize(hole)
            if breadvolt:
                zone = board.breadvolt_zone(canon)
                if zone == "pin":
                    issues.append(Issue("error", "breadvolt",
                                        f"{comp.ref} pin {pin}: {canon} is used by a BreadVolt pin"))
                elif zone == "covered":
                    issues.append(Issue(
                        "error", "breadvolt",
                        f"{comp.ref} pin {pin}: {canon} is under the BreadVolt "
                        f"(rows 1–{board.breadvolt.covered_rows})",
                    ))
            if canon in occupied:
                other_ref, other_pin = occupied[canon]
                issues.append(Issue("error", "hole_conflict",
                                    f"{comp.ref} pin {pin} and {other_ref} pin {other_pin} both use {canon}"))
            else:
                occupied[canon] = (comp.ref, pin)

    if breadvolt and board.breadvolt is not None:
        for a, b in netlist.wires:
            for hole in (a, b):
                zone = board.breadvolt_zone(hole)
                if zone == "pin":
                    issues.append(Issue("error", "breadvolt",
                                        f"Wire {a}-{b}: {hole} is used by a BreadVolt pin"))
                elif zone == "covered":
                    issues.append(Issue(
                        "error", "breadvolt",
                        f"Wire {a}-{b}: {hole} is under the BreadVolt "
                        f"(rows 1–{board.breadvolt.covered_rows})",
                    ))

    # 2. Supply shorts and component pins sharing a net.
    for comp in netlist.components:
        pin_nets = {
            pin: netlist.net_of(hole)
            for pin, hole in comp.pins.items()
            if hole != NC and board.has_hole(hole)
        }
        if comp.kind == "source":
            if "+" in pin_nets and "-" in pin_nets and pin_nets["+"] == pin_nets["-"]:
                issues.append(Issue("error", "supply_short",
                                    f"{comp.ref}: + and - are on the same net"))
            continue
        by_net: dict[str, list[str]] = {}
        for pin, net in pin_nets.items():
            by_net.setdefault(net, []).append(pin)
        for pins in by_net.values():
            if len(pins) > 1:
                issues.append(Issue("error", "pin_short",
                                    f"{comp.ref}: pins {', '.join(sorted(pins))} are shorted together"))

    # 3. Pins alone on their net (nothing else connected).
    nets = netlist.nets_with_pins()
    for comp, pin, hole in netlist.placed_pins():
        if len(nets[netlist.net_of(hole)]) == 1:
            issues.append(Issue("warning", "dangling_pin",
                                f"{comp.ref} pin {pin} at {hole} connects to nothing else"))

    return issues

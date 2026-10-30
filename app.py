"""NiceGUI front end for the breadboard dashboard.

Run:  python app.py   then open http://127.0.0.1:8080
"""
from __future__ import annotations

import json
import os
from dataclasses import asdict
from pathlib import Path

from nicegui import ui

from core.board import Board
from core.checks import LinkCheck, run_checks, run_link_checks
from core.entry import parse_components, parse_wire, parse_wires
from core.nets import Component, Netlist, breadvolt_lift, shift_placement
from core.parts import PARTS
from core.presets import CIRCUITS, Circuit
from core.render import render_svg

BOARD_DIR = Path(__file__).parent / "boards"
BOARDS: dict[str, Board] = {p.stem: Board.load(p) for p in sorted(BOARD_DIR.glob("*.json"))}
DEFAULT_BOARD = "breadboard_170"


class Session:
    """Single-user working state, kept in memory until the app restarts."""

    def __init__(self) -> None:
        self.board_key = DEFAULT_BOARD
        self.components: list[Component] = []
        self.wires: list[tuple[str, str]] = []
        self.breadvolt = False
        self.breadvolt_shift = 0

    @property
    def board(self) -> Board:
        return BOARDS[self.board_key]

    def netlist(self) -> Netlist:
        return Netlist(self.board, list(self.components), list(self.wires))


state = Session()


def netlist_to_json() -> str:
    return json.dumps({
        "board": state.board_key,
        "components": [asdict(c) for c in state.components],
        "wires": [list(w) for w in state.wires],
        "breadvolt": state.breadvolt,
        "breadvolt_shift": state.breadvolt_shift,
    }, indent=2)


def netlist_from_json(text: str) -> None:
    data = json.loads(text)
    board_key = data.get("board", DEFAULT_BOARD)
    if board_key not in BOARDS:
        raise ValueError(f"Unknown board {board_key!r}")
    components = [
        Component(ref=c["ref"], kind=c["kind"], pins=dict(c["pins"]), value=c.get("value", ""))
        for c in data.get("components", [])
    ]
    wires = [(w[0], w[1]) for w in data.get("wires", [])]
    netlist = Netlist(BOARDS[board_key], components, wires)  # validates the wires
    state.board_key = board_key
    state.components = components
    state.wires = list(netlist.wires)
    state.breadvolt = bool(data.get("breadvolt", False))
    state.breadvolt_shift = int(data.get("breadvolt_shift", 0))


@ui.page("/")
def index() -> None:
    ui.add_head_html("""
<style>
  html, body, .q-layout, .q-page-container, .q-page {
    height: 100%;
    margin: 0;
    background: #e6e1d6 !important;
    color: #1f1b16;
    color-scheme: light;
    overflow: hidden;
  }
  .q-page {
    padding: 0 !important;
  }
  .nicegui-content {
    background: #e6e1d6 !important;
    max-width: none !important;
    width: 100%;
    height: 100vh;
    max-height: 100vh;
    min-height: 0;
    overflow: hidden;
    display: flex;
    flex-direction: column;
    align-items: stretch;
    box-sizing: border-box;
    padding: 6px 8px;
    gap: 4px;
  }
  .auditor-title {
    flex: 0 0 auto;
    width: 100%;
    gap: 8px;
    margin: 0;
  }
  .auditor-shell.nicegui-row {
    flex: 1 1 auto;
    align-items: stretch;
    width: 100%;
    min-height: 0;
    min-width: 0;
    gap: 6px;
    overflow: hidden;
  }
  .auditor-pane.nicegui-column {
    background: #fffdf8;
    border: 1px solid #d5cec2;
    border-radius: 8px;
    padding: 6px;
    gap: 6px;
    min-height: 0;
    min-width: 0;
    height: auto;
    max-height: none;
    align-self: stretch;
    box-sizing: border-box;
    overflow-x: scroll;
    overflow-y: scroll;
    scrollbar-color: #6b6458 #efeae1;
  }
  .auditor-pane .nicegui-row {
    gap: 6px;
    flex-wrap: nowrap;
  }
  .auditor-controls,
  .auditor-lines {
    flex: 0 0 17rem;
    width: 17rem;
  }
  .auditor-controls.nicegui-column,
  .auditor-lines.nicegui-column {
    align-items: stretch;
  }
  .auditor-board {
    flex: 1 1 auto;
    background: #f4f0e6;
    align-items: flex-start;
    justify-content: flex-start;
    gap: 0;
    padding: 0;
  }
  .auditor-board > div {
    display: block;
    width: 100%;
    min-width: 0;
    overflow: visible;
  }
  .auditor-board svg {
    display: block;
    width: 100%;
    height: auto;
    min-width: 32rem;
    max-width: none;
    max-height: none;
    background: #f4f0e6;
  }
  .auditor-lines .q-item {
    min-height: 28px;
    padding-top: 2px;
    padding-bottom: 2px;
  }
</style>
""")
    with ui.row().classes("auditor-title items-baseline"):
        ui.label("Circuit board auditor").classes("text-h5")
        ui.label("Press H for help").classes("text-caption text-grey")

    with ui.row().classes("auditor-shell no-wrap items-stretch w-full"):
        with ui.column().classes("auditor-pane auditor-controls"):
            board_select = ui.select(
                {key: board.name for key, board in BOARDS.items()},
                value=state.board_key,
                label="Board",
                on_change=lambda e: on_board_change(e.value),
            ).classes("w-full")
            breadvolt_box = ui.checkbox(
                "BreadVolt",
                value=state.breadvolt,
                on_change=lambda e: on_breadvolt(e.value),
            )
            breadvolt_note = ui.label(
                "Red is +9V and black is ground, from the rail the circuit uses. "
                "A red rail with nothing on it reads (off). "
                "Rows 1–10 of the terminal strips are covered, and the circuit slides up above them."
            ).classes("text-caption text-grey")
            circuit_select = ui.select(
                {key: circuit.label for key, circuit in CIRCUITS.items()},
                value=None,
                label="Add circuit",
                on_change=lambda e: load_circuit(e.value),
            ).classes("w-full")
            comp_in = ui.textarea(
                "Components (one per line)",
                placeholder="R1 resistor 470k 1=E1 2=J1",
            ).classes("w-full").props("rows=3")
            ui.button("Add components", on_click=lambda: add_component())
            wire_in = ui.input("Wire: HOLE-HOLE", placeholder="E1-F1").classes("w-full")
            ui.button("Add wire", on_click=lambda: add_wire())
            with ui.row().classes("w-full no-wrap"):
                ui.button("Remove last component", on_click=lambda: remove_last())
                ui.button("Clear all", on_click=lambda: clear_all())
            ui.separator()
            ui.label("Continuity probe").classes("text-subtitle2")
            with ui.row().classes("w-full no-wrap"):
                probe_a = ui.input("Hole A", placeholder="A1").classes("col")
                probe_b = ui.input("Hole B", placeholder="E1").classes("col")
            with ui.row().classes("w-full no-wrap"):
                ui.button("Probe", on_click=lambda: probe())
                ui.button("Check circuit", on_click=lambda: check_circuit())
            probe_out = ui.label("")
            ui.separator()
            ui.label("Netlist JSON").classes("text-subtitle2")
            json_box = ui.textarea().classes("w-full").props("rows=3")
            with ui.row().classes("w-full no-wrap"):
                ui.button("Export", on_click=lambda: export_json())
                ui.button("Import", on_click=lambda: import_json())

        with ui.column().classes("auditor-pane auditor-board col-grow"):
            board_view = ui.html("", sanitize=False)

        with ui.column().classes("auditor-pane auditor-lines"):
            comp_panel = ui.expansion("Components", value=False).classes("w-full").props("dense")
            with comp_panel:
                comp_list = ui.column().classes("w-full gap-0")
            check_panel = ui.expansion("Checks", value=False).classes("w-full").props("dense")
            with check_panel:
                issue_list = ui.column().classes("w-full gap-0")
            continuity_panel = ui.expansion("Continuity", value=False).classes("w-full").props("dense")
            with continuity_panel:
                probe_list = ui.column().classes("w-full gap-0")
                with probe_list:
                    ui.label("Run Check circuit to list every probe.").classes("text-caption text-grey")

    with ui.dialog() as help_dialog, ui.card().classes("w-[40rem] max-w-full"):
        ui.label("Help").classes("text-h6")
        ui.label("Press H to show or hide this screen.").classes("text-caption")
        ui.label("Parts").classes("text-subtitle1")
        for part in PARTS:
            with ui.column().classes("gap-0 q-mb-sm"):
                ui.label(f"{part.kind}: pins {part.pins}").classes("text-bold")
                ui.label(f"Example: {part.example}").classes("font-mono text-sm")
                if part.note:
                    ui.label(part.note).classes("text-caption")
        ui.label("Entry").classes("text-subtitle1")
        ui.label("Component box: one component per line, REF KIND [VALUE] PIN=HOLE ... "
                 "(use PIN=nc for an open pin)")
        ui.label("Add circuit loads a whole example, including its jumper wires. "
                 "LED chaser is placed on the California JOS board.")
        ui.label("On that board, BreadVolt covers rows 1–10 and its pins occupy "
                 "power-rail holes 1–4. A red rail the circuit uses is +9V; one with "
                 "nothing on it reads (off). Black rails are ground. "
                 "Rail hole 5 is skipped. Turning it on slides "
                 "the placed circuit up to the first row above the cover.")
        ui.label("Wire box: HOLE-HOLE, for example E1-F1")
        ui.label("Components, checks, and continuity sit on the right. Each heading and each line opens for the detail.")
        ui.label("Continuity").classes("text-subtitle1")
        ui.label("Enter two holes in the probe boxes and press Probe. "
                 "Check circuit runs the loaded example's continuity list.")
        ui.button("Close", on_click=lambda: help_dialog.close())

    def toggle_help() -> None:
        if help_dialog.value:
            help_dialog.close()
        else:
            help_dialog.open()

    def on_key(e) -> None:
        if e.action.keydown and e.key.str and e.key.str.lower() == "h":
            toggle_help()

    ui.keyboard(on_key=on_key, ignore=["input", "textarea"])

    def refresh() -> None:
        board_view.content = render_svg(state.board, state.netlist(), breadvolt=use_breadvolt())
        comp_list.clear()
        with comp_list:
            n_parts = len(state.components)
            n_wires = len(state.wires)
            comp_panel.text = f"Components · {n_parts} parts, {n_wires} wires"
            if not state.components and not state.wires:
                ui.label("No components yet.").classes("text-caption text-grey")
            for c in state.components:
                pins = "\n".join(f"{p} = {h}" for p, h in c.pins.items())
                header = f"{c.ref}  {c.kind}  {c.value}".strip()
                with ui.expansion(header, value=False).props("dense").classes("w-full"):
                    ui.label(pins).classes("font-mono text-caption").style("white-space: pre-line")
            for a, b in state.wires:
                ui.label(f"wire  {a}-{b}").classes("text-caption q-pl-md")
        fitted = state.board.breadvolt is not None
        breadvolt_box.set_visibility(fitted)
        breadvolt_note.set_visibility(fitted)
        if breadvolt_box.value != state.breadvolt:
            breadvolt_box.value = state.breadvolt
        issue_list.clear()
        with issue_list:
            issues = run_checks(state.netlist(), breadvolt=use_breadvolt())
            errors = sum(1 for issue in issues if issue.severity == "error")
            warnings = len(issues) - errors
            if not issues:
                check_panel.text = "Checks · clear"
                ui.label("No issues found.").classes("text-positive")
            else:
                check_panel.text = f"Checks · {errors} errors, {warnings} warnings"
            for issue in issues:
                css = "text-negative" if issue.severity == "error" else "text-warning"
                with ui.expansion(f"[{issue.severity}] {issue.code}", value=False).props("dense").classes(f"w-full {css}"):
                    ui.label(issue.message).classes("text-caption")

    def use_breadvolt() -> bool:
        return state.breadvolt and state.board.breadvolt is not None

    def on_breadvolt(value: bool) -> None:
        value = bool(value)
        if value == state.breadvolt:
            return
        if value:
            try:
                delta = apply_breadvolt_lift()
            except ValueError as ex:
                ui.notify(str(ex), type="negative")
                breadvolt_box.value = False
                return
            state.breadvolt = True
            if delta:
                ui.notify(f"Moved the circuit up {delta} rows, above the BreadVolt", type="positive")
        else:
            dropped = state.breadvolt_shift
            drop_breadvolt_lift()
            state.breadvolt = False
            if dropped:
                ui.notify("Moved the circuit back down", type="positive")
        refresh()

    def apply_breadvolt_lift() -> int:
        """Slide the placement up until it clears the cover. Return the rows moved."""
        delta = breadvolt_lift(state.board, state.components, state.wires)
        if not delta:
            return 0
        state.components, state.wires = shift_placement(
            state.board, state.components, state.wires, delta,
        )
        state.breadvolt_shift += delta
        return delta

    def drop_breadvolt_lift() -> None:
        if not state.breadvolt_shift:
            return
        state.components, state.wires = shift_placement(
            state.board, state.components, state.wires, -state.breadvolt_shift,
        )
        state.breadvolt_shift = 0

    def on_board_change(key: str) -> None:
        if key == state.board_key:  # programmatic change from import, nothing to clear
            return
        state.board_key = key
        state.components = []
        state.wires = []
        state.breadvolt_shift = 0
        refresh()

    def add_parsed(comps: list[Component]) -> bool:
        """Append components. Return False and notify if a ref is already on the board."""
        existing = {c.ref for c in state.components}
        dupes = [c.ref for c in comps if c.ref in existing]
        if dupes:
            ui.notify(f"Already placed: {', '.join(dupes)}", type="negative")
            return False
        state.components.extend(comps)
        return True

    def add_component() -> None:
        try:
            comps = parse_components(comp_in.value or "")
        except ValueError as ex:
            ui.notify(str(ex), type="negative")
            return
        if not add_parsed(comps):
            return
        comp_in.value = ""
        refresh()

    def add_new_wires(wires: list[tuple[str, str]]) -> int:
        """Append jumpers that are not already present. Return how many were added."""
        have = {tuple(sorted(pair)) for pair in state.wires}
        added = 0
        for a, b in wires:
            key = tuple(sorted((a, b)))
            if key in have:
                continue
            state.wires.append((a, b))
            have.add(key)
            added += 1
        return added

    def load_circuit(key: str | None) -> None:
        if not key:
            return
        circuit = CIRCUITS[key]
        board = BOARDS.get(circuit.board)
        if board is None:
            ui.notify(f"Unknown board {circuit.board!r}", type="negative")
            circuit_select.set_value(None)
            return
        try:
            comps = parse_components(circuit.lines)
            wires = [(board.normalize(a), board.normalize(b)) for a, b in parse_wires(circuit.wires)]
        except ValueError as ex:
            ui.notify(str(ex), type="negative")
            circuit_select.set_value(None)
            return
        if circuit.board != state.board_key:
            state.board_key = circuit.board
            state.components = []
            state.wires = []
            state.breadvolt_shift = 0
            board_select.set_value(circuit.board)
        if state.breadvolt and board.breadvolt is not None:
            delta = state.breadvolt_shift or breadvolt_lift(board, comps, wires)
            try:
                comps, wires = shift_placement(board, comps, wires, delta)
            except ValueError as ex:
                ui.notify(str(ex), type="negative")
                circuit_select.set_value(None)
                return
        else:
            delta = 0
        existing = {c.ref for c in state.components}
        overlap = [c.ref for c in comps if c.ref in existing]
        if overlap and len(overlap) != len(comps):
            ui.notify(f"Already placed: {', '.join(overlap)}", type="negative")
            circuit_select.set_value(None)
            refresh()
            return
        if not overlap:
            state.components.extend(comps)
        if delta and not state.breadvolt_shift:
            state.breadvolt_shift = delta
        added_wires = add_new_wires(wires)
        circuit_select.set_value(None)
        refresh()
        if overlap and not added_wires:
            ui.notify(f"{circuit.label} is already placed", type="negative")
            return
        ui.notify(
            f"Added {circuit.label} ({len(comps)} components, {added_wires} wires)",
            type="positive",
        )

    def add_wire() -> None:
        try:
            a, b = parse_wire(wire_in.value)
            a, b = state.board.normalize(a), state.board.normalize(b)
        except ValueError as ex:
            ui.notify(str(ex), type="negative")
            return
        state.wires.append((a, b))
        wire_in.value = ""
        refresh()

    def remove_last() -> None:
        if state.components:
            state.components.pop()
        refresh()

    def clear_all() -> None:
        state.components.clear()
        state.wires.clear()
        state.breadvolt_shift = 0
        refresh()

    def probe() -> None:
        try:
            nl = state.netlist()
            a = nl.board.normalize(probe_a.value)
            b = nl.board.normalize(probe_b.value)
        except ValueError as ex:
            probe_out.text = str(ex)
            return
        connected = nl.continuity(a, b)
        probe_out.text = f"{a} and {b}: {'connected' if connected else 'not connected'}"

    def loaded_circuit() -> Circuit | None:
        refs = {c.ref for c in state.components}
        found = None
        for circuit in CIRCUITS.values():
            needed = {c.ref for c in parse_components(circuit.lines)}
            if needed and needed <= refs and circuit.links:
                found = circuit
        return found

    def shifted_links(links: tuple[LinkCheck, ...]) -> tuple[LinkCheck, ...]:
        delta = state.breadvolt_shift
        if not delta:
            return links
        board = state.board
        return tuple(
            LinkCheck(board.shift_hole(check.a, delta), board.shift_hole(check.b, delta),
                      check.connected, check.note)
            for check in links
        )

    def check_circuit() -> None:
        circuit = loaded_circuit()
        probe_list.clear()
        if circuit is None:
            probe_out.text = "Load a circuit before checking continuity."
            continuity_panel.text = "Continuity"
            with probe_list:
                ui.label("Run Check circuit to list every probe.").classes("text-caption text-grey")
            return
        results = run_link_checks(state.netlist(), shifted_links(circuit.links))
        failed = [r for r in results if not r.ok]
        passed = len(results) - len(failed)
        summary = f"{circuit.label}: {passed} passed, {len(failed)} failed"
        probe_out.text = summary
        continuity_panel.text = f"Continuity · {passed} passed, {len(failed)} failed"
        continuity_panel.value = True
        with probe_list:
            ordered = sorted(results, key=lambda r: r.ok)
            for result in ordered:
                expect = "connected" if result.check.connected else "open"
                mark = "pass" if result.ok else "fail"
                css = "text-positive" if result.ok else "text-negative"
                note = f" — {result.check.note}" if result.check.note else ""
                header = f"[{mark}] {result.check.a}-{result.check.b} {expect}"
                with ui.expansion(header, value=False).props("dense").classes(f"w-full {css}"):
                    ui.label(f"measured {result.measured}{note}").classes("text-caption")

    def export_json() -> None:
        json_box.value = netlist_to_json()

    def import_json() -> None:
        try:
            netlist_from_json(json_box.value)
        except Exception as ex:  # any parse or validation error goes back to the user
            ui.notify(f"Import failed: {ex}", type="negative")
            return
        board_select.value = state.board_key
        refresh()
        ui.notify("Netlist imported", type="positive")

    refresh()


if __name__ in {"__main__", "__mp_main__"}:
    ui.run(
        title="Circuit board auditor",
        host=os.environ.get("HOST", "127.0.0.1"),
        port=int(os.environ.get("PORT", "8080")),
        reload=False,
        dark=False,
    )

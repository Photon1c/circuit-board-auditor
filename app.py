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
from core.presets import CIRCUITS, Circuit, incompatibility, place_on
from core.render import render_svg
from core.summary import audit_dict, describe_layout, legend_lines

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
        self.analyzer = False
        # Default clips suit the Ultrasonic Sensor-ESP preset:
        # CH0 TRIG (B5), CH1 ECHO raw (B11), CH2 ECHO at D5 (A12),
        # GND common (A13).
        self.analyzer_map = "CH0=B5 CH1=B11 CH2=A12 GND=A13"
        # Shaded footprints from the loaded preset (label, corner, corner).
        self.covers: tuple[tuple[str, str, str], ...] = ()

    @property
    def board(self) -> Board:
        return BOARDS[self.board_key]

    def netlist(self) -> Netlist:
        return Netlist(self.board, list(self.components), list(self.wires))


state = Session()


def netlist_to_json() -> str:
    probes = None
    if state.analyzer:
        try:
            probes = parse_analyzer_map(state.analyzer_map, state.board)
        except ValueError:
            probes = None
    return json.dumps({
        "board": state.board_key,
        "components": [asdict(c) for c in state.components],
        "wires": [list(w) for w in state.wires],
        "breadvolt": state.breadvolt,
        "breadvolt_shift": state.breadvolt_shift,
        "analyzer": state.analyzer,
        "analyzer_map": state.analyzer_map,
        "covers": [list(c) for c in state.covers],
        # Audit section: every wire (J-ids match the drawing and the
        # Connections text) and every connected group, in plain data.
        # Import ignores it; it exists so the physical wires can be
        # checked against something other than the picture.
        "audit": audit_dict(state.board, state.netlist(),
                            analyzer=probes, covers=state.covers),
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
    state.analyzer = bool(data.get("analyzer", False))
    state.analyzer_map = str(data.get("analyzer_map", state.analyzer_map))
    state.covers = tuple(
        (str(c[0]), str(c[1]), str(c[2]))
        for c in data.get("covers", []) if len(c) == 3
    )


def parse_analyzer_map(text: str, board: Board) -> dict[str, str]:
    """'CH0=B5 CH1=B11 GND=A13' -> {'CH0': 'B5', ...}, holes validated."""
    probes: dict[str, str] = {}
    for token in (text or "").replace(",", " ").split():
        if "=" not in token:
            raise ValueError(f"Analyzer probe {token!r} needs the form CH0=B5")
        ch, hole = token.split("=", 1)
        ch = ch.strip().upper()
        if ch != "GND" and not (ch.startswith("CH") and ch[2:].isdigit()
                                and 0 <= int(ch[2:]) <= 7):
            raise ValueError(f"Unknown analyzer channel {ch!r} (use CH0-CH7 or GND)")
        hole = board.normalize(hole.strip())
        if not board.has_hole(hole):
            raise ValueError(f"Analyzer probe {ch} names hole {hole!r}, "
                             "which this board does not have")
        probes[ch] = hole
    return probes


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
<script>
  // Instant hover tooltip for the board drawing. Native SVG <title>
  // tooltips are slow and often never fire inside the app, so elements
  // carry data-tip and this follows the mouse with it instead.
  document.addEventListener('mouseover', (e) => {
    const el = e.target.closest ? e.target.closest('[data-tip]') : null;
    let tip = document.getElementById('svg-tip');
    if (!el) { if (tip) tip.style.display = 'none'; return; }
    if (!tip) {
      tip = document.createElement('div');
      tip.id = 'svg-tip';
      tip.style.cssText = 'position:fixed;z-index:9999;pointer-events:none;' +
        'background:#1f1b16;color:#fffdf8;padding:3px 8px;border-radius:4px;' +
        'font-size:12px;display:none;max-width:22rem';
      document.body.appendChild(tip);
    }
    tip.textContent = el.getAttribute('data-tip');
    tip.style.display = 'block';
  });
  document.addEventListener('mousemove', (e) => {
    const tip = document.getElementById('svg-tip');
    if (tip && tip.style.display === 'block') {
      tip.style.left = (e.clientX + 12) + 'px';
      tip.style.top = (e.clientY + 14) + 'px';
    }
  });
  document.addEventListener('mouseout', (e) => {
    if (e.target.closest && e.target.closest('[data-tip]')) {
      const tip = document.getElementById('svg-tip');
      if (tip) tip.style.display = 'none';
    }
  });
</script>
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
            analyzer_box = ui.checkbox(
                "Logic analyzer",
                value=state.analyzer,
                on_change=lambda e: on_analyzer(e.value),
            )
            analyzer_in = ui.input(
                "Analyzer probes: CHn=HOLE",
                value=state.analyzer_map,
                on_change=lambda e: on_analyzer_map(e.value),
            ).classes("w-full")
            analyzer_note = ui.label(
                "Draws the analyzer clips and leads on the board (view only; "
                "not part of the netlist). Defaults suit the Ultrasonic preset: "
                "CH0 TRIG, CH1 ECHO raw, CH2 ECHO at the MCU pin, GND common."
            ).classes("text-caption text-grey")
            analyzer_status = ui.label("").classes("text-caption text-negative")
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
            layout_panel = ui.expansion("Connections (text)", value=True).classes("w-full").props("dense")
            with layout_panel:
                layout_list = ui.column().classes("w-full gap-0")
            legend_panel = ui.expansion("Legend", value=False).classes("w-full").props("dense")
            with legend_panel:
                legend_list = ui.column().classes("w-full gap-0")
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
                 "It goes on the board already selected when every hole it needs is there. "
                 "When it does not fit, the app says why and switches to the board "
                 "the example was drawn for.")
        ui.label("On that board, BreadVolt covers rows 1–10 and its pins occupy "
                 "power-rail holes 1–4. A red rail the circuit uses is +9V; one with "
                 "nothing on it reads (off). Black rails are ground. "
                 "Rail hole 5 is skipped. Turning it on slides "
                 "the placed circuit up to the first row above the cover.")
        ui.label("Logic analyzer: tick the box to draw the analyzer clips "
                 "(CH0-CH7, GND) on the holes named in the probe box, for "
                 "example CH0=B5 CH1=B11 CH2=A12 GND=A13. It is a viewing "
                 "aid for bench probing and changes no nets or checks.")
        ui.label("Wire box: HOLE-HOLE, for example E1-F1")
        ui.label("Components, checks, and continuity sit on the right. Each heading and each line opens for the detail.")
        ui.label("Reading the board: the Connections (text) panel on the right "
                 "lists every part, jumper, and connected group in words, and "
                 "the Legend explains the dots, lines, rings, and shading. "
                 "Hover any hole, wire, part outline, clip, or shaded area "
                 "on the drawing to read what it is.")
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
        probes = None
        analyzer_error = ""
        if state.analyzer:
            try:
                probes = parse_analyzer_map(state.analyzer_map, state.board)
            except ValueError as ex:
                analyzer_error = str(ex)
        analyzer_status.text = analyzer_error
        if analyzer_in.value != state.analyzer_map:
            analyzer_in.value = state.analyzer_map
        analyzer_in.set_visibility(state.analyzer)
        analyzer_note.set_visibility(state.analyzer)
        if analyzer_box.value != state.analyzer:
            analyzer_box.value = state.analyzer
        board_view.content = render_svg(
            state.board, state.netlist(),
            breadvolt=use_breadvolt(), analyzer=probes,
            covers=state.covers or None)
        layout_list.clear()
        with layout_list:
            ui.label(
                describe_layout(state.board, state.netlist(),
                                analyzer=probes, covers=state.covers)
            ).classes("font-mono text-caption").style("white-space: pre-wrap")
        legend_list.clear()
        with legend_list:
            for line in legend_lines(state.board):
                ui.label(line).classes("text-caption")
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

    def on_analyzer(value: bool) -> None:
        state.analyzer = bool(value)
        refresh()

    def on_analyzer_map(text: str) -> None:
        state.analyzer_map = text or ""
        refresh()

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
        state.covers = ()
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
        preset_board = BOARDS.get(circuit.board)
        if preset_board is None:
            ui.notify(f"Unknown board {circuit.board!r}", type="negative")
            circuit_select.set_value(None)
            return
        target = state.board
        reason = incompatibility(target, circuit)
        if reason is not None and state.board_key != circuit.board:
            ui.notify(
                f"Board/circuit not compatible ({reason}); "
                f"switching to preset board: {preset_board.name}",
                type="warning",
            )
            target = preset_board
            reason = incompatibility(target, circuit)
        if reason is not None:
            ui.notify(f"{circuit.label} does not fit on {target.name}: {reason}", type="negative")
            circuit_select.set_value(None)
            return
        placed = place_on(target, circuit)
        if placed is None:  # incompatibility() above already found every missing hole
            circuit_select.set_value(None)
            return
        comps, wires = placed
        if target is not state.board:
            state.board_key = circuit.board
            state.components = []
            state.wires = []
            state.breadvolt_shift = 0
            board_select.set_value(circuit.board)
        if state.breadvolt and target.breadvolt is not None:
            delta = state.breadvolt_shift or breadvolt_lift(target, comps, wires)
            try:
                comps, wires = shift_placement(target, comps, wires, delta)
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
        if circuit.analyzer_map:
            state.analyzer = True
            state.analyzer_map = circuit.analyzer_map
        state.covers = circuit.covers
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
        state.covers = ()
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

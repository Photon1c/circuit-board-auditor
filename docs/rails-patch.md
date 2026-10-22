# Handoff: add power rail support to the breadboard dashboard

**For:** Cursor (or any coding agent)
**Project:** `breadboard_dash`, based on v0.3 (36 tests passing)
**Status before this work:** rails are stored in board JSON but ignored by the net model, layout, and rendering.

## Why this matters

Boards like the California JOS 830 have power rails along the sides. A rail hole is electrically connected to the other holes on that rail. Right now the app treats rail holes as isolated, so continuity and short checks give wrong answers for any circuit that uses them. This must be fixed before the 830 board can be used.

## Current state (read these files first)

- `boards/jos_830.json` has a `rails` list of four entries, each `{"name": "...", "holes": 50}`. The loader stores them as-is.
- `core/board.py`:
  - `Board.rails` is a tuple of raw dicts. Nothing reads it.
  - `_validate()` does not check rails.
  - `strip_id()` only handles breadboard strips, perfboard holes, and stripboard columns or rows. It has no rail case.
  - `positions()` lays out only the main grid. Rails have no positions.
- `core/nets.py`: `Netlist.__post_init__` builds union-find from `board.holes()` and `board.strip_id()`. Rail holes are not in `board.holes()`, so they are never connected.
- `core/render.py`: draws only `board.holes()`. Rails are not drawn.
- `core/entry.py` and `core/board.py` `normalize()`: hole names must match `^([A-Za-z])(\d+)$`, so a rail hole name needs a single letter plus a number.

## Decisions to implement

1. **Rail schema.** Each rail in JSON is an object:
   ```json
   {"id": "K", "name": "+ left", "holes": 50, "segments": [[1, 50]]}
   ```
   - `id`: one letter, unique on the board, and not one of the `columns`. For the JOS 830 use `K`, `L`, `M`, `N`.
   - `name`: human label, shown in the UI.
   - `holes`: number of rail positions, numbered 1 to `holes`.
   - `segments` (optional): list of `[first, last]` ranges, each electrically continuous. If absent, the whole rail is one segment. Some boards split rails at the middle. The JOS segmentation is **unconfirmed**, so default to one segment.
2. **Hole names.** A rail hole is `<id><n>`, for example `K1`, `K50`, `N12`. Update `normalize()` and `has_hole()` so they accept rail ids as valid columns, and keep the existing rejections for out-of-range numbers.
3. **Connectivity.** In `strip_id()`, a rail hole returns `rail:<id>:seg<k>`, where `k` is the index of the segment containing `n`. Rails are then merged by the same union-find as strips.
4. **Validation.** In `_validate()`, check that:
   - rail ids are single letters,
   - rail ids are unique and do not collide with `columns`,
   - each `holes` value is at least 1,
   - each segment is inside `1..holes` and segments do not overlap.
   Raise `ValueError` with the rail id in the message.
5. **Layout.** In `positions()`, place rails outside the main grid: left rails at negative x (offset -2 and -1 for a pair), right rails after the last column with a gap of 2. Rail holes run vertically with `y` following the same bottom-to-top or top-to-bottom direction as rows. Keep the existing main-grid coordinates unchanged, so current tests still pass.
6. **Rendering.** In `render_svg()`, draw rail holes with the same circles and add a rail id label above each rail. Include rails in `holes` iteration for the drawing pass only, not for the main grid tests.
7. **Entry and probe.** No parser change is needed beyond accepting the new hole names. The probe and component entry should work on rail holes with no UI change.

## Acceptance tests (add to `tests/test_rails.py`)

- `K1` and `K50` are connected when the rail has one segment.
- Rail `K` and rail `L` are not connected.
- With two segments `[[1, 25], [26, 50]]`, `K25` and `K26` are not connected, and `K1` and `K25` are.
- A rail hole never connects to a breadboard column hole. Check that `K1` is not connected to `A1`.
- `normalize("k1") == "K1"` and `has_hole("K51")` is False.
- Validation rejects a rail id that matches a column letter, such as `A`.
- Validation rejects overlapping segments.
- `positions()` on `jos_830.json` puts left rails at x < 0 and right rails at x > the last column.
- `render_svg()` on `jos_830.json` draws 630 + 200 = 830 circles.
- A short check: a source with `+` on rail `K` and `-` on rail `K` reports `supply_short` (existing check, new path).

All 36 existing tests must still pass.

## Acceptance check on the JOS board

After the change, `Board.load("boards/jos_830.json")` should report 830 holes, and `strip_id("A1") == strip_id("E1")`, `strip_id("E1") != strip_id("F1")`, and `strip_id("K1") == strip_id("K50")`. The row numbering assumption (row 1 at bottom) is still unconfirmed, so do not hard-code it beyond what `row_direction` already says.

## Out of scope

- Splitting rails at the centre of the board. Support it through `segments` only.
- Any change to the stripboard or perfboard logic.
- Netlify, deployment, or authentication.
- Confirming the JOS rail count or segmentation. That is a physical check the user will do.

## Notes for the implementer

- Keep the code style of the existing modules: `from __future__ import annotations`, dataclasses, and `ValueError` for bad input.
- Don't change the JSON keys already in use: `name`, `type`, `rows`, `columns`, `origin`, `column_direction`, `row_direction`, `strips`, `center_gap`, `rails`, `specs`.
- Run `pytest` from the project root. The pytest config is in `pytest.ini`.

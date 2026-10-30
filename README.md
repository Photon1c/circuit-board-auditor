# circuit-board-auditor

Run breadboard, perfboard, and stripboard continuity checks on a visualized dashboard.

Place parts and jumper wires on a drawing of the real board, then probe two holes the way you would with a multimeter. The drawing, the netlist, and the checks stay in the browser tab until you export them.

## Install and start

From this directory, in PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python app.py
```

On macOS or Linux, activate with `source .venv/bin/activate` instead.

Then open http://127.0.0.1:8080 . Leave that terminal running while you work. Press Ctrl+C to stop. If port 8080 is already in use, start on another port:

```powershell
$env:PORT = "8081"
python app.py
```

## The page

The window is a wide, three-column layout:

- **Left:** board choice, part entry, wires, the probe, and JSON import/export.
- **Center:** the board. It scales to the height of the window.
- **Right:** Components, Checks, and Continuity. Each heading is closed until you open it. Inside Components and Continuity, each line is closed too: open a part to see its pins, or a probe to see the measurement and note.

Press **H** for the part catalog (pin names and a copy-paste example for each kind). Press H again to close it. The help key is ignored while you are typing in a box.

## Place a part

One line is one part. Paste several lines to add them together, then press **Add components**.

```
REF KIND [VALUE] PIN=HOLE PIN=HOLE ...
```

```
R1 resistor 470k 1=E1 2=J1
D1 led green anode=J4 cathode=J5
C1 capacitor 100u +=A3 -=A6
```

- `REF` is the name you want on the board (`R1`, `U1`, `D1`). It must be unique.
- `KIND` is one of `resistor`, `capacitor`, `led`, `diode`, `pot`, `source`, `ic`, or `module`. It is not case-sensitive.
- `VALUE` is optional and is kept as you typed it (`470k`, `GREEN`, `100u`).
- `PIN=HOLE` uses the pin name from the catalog. Hole names look like `E1` or `K15`.
- `PIN=nc` leaves that pin out of the circuit on purpose.

LED `anode` is the long leg and `cathode` is the short leg. A pot's pins are `A`, `W`, and `B`. An IC uses the pin numbers printed on the datasheet (`PIN1`, `1`, and so on).

The drawing marks polarity inside the holes. An LED or diode has a cross in the anode and a bar in the cathode. Every capacitor has a cross in the positive hole and a bar in the negative hole. Name those pins `+` and `-`, or use pin 1 and pin 2, where pin 1 is positive. A resistor has no polarity mark.

**Remove last component** drops the most recently added part. **Clear all** drops every part and wire.

## Jumper wires

Type two holes in the wire box and press **Add wire**:

```
E1-F1
```

A wire is a conductor. A resistor is not: the probe does not beep through a part, only through copper and jumpers.

## Probe and check a circuit

**Probe** answers whether two holes you type are connected.

**Check circuit** runs the continuity list for a loaded example, such as the LED chaser. The summary stays next to the button. The individual lines open under **Continuity** on the right. Failures are listed first. Each line says what should be connected or open, what was measured, and why that pair matters.

**Add circuit** places a whole example, including its jumper wires. **LED chaser** switches to the California JOS board and places the 555, 4017, ULN2003, the passives, the LEDs, and the jumpers. Choosing it again does not duplicate parts; it only fills in jumpers that are missing.

## California JOS board

Row 1 is at the bottom. Columns run J to A from left to right. J–F and E–A are separate strips, so `F1` is not connected to `E1`. Hole names use that same row on both halves: `J1` lines up with `E1`. The printed numbers on the right edge run the other way, so the bottom of that edge reads 63 and the top reads 1.

Power rails:

| Rail | Side | Polarity |
| --- | --- | --- |
| K | outer left | negative |
| L | inner left, beside J | positive |
| M | inner right, beside A | negative |
| N | outer right | positive |

Each rail is one electrical run from hole 1 to hole 63. Hole 5 is missing on every rail (there is no `K5`, `L5`, `M5`, or `N5`). Hole 4 is still connected to hole 6.

On the drawing a positive rail is red, and so is every jumper that lands on it. A negative rail is black, and so is every jumper that lands on it. Other jumpers stay dark. With BreadVolt on, a red rail the circuit uses reads +9V and a black rail reads GND. A red rail with nothing on it reads (off). The LED chaser’s battery feeds the right rail only, so the left red rail reads (off). The shaded block covers the terminal rows only. The two positive rails stay separate, and the two ground rails meet only where a jumper joins them.

**BreadVolt** is available only on this board. Turn it on when the module is plugged into the bottom of the board:

- Its pins occupy power-rail holes 1–4.
- Rows 1–10 are covered, so parts and wires there are reported as blocked.
- Anything already placed slides up so its lowest hole sits on row 11, just above the cover. Turning BreadVolt off slides that circuit back down.

The two BreadVolt channels are independent. The checkbox does not join the left positive rail to the right one. Join grounds yourself, as the LED chaser does with `K15-M11`.

## What the checks mean

Open **Checks** on the right. The heading shows the error and warning counts.

- **invalid_hole** — a pin or wire names a hole this board does not have.
- **hole_conflict** — two pins are in the same hole.
- **supply_short** — a power source has `+` and `-` on the same net.
- **pin_short** — two pins of the same part share a net. This includes ties you made on purpose, such as a 555's trigger and threshold tied together. Read the message and keep the ones you intended.
- **dangling_pin** — a pin's net has nothing else on it. Unused pins of an inserted IC stay listed so you can see they are open.
- **breadvolt** — a pin or wire is under the BreadVolt, or in a hole its pins occupy. This appears only while BreadVolt is on.

## Save and reload

**Export** writes the board, parts, wires, and BreadVolt state into the JSON box. Copy that text somewhere safe. **Import** loads it back, including which board it belongs to. Switching boards from the Board menu clears the parts on the page.

## Run the tests

With the virtual environment active, from this directory:

```powershell
pytest
```

## Boards

| File | Board |
| --- | --- |
| `boards/breadboard_170.json` | 170-hole breadboard |
| `boards/california_jos_breadboard_870_solderless.json` | California JOS 830-point breadboard, with rails and BreadVolt |
| `boards/gennel_stripboard_368.json` | GENNEL 50×70 stripboard |
| `boards/patikil_perfboard_144.json` | PATIKIL 1.2 in perfboard |

A board file describes the holes and which ones are connected. The drawing and the probe both use that file.

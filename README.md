# DS2 SotFS controller fix

A one-byte patch for **Dark Souls II: Scholar of the First Sin** on PC. It fixes
controllers that move too slowly, give no input at all, or make the camera spin.

The underlying bug: DS2 binds player 1 to the first raw DirectInput controller
it finds, and **never** falls back to XInput (Xbox-style) after that. The patch
makes the game skip its DirectInput gamepad scan, so it only uses XInput. Steam
Input then provides a clean, full-range Xbox pad.

Tested with a PowerA wireless Switch controller over Bluetooth plus Steam Input.

## Who this is for

- **Switch Pro / PowerA / other non-Xbox pads:** you get slow walking or camera
  with Steam Input off, or nothing at all with Steam Input on.
- **Xbox pads with no input or a spinning camera:** some other "game controller"
  device (wheel, flight stick, vJoy, RGB or keyboard software) is being grabbed
  instead of your pad. This is the case the usual "disable HID-compliant game
  controllers in Device Manager" advice works around.

A plain Xbox controller with nothing else attached already works in DS2. The
patch doesn't change anything for it.

## Usage

Requires Python 3 on Windows (stdlib only). Close the game first.

```
py ds2_xinput_patch.py           # apply
py ds2_xinput_patch.py status
py ds2_xinput_patch.py restore   # back to the untouched exe
py ds2_xinput_patch.py --game-dir "D:\SteamLibrary\steamapps\common\Dark Souls II Scholar of the First Sin\Game"
```

Then, for any **non-Xbox** controller, open DS2 in your Steam Library and go to
**Properties → Controller → Enable Steam Input**. After the patch the game only
talks to Xbox-style (XInput) pads, so Steam Input (or DS4Windows, etc.) has to do
the translation.

Notes:
- The patcher only touches the current Steam build (SHA-256 `0045931b…3131`).
  It keeps the original as `DarkSoulsII.exe.original`. If another patch had
  already modified the exe, that copy is saved as
  `DarkSoulsII.exe.replaced-<timestamp>`.
- **"Verify integrity of game files" in Steam undoes the patch.** Just run it again.

## What's actually going on

Switch-style pads have two report modes:

| Mode | Used by | Sticks |
|------|---------|--------|
| `0x3F` simple HID | DirectInput | declared 0–65535, but full tilt doesn't reach full scale in practice |
| `0x30` full report | Steam (Switch support on) | 12-bit, calibrated, full range; DirectInput can't decode it |

In `DarkSoulsII.exe`:

- At startup, `IDirectInput8::EnumDevices(DI8DEVCLASS_GAMECTRL)` (`0x140ef6990`)
  collects every non-Xbox game controller. Player 1's pad is created on the first one.
- `0x140f06740` only tries XInput when the pad has **no** DirectInput device, so
  once a DirectInput device is bound, XInput is never used.

The result:
- **Steam Input off:** the game reads the `0x3F` report. The stick never hits full
  scale, and the game's 36% per-axis deadzone (`(|v|-0.36)/0.64`) then subtracts
  more, which gives walk speed and a slow camera.
- **Steam Input on:** Steam switches the pad to `0x30`, so the DirectInput view
  freezes at center. The game keeps reading that dead device and ignores Steam's
  virtual Xbox pad, which gives no input at all.

The patch changes the `jne` that guards the scan (VA `0x140ef69a6`, file offset
`0xEF5DA6`, `75`→`EB`) into a `jmp`. The game already takes that path in its
built-in DualShock mode. Keyboard and mouse are opened separately and still work.

### About "deadzone center" patches

A radial-deadzone exe patch that has circulated rewrites the stick code at
`0x140b09617`. It accumulates `x²+y²` in `xmm4`, but never zeroes `xmm4` before
the **left** stick, so the left stick reads garbage and stops working. If the
deadzone bothers you, a Steam Input layout with anti-deadzone is the safer route.

## Diagnostics

`tools/padprobe.py` shows what Windows sees from each controller and records the
real stick range:

```
py tools\padprobe.py 30    # spin both sticks for 30 s
```

If it reports full report mode (`0x30`), Steam currently owns the controller.

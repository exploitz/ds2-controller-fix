"""DS2 SotFS: stop the game from grabbing raw DirectInput gamepads (XInput only).

Why: DarkSoulsII.exe enumerates DirectInput game controllers at startup and binds
player 1 to the first one it finds. Once a pad is bound to DirectInput the game
never falls back to XInput (FUN 0x140f06740 bails out when the pad already has a
DirectInput device). With a Switch-style controller that means:
  * Steam Input OFF -> game reads the controller's simple HID report, whose sticks
    never reach the edge of their declared range -> walk speed / slow camera.
  * Steam Input ON  -> Steam switches the controller to its full report mode, the
    DirectInput view freezes, and the game keeps reading that dead device instead
    of Steam's virtual Xbox pad -> no input at all.

The patch turns the `jne` that guards the DirectInput EnumDevices call
(VA 0x140ef69a6) into a `jmp`, the same path the game already takes in its
DualShock mode. Keyboard and mouse are opened separately and are unaffected.

Usage (Windows Python):
    py ds2_xinput_patch.py            # apply (default)
    py ds2_xinput_patch.py status
    py ds2_xinput_patch.py restore    # put the untouched original exe back
    py ds2_xinput_patch.py --game-dir "D:\\...\\Game" apply
"""
import argparse
import hashlib
import shutil
import sys
import time
from pathlib import Path

DEFAULT_GAME_DIR = Path(
    r"C:\Program Files (x86)\Steam\steamapps\common\Dark Souls II Scholar of the First Sin\Game"
)
ORIGINAL_SHA256 = "0045931b8914504531b7864a9488d396dc50cbaf524964016e1d69c3d1173131"
PATCH_OFFSET = 0xEF5DA6  # file offset of VA 0x140ef69a6: jne (0x75) -> jmp (0xEB)
JNE, JMP = 0x75, 0xEB


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def with_byte(data: bytes, value: int) -> bytes:
    return data[:PATCH_OFFSET] + bytes([value]) + data[PATCH_OFFSET + 1 :]


def state(data: bytes) -> str:
    if sha256(data) == ORIGINAL_SHA256:
        return "original"
    if len(data) > PATCH_OFFSET and data[PATCH_OFFSET] == JMP and sha256(with_byte(data, JNE)) == ORIGINAL_SHA256:
        return "xinput-only patch"
    return "unknown (modified by something else)"


def write_exe(exe: Path, data: bytes) -> None:
    try:
        _ = exe.write_bytes(data)
    except PermissionError:
        sys.exit(f"Cannot write {exe} - close Dark Souls II (and run as admin if Steam is in Program Files).")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    _ = ap.add_argument("action", nargs="?", default="apply", choices=["apply", "status", "restore"])
    _ = ap.add_argument("--game-dir", type=Path, default=DEFAULT_GAME_DIR)
    args = ap.parse_args()
    action: str = args.action
    game_dir: Path = args.game_dir

    exe = game_dir / "DarkSoulsII.exe"
    backup = game_dir / "DarkSoulsII.exe.original"
    if not exe.exists():
        sys.exit(f"Not found: {exe}")
    current = exe.read_bytes()
    print(f"DarkSoulsII.exe: {state(current)}")

    if action == "status":
        return

    # Find a pristine copy to work from.
    if sha256(current) == ORIGINAL_SHA256:
        original = current
        if not backup.exists():
            _ = shutil.copy2(exe, backup)
            print(f"Backed up original -> {backup.name}")
    elif backup.exists() and sha256(backup.read_bytes()) == ORIGINAL_SHA256:
        original = backup.read_bytes()
    else:
        sys.exit("No untouched DarkSoulsII.exe found (hash mismatch). Verify game files in Steam first.")

    target = original if action == "restore" else with_byte(original, JMP)
    if current == target:
        print("Nothing to do.")
        return
    if state(current).startswith("unknown"):
        # Keep whatever third-party patch was there instead of silently discarding it.
        keep = game_dir / f"DarkSoulsII.exe.replaced-{time.strftime('%Y%m%d-%H%M%S')}"
        _ = shutil.copy2(exe, keep)
        print(f"Saved the previously modified exe -> {keep.name}")
    write_exe(exe, target)
    print(f"DarkSoulsII.exe: {state(exe.read_bytes())}")


if __name__ == "__main__":
    main()

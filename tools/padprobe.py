"""Controller probe: shows what Windows (and therefore DirectInput games like DS2)
actually receives from each gamepad, and the true stick range it reaches.

Usage (Windows Python, no packages needed):
    py padprobe.py            # list devices + one snapshot
    py padprobe.py 30         # also record min/max for 30 seconds - spin both sticks
"""
import ctypes as C
import ctypes.wintypes as W
import sys
import time

hid = C.WinDLL("hid")
setupapi = C.WinDLL("setupapi")
k32 = C.WinDLL("kernel32", use_last_error=True)
winmm = C.WinDLL("winmm")


class GUID(C.Structure):
    _fields_ = [("d1", W.DWORD), ("d2", W.WORD), ("d3", W.WORD), ("d4", C.c_ubyte * 8)]


class SP_DEVICE_INTERFACE_DATA(C.Structure):
    _fields_ = [("cbSize", W.DWORD), ("guid", GUID), ("flags", W.DWORD), ("res", C.c_void_p)]


class HIDD_ATTRIBUTES(C.Structure):
    _fields_ = [("Size", W.ULONG), ("VendorID", W.USHORT), ("ProductID", W.USHORT), ("Version", W.USHORT)]


class HIDP_CAPS(C.Structure):
    _fields_ = [("Usage", W.USHORT), ("UsagePage", W.USHORT),
                ("InputReportByteLength", W.USHORT), ("OutputReportByteLength", W.USHORT),
                ("FeatureReportByteLength", W.USHORT), ("Reserved", W.USHORT * 17),
                ("NumberLinkCollectionNodes", W.USHORT), ("NumberInputButtonCaps", W.USHORT),
                ("NumberInputValueCaps", W.USHORT), ("NumberInputDataIndices", W.USHORT),
                ("rest", W.USHORT * 9)]


class HIDP_VALUE_CAPS(C.Structure):
    _fields_ = [("UsagePage", W.USHORT), ("ReportID", C.c_ubyte), ("IsAlias", C.c_ubyte),
                ("BitField", W.USHORT), ("LinkCollection", W.USHORT), ("LinkUsage", W.USHORT),
                ("LinkUsagePage", W.USHORT), ("IsRange", C.c_ubyte), ("IsStringRange", C.c_ubyte),
                ("IsDesignatorRange", C.c_ubyte), ("IsAbsolute", C.c_ubyte), ("HasNull", C.c_ubyte),
                ("Reserved", C.c_ubyte), ("BitSize", W.USHORT), ("ReportCount", W.USHORT),
                ("Reserved2", W.USHORT * 5), ("UnitsExp", W.ULONG), ("Units", W.ULONG),
                ("LogicalMin", W.LONG), ("LogicalMax", W.LONG), ("PhysicalMin", W.LONG),
                ("PhysicalMax", W.LONG), ("UsageMin", W.USHORT), ("UsageMax", W.USHORT),
                ("u", W.USHORT * 6)]


class JOYINFOEX(C.Structure):
    _fields_ = [(n, W.DWORD) for n in ("dwSize", "dwFlags", "x", "y", "z", "r", "u", "v", "buttons",
                                        "buttonNumber", "pov", "res1", "res2")]


class JOYCAPSW(C.Structure):
    _fields_ = [("wMid", W.WORD), ("wPid", W.WORD), ("szPname", W.WCHAR * 32),
                ("wXmin", W.UINT), ("wXmax", W.UINT), ("wYmin", W.UINT), ("wYmax", W.UINT),
                ("wZmin", W.UINT), ("wZmax", W.UINT), ("wNumButtons", W.UINT),
                ("wPeriodMin", W.UINT), ("wPeriodMax", W.UINT), ("wRmin", W.UINT), ("wRmax", W.UINT),
                ("wUmin", W.UINT), ("wUmax", W.UINT), ("wVmin", W.UINT), ("wVmax", W.UINT),
                ("wCaps", W.UINT), ("wMaxAxes", W.UINT), ("wNumAxes", W.UINT), ("wMaxButtons", W.UINT),
                ("szRegKey", W.WCHAR * 32), ("szOEMVxD", W.WCHAR * 260)]


USAGE_NAMES = {0x30: "X", 0x31: "Y", 0x32: "Z", 0x33: "Rx", 0x34: "Ry", 0x35: "Rz",
               0x36: "Slider", 0x37: "Dial", 0x39: "Hat"}
k32.CreateFileW.restype = W.HANDLE
setupapi.SetupDiGetClassDevsW.restype = W.HANDLE
INVALID = W.HANDLE(-1).value


def hid_game_devices():
    g = GUID()
    hid.HidD_GetHidGuid(C.byref(g))
    hdi = setupapi.SetupDiGetClassDevsW(C.byref(g), None, None, 0x12)
    i = 0
    while True:
        did = SP_DEVICE_INTERFACE_DATA(cbSize=C.sizeof(SP_DEVICE_INTERFACE_DATA))
        if not setupapi.SetupDiEnumDeviceInterfaces(W.HANDLE(hdi), None, C.byref(g), i, C.byref(did)):
            break
        i += 1
        need = W.DWORD()
        setupapi.SetupDiGetDeviceInterfaceDetailW(W.HANDLE(hdi), C.byref(did), None, 0, C.byref(need), None)
        buf = C.create_string_buffer(need.value)
        C.cast(buf, C.POINTER(W.DWORD))[0] = 8  # cbSize on x64
        if not setupapi.SetupDiGetDeviceInterfaceDetailW(W.HANDLE(hdi), C.byref(did), buf, need, None, None):
            continue
        path = C.wstring_at(C.addressof(buf) + 4)
        h = k32.CreateFileW(path, 0xC0000000, 3, None, 3, 0x40000000, None)
        if h in (None, INVALID):
            h = k32.CreateFileW(path, 0, 3, None, 3, 0x40000000, None)
        if h in (None, INVALID):
            continue
        pp = C.c_void_p()
        if not hid.HidD_GetPreparsedData(W.HANDLE(h), C.byref(pp)):
            k32.CloseHandle(W.HANDLE(h))
            continue
        caps = HIDP_CAPS()
        hid.HidP_GetCaps(pp, C.byref(caps))
        if caps.UsagePage == 1 and caps.Usage in (4, 5, 8):
            yield path, h, pp, caps
        else:
            hid.HidD_FreePreparsedData(pp)
            k32.CloseHandle(W.HANDLE(h))


def describe(path, h, pp, caps):
    attr = HIDD_ATTRIBUTES(Size=C.sizeof(HIDD_ATTRIBUTES))
    hid.HidD_GetAttributes(W.HANDLE(h), C.byref(attr))
    name = C.create_unicode_buffer(128)
    hid.HidD_GetProductString(W.HANDLE(h), name, C.sizeof(name))
    kind = {4: "joystick", 5: "gamepad", 8: "multi-axis"}[caps.Usage]
    print(f"\n[HID {kind}] '{name.value}' VID={attr.VendorID:04X} PID={attr.ProductID:04X}")
    print(f"  path={path}")
    print(f"  input report bytes={caps.InputReportByteLength} buttonCaps={caps.NumberInputButtonCaps} "
          f"valueCaps={caps.NumberInputValueCaps}")
    n = W.USHORT(caps.NumberInputValueCaps)
    vc = (HIDP_VALUE_CAPS * max(1, n.value))()
    hid.HidP_GetValueCaps(0, vc, C.byref(n), pp)
    vals = []
    for v in vc[: n.value]:
        lo = v.UsageMin
        hi = v.UsageMax if v.IsRange else v.UsageMin
        for u in range(lo, hi + 1):
            vals.append((v.UsagePage, u, v.ReportID, v.LogicalMin, v.LogicalMax, v.BitSize))
            print(f"  axis {USAGE_NAMES.get(u, hex(u)):>6} page={v.UsagePage:#x} report={v.ReportID:#04x} "
                  f"bits={v.BitSize} logical=[{v.LogicalMin}, {v.LogicalMax}]")
    return vals


def record(h, pp, caps, vals, seconds):
    """Read raw input reports and track the real min/max of every axis."""
    buf = C.create_string_buffer(caps.InputReportByteLength)
    ov = (C.c_byte * 32)()
    ev = k32.CreateEventW(None, True, False, None)
    C.cast(ov, C.POINTER(C.c_void_p))[3] = ev  # OVERLAPPED.hEvent at offset 24
    stats: dict[str, list[int]] = {}  # axis -> [rest, min, max]
    spans: dict[str, tuple[int, int]] = {}  # axis -> declared (min, max)
    report_ids: dict[int, int] = {}
    first_raw = None

    def track(axis: str, x: int, lo: int, hi: int) -> None:
        s = stats.setdefault(axis, [x, x, x])
        s[1], s[2] = min(s[1], x), max(s[2], x)
        spans[axis] = (lo, hi)

    end = time.time() + seconds
    while time.time() < end:
        got = W.DWORD()
        k32.ResetEvent(ev)
        ok = k32.ReadFile(W.HANDLE(h), buf, len(buf), C.byref(got), ov)
        if not ok and C.get_last_error() != 997:  # ERROR_IO_PENDING
            print("  ReadFile failed", C.get_last_error())
            return
        if k32.WaitForSingleObject(ev, 250) != 0:
            k32.CancelIo(W.HANDLE(h))
            continue
        k32.GetOverlappedResult(W.HANDLE(h), ov, C.byref(got), True)
        raw = buf.raw[: got.value]
        if first_raw is None:
            first_raw = raw
        report_ids[raw[0]] = report_ids.get(raw[0], 0) + 1
        if raw[0] == 0x30 and len(raw) >= 12:
            # Nintendo full report: 12-bit packed sticks at bytes 6-8 (left) and 9-11 (right).
            for nx, ny, o in (("full LX", "full LY", 6), ("full RX", "full RY", 9)):
                track(nx, raw[o] | (raw[o + 1] & 0xF) << 8, 0, 4095)
                track(ny, raw[o + 1] >> 4 | raw[o + 2] << 4, 0, 4095)
            continue
        for p, u, rid, lmin, lmax, _bits in vals:
            if raw[0] != rid or p != 1:
                continue
            val = W.ULONG()
            if hid.HidP_GetUsageValue(0, p, 0, u, C.byref(val), pp, buf, got) == 0x110000:
                track(f"hid {USAGE_NAMES.get(u, hex(u))}", val.value, lmin, lmax)
    if first_raw:
        print(f"  first raw report: {first_raw[:16].hex(' ')} ...")
    print(f"  report ids seen: { {hex(k): v for k, v in report_ids.items()} }")
    if 0x30 in report_ids:
        print("  NOTE: controller is in Nintendo FULL report mode (0x30) - something (normally Steam) owns it.\n"
              "        DirectInput only decodes report 0x3F, so DirectInput games see frozen, centered sticks.")
    for axis, (rest, lo, hi) in stats.items():
        lmin, lmax = spans[axis]
        span = lmax - lmin or 1
        print(f"  {axis:>10}: rest={rest:6d} min={lo:6d} max={hi:6d}  "
              f"-> reaches {100 * (lo - lmin) / span:5.1f}% .. {100 * (hi - lmin) / span:5.1f}% of declared range")


def winmm_view():
    print("\n[WinMM / DirectInput joystick view]")
    for jid in range(16):
        caps = JOYCAPSW()
        if winmm.joyGetDevCapsW(jid, C.byref(caps), C.sizeof(caps)) != 0:
            continue
        info = JOYINFOEX(dwSize=C.sizeof(JOYINFOEX), dwFlags=0xFF)
        r = winmm.joyGetPosEx(jid, C.byref(info))
        print(f"  id {jid}: '{caps.szPname}' axes={caps.wNumAxes} buttons={caps.wNumButtons} "
              f"X[{caps.wXmin},{caps.wXmax}] status={r} pos x={info.x} y={info.y} z={info.z} "
              f"r={info.r} u={info.u} v={info.v} btn={info.buttons:#x}")


def main():
    secs = float(sys.argv[1]) if len(sys.argv) > 1 else 1.0
    winmm_view()
    devs = list(hid_game_devices())
    if not devs:
        print("\nNo HID joystick/gamepad devices found.")
    for path, h, pp, caps in devs:
        vals = describe(path, h, pp, caps)
        if secs > 1:
            print(f"  >>> recording {secs:.0f}s: spin BOTH sticks in full circles, push to every edge <<<")
        record(h, pp, caps, vals, secs)


if __name__ == "__main__":
    main()

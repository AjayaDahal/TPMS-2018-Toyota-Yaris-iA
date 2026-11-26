#!/usr/bin/env python3
"""Audit the v2 ESP32 pin map (02-firmware/v2/include/pins_v2.h).

Checks the DOIT ESP32 DevKit V1 (30-pin, WROOM-32) rules that are easy to get wrong:
strapping pins, input-only pins, flash pins, boot-time glitches on power controls, ADC1 for analog inputs, UART0,
duplicates, and that the CC1101 / I2C / buzzer pins still match the v1 panel (02-firmware/bringup/include/pins.h).
It also checks the carrier PCB's netlist (01-hardware/v2/carrier/carrier_design.py): every pin reaches its part
(directly or through its one series resistor) and the nc / USB pins stay unconnected.

    python 01-hardware/v2/check_pinmap.py             # audit; exit code 1 if any rule fails
    python 01-hardware/v2/check_pinmap.py --selftest  # the rules must catch the pin errors of the earlier v2 drafts
"""
import argparse
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
V2_PINS = ROOT / "02-firmware" / "v2" / "include" / "pins_v2.h"
V1_PINS = ROOT / "02-firmware" / "bringup" / "include" / "pins.h"

DEVKIT_30PIN = {36, 39, 34, 35, 32, 33, 25, 26, 27, 14, 12, 13, 23, 22, 1, 3, 21, 19, 18, 5, 17, 16, 4, 2, 15}
FLASH_PINS = set(range(6, 12))
INPUT_ONLY = {34, 35, 36, 39}            # no output driver, no internal pull resistors
ADC1 = {32, 33, 34, 35, 36, 39}          # ADC2 can't be read while Wi-Fi runs
STRAPPING = {0, 2, 5, 12, 15}
BOOT_ACTIVITY = {1, 3, 5, 14, 15}        # drive a signal or PWM during boot
SHARED_WITH_V1 = ("PIN_SPI_SCK", "PIN_SPI_MISO", "PIN_SPI_MOSI", "PIN_CC_CS", "PIN_CC_GDO0", "PIN_CC_GDO2",
                  "PIN_I2C_SDA", "PIN_I2C_SCL", "PIN_BUZZER")
DIRECTIONS = {"in", "out", "analog", "io", "usb", "nc"}
PIN_LINE = re.compile(r"^\s*constexpr\s+int\s+(PIN_\w+)\s*=\s*(\d+)\s*;\s*(?://\s*(?:\[([^\]]*)\])?\s*(.*))?$")


def parse(text):
    pins = []
    for number, line in enumerate(text.splitlines(), 1):
        m = PIN_LINE.match(line)
        if not m:
            continue
        tags = [t.strip() for t in m.group(3).split(",")] if m.group(3) else []
        pins.append(dict(name=m.group(1), gpio=int(m.group(2)), dir=tags[0] if tags else None, flags=set(tags[1:]),
                         note=(m.group(4) or "").strip(), line=number))
    return pins


def audit(pins, v1=None):
    """Returns (errors, warnings), each a list of (rule, message)."""
    errors, warnings = [], []
    users = {}
    for p in pins:
        users.setdefault(p["gpio"], []).append(p["name"])
    for gpio, names in sorted(users.items()):
        if len(names) > 1:
            errors.append(("R1 duplicate", f"GPIO{gpio} is used by {', '.join(names)}"))

    for p in pins:
        g, name, d, flags = p["gpio"], p["name"], p["dir"], p["flags"]
        if d not in DIRECTIONS:
            errors.append(("R0 tag", f"{name}: missing or unknown direction tag [{d}]"))
        if g in FLASH_PINS:
            errors.append(("R2 flash", f"{name}: GPIO{g} is wired to the module's SPI flash"))
        elif g not in DEVKIT_30PIN:
            errors.append(("R2 devkit", f"{name}: GPIO{g} is not broken out on the 30-pin DOIT DevKit V1"))
        if g in INPUT_ONLY and d not in ("in", "analog"):
            errors.append(("R3 input-only", f"{name}: GPIO{g} is input-only but tagged [{d}]"))
        if g == 12 and d != "nc":
            errors.append(("R4 GPIO12", f"{name}: GPIO12 selects the flash voltage at reset; leave it unconnected"))
        if g == 2 and d != "nc" and ("bootlow" not in flags or "idlehigh" in flags):
            errors.append(("R5 GPIO2", f"{name}: GPIO2 must be low or floating at reset, or serial flashing fails"))
        if "power" in flags and (g in BOOT_ACTIVITY or g in STRAPPING):
            errors.append(("R6 power glitch", f"{name}: power control on GPIO{g}, which toggles or straps at boot"))
        if "power" in flags and not flags & {"pullup", "pulldown"}:
            errors.append(("R6 power default", f"{name}: power control needs an external pull resistor so its state "
                                               "is defined while the ESP32 resets or is being flashed"))
        if d == "analog" and g not in ADC1:
            errors.append(("R7 ADC1", f"{name}: GPIO{g} is not on ADC1 (ADC2 is unusable while Wi-Fi runs)"))
        if g in (1, 3) and d != "usb":
            errors.append(("R8 UART0", f"{name}: GPIO{g} is UART0 to the DevKit's USB bridge (log, flashing)"))
        if g in (36, 39) and d == "in" and "poll" not in flags:
            warnings.append(("W1 errata 3.11", f"{name}: GPIO{g} is pulled low for ~80 ns when the ADC or Wi-Fi "
                                               "powers up; poll it instead of using an interrupt"))
        if g in INPUT_ONLY and d == "in" and "v1" not in flags and "pullup" not in flags:
            warnings.append(("W2 no pull", f"{name}: GPIO{g} has no internal pull resistor; fine only if the source "
                                           "drives both levels"))

    if v1 is not None:
        v1_by_name = {p["name"]: p["gpio"] for p in v1}
        v2_by_name = {p["name"]: p for p in pins}
        for name in SHARED_WITH_V1:
            if name not in v2_by_name:
                errors.append(("R9 v1 match", f"{name} is missing from the v2 map"))
            elif name in v1_by_name and v2_by_name[name]["gpio"] != v1_by_name[name]:
                errors.append(("R9 v1 match", f"{name}: v2 GPIO{v2_by_name[name]['gpio']} but v1 GPIO{v1_by_name[name]} "
                                              "(the CC1101 driver and decoder are reused unchanged)"))
    return errors, warnings


# The two pin maps proposed earlier in this project's v2 plan (system_plan.json history), reduced to the lines
# that were wrong. The audit must flag each one; --selftest proves it.
EARLIER_DRAFTS = {
    "draft 1: left blinker on IO35": ("R1 duplicate", """
constexpr int PIN_CC_GDO2 = 35;    // [in,v1]
constexpr int PIN_BLINK_L = 35;    // [in,pullup]
constexpr int PIN_BLINK_R = 39;    // [in,pullup]
"""),
    "draft 2: HS-CAN receive on IO2": ("R5 GPIO2", """
constexpr int PIN_CAN_RX = 2;      // [in,idlehigh]  SN65HVD230 R output idles high (recessive)
"""),
    "draft 2: power latch without a defined reset state": ("R6 power default", """
constexpr int PIN_PWR_LATCH = 27;  // [out,power]
"""),
    "Pi enable on a boot-glitching pin": ("R6 power glitch", """
constexpr int PIN_PI_EN = 14;      // [out,power,pulldown]
"""),
    "ACC sense on an ADC2 pin": ("R7 ADC1", """
constexpr int PIN_ACC_SENSE = 26;  // [analog]
"""),
    "LED on the flash-voltage strapping pin": ("R4 GPIO12", """
constexpr int PIN_LED_L = 12;      // [out]
"""),
}


def selftest():
    ok = True
    for label, (rule, text) in EARLIER_DRAFTS.items():
        errors, _ = audit(parse(text))
        caught = any(r == rule for r, _ in errors)
        print(f"  {'caught' if caught else 'MISSED'}  {label}  ->  {rule}")
        ok &= caught
    errors, _ = audit(parse(V2_PINS.read_text(encoding="utf-8")), parse(V1_PINS.read_text(encoding="utf-8")))
    print(f"  {'clean ' if not errors else 'ERRORS'}  current pins_v2.h")
    bad = check_carrier(parse(V2_PINS.read_text(encoding="utf-8")), _mutated_carrier())
    print(f"  {'caught' if bad else 'MISSED'}  carrier netlist with two GPIOs swapped")
    return ok and not errors and bool(bad)


# ---------------------------------------------------------------------- carrier netlist check
# Where each pin of pins_v2.h must end up on the carrier PCB (01-hardware/v2/carrier/carrier_design.py): the DevKit
# pin's net must reach this part pin directly or through one series resistor (the cut points).
CARRIER_ENDPOINTS = {
    "PIN_SPI_SCK": "A2.5", "PIN_SPI_MISO": "A2.7", "PIN_SPI_MOSI": "A2.6", "PIN_CC_CS": "A2.4",
    "PIN_CC_GDO0": "A2.3", "PIN_CC_GDO2": "A2.8", "PIN_I2C_SDA": "U802.15", "PIN_I2C_SCL": "U802.14",
    "PIN_BUZZER": "Q603.1", "PIN_LED_L": "Q601.1", "PIN_LED_R": "Q602.1", "PIN_BTN": "J4.1",
    "PIN_BLINK_L": "U501.4", "PIN_BLINK_R": "U502.4", "PIN_ACC_SENSE": "R518.2", "PIN_GPS_RX": "J7.3",
    "PIN_GPS_TX": "J7.2", "PIN_PI_UART_RX": "J6.2", "PIN_PI_UART_TX": "J6.3", "PIN_PI_INHIBIT": "Q201.1",
    "PIN_PI_PGOOD": "R214.2",
}
CARRIER_DIR = ROOT / "01-hardware" / "v2" / "carrier"


def _load_carrier():
    sys.path.insert(0, str(CARRIER_DIR))
    try:
        import carrier_design  # noqa: PLC0415
    finally:
        sys.path.pop(0)
    return carrier_design


def _mutated_carrier():
    import copy  # noqa: PLC0415
    cd = copy.deepcopy({"parts": _load_carrier().PARTS, "symbols": _load_carrier().CUSTOM_SYMBOLS})
    a1 = next(p for p in cd["parts"] if p["ref"] == "A1")
    a1["pins"]["8"], a1["pins"]["11"] = a1["pins"]["11"], a1["pins"]["8"]          # IO25 <-> IO14
    return cd


def check_carrier(pins, carrier=None):
    """Errors where the carrier's netlist does not wire a pins_v2.h pin to its function (or wires an nc pin)."""
    if carrier is None:
        cd = _load_carrier()
        carrier = {"parts": cd.PARTS, "symbols": cd.CUSTOM_SYMBOLS}
    parts = {p["ref"]: p for p in carrier["parts"]}
    spec = carrier["symbols"]["ESP32_DevKit_30pin"]
    gpio_pin = {}
    for entry in spec["left"] + spec["right"]:
        m = re.search(r"IO(\d+)", entry[1])
        if m:
            gpio_pin[int(m.group(1))] = entry[0]
    a1 = parts["A1"]["pins"]
    errors = []
    for p in pins:
        g, name = p["gpio"], p["name"]
        net = a1.get(gpio_pin.get(g, ""), None)
        if p["dir"] in ("nc", "usb") or name == "PIN_STATUS_LED":
            if net is not None:
                errors.append(f"{name}: GPIO{g} must stay unconnected on the carrier, but is on net {net}")
            continue
        target = CARRIER_ENDPOINTS.get(name)
        if target is None:
            errors.append(f"{name}: no expected carrier endpoint listed")
            continue
        ref, pin = target.split(".")
        tnet = parts[ref]["pins"][pin]
        reach = {net}
        for q in parts.values():                       # one series resistor (cut point)
            if q["sym"] == "Device:R" and net in q["pins"].values() and not q["dnp"]:
                reach |= set(q["pins"].values())
        if net is None or tnet not in reach:
            errors.append(f"{name}: GPIO{g} (DevKit pin {gpio_pin.get(g)}, net {net}) does not reach {target} "
                          f"(net {tnet})")
    return errors


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()
    if args.selftest:
        good = selftest()
        print("self-test passed" if good else "self-test FAILED")
        return 0 if good else 1

    pins = parse(V2_PINS.read_text(encoding="utf-8"))
    errors, warnings = audit(pins, parse(V1_PINS.read_text(encoding="utf-8")))
    print(f"{V2_PINS.relative_to(ROOT)}: {len(pins)} pins")
    print(f"{'GPIO':>4}  {'name':<20} {'tags':<26} note")
    for p in sorted(pins, key=lambda p: p["gpio"]):
        tags = ",".join([p["dir"] or "?"] + sorted(p["flags"]))
        print(f"{p['gpio']:>4}  {p['name']:<20} [{tags:<24}] {p['note']}")
    unused = sorted(DEVKIT_30PIN - {p["gpio"] for p in pins})
    print(f"unassigned DevKit GPIOs: {', '.join(map(str, unused)) if unused else 'none'}")
    for rule, msg in warnings:
        print(f"WARNING {rule}: {msg}")
    for rule, msg in errors:
        print(f"ERROR   {rule}: {msg}")
    carrier_errors = check_carrier(pins)
    for msg in carrier_errors:
        print(f"ERROR   R10 carrier: {msg}")
    print(f"carrier netlist (01-hardware/v2/carrier/carrier_design.py): "
          f"{'matches' if not carrier_errors else 'MISMATCH'}")
    errors += [("R10 carrier", m) for m in carrier_errors]
    print(f"{len(errors)} errors, {len(warnings)} warnings")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())

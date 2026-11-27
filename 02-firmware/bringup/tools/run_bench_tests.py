#!/usr/bin/env python3
"""Orchestrate live ESP32 + CC1101 + USRP B205mini bench tests (T4, T5, T6)."""

import argparse
import re
import subprocess
import sys
import threading
import time
from pathlib import Path
import serial

TOOLS_DIR = Path(__file__).resolve().parent
SIM_SCRIPT = TOOLS_DIR / "b205_sim_tpms.py"


class SerialCapture:
    def __init__(self, port: str, baud: int = 115200):
        self.ser = serial.Serial(port, baud, timeout=0.05)
        # Keep ESP32 out of bootloader/reset when opening
        self.ser.dtr = False
        self.ser.rts = False
        time.sleep(0.2)
        self.ser.reset_input_buffer()
        self.lines: list[str] = []
        self._buf = ""
        self._lock = threading.Lock()
        self._stop = False
        self._thread = threading.Thread(target=self._reader, daemon=True)
        self._thread.start()

    def _reader(self):
        while not self._stop:
            data = self.ser.read(4096)
            if data:
                text = data.decode("utf-8", errors="replace")
                with self._lock:
                    self._buf += text
                    while "\n" in self._buf:
                        line, self._buf = self._buf.split("\n", 1)
                        self.lines.append(line.rstrip("\r"))

    def drain(self) -> list[str]:
        time.sleep(0.15)
        with self._lock:
            out = self.lines[:]
            self.lines.clear()
            return out

    def send(self, ch: bytes):
        self.ser.write(ch)
        self.ser.flush()

    def close(self):
        self._stop = True
        self._thread.join(timeout=1.0)
        self.ser.close()


def run_sim(args_list: list[str]) -> subprocess.CompletedProcess:
    cmd = ["python3", "-s", str(SIM_SCRIPT)] + args_list
    return subprocess.run(cmd, capture_output=True, text=True)


def run_t4_cw(cap: SerialCapture, gains: list[float]):
    print("\n=== T4: 315.000 MHz CW RSSI & GDO2 SWEEP ===")
    cap.drain()
    for _ in range(2):
        cap.send(b"d")
        time.sleep(0.2)
    idle_lines = cap.drain()
    print("Idle baseline:")
    for l in idle_lines:
        if "CC1101 dump:" in l or "[" in l:
            print(" ", l)

    for g in gains:
        cap.drain()
        proc = subprocess.Popen(
            ["python3", "-s", str(SIM_SCRIPT), "--mode", "cw", "--cw-ms", "1200", "--count", "1", "--interval", "0.1", "--gain", str(g)],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        # Poll 'd' across the 1.2s CW pulse (including UHD init ~1.5s)
        t0 = time.time()
        while proc.poll() is None and time.time() - t0 < 8.0:
            cap.send(b"d")
            time.sleep(0.2)
        out, _ = proc.communicate(timeout=5)
        lines = cap.drain()
        rssis = []
        gdo2s = []
        for l in lines:
            m = re.search(r"RSSI=(-?\d+) dBm GDO0=(\d) GDO2=(\d)", l)
            if m:
                rssis.append(int(m.group(1)))
                gdo2s.append(int(m.group(3)))
        peak_rssi = max(rssis) if rssis else None
        max_gdo2 = max(gdo2s) if gdo2s else None
        print(f"CW gain={g:4.1f} dB -> rc={proc.returncode}, samples={len(rssis)}, peak_RSSI={peak_rssi} dBm, max_GDO2={max_gdo2}, all_RSSI={rssis}")
        if proc.returncode != 0:
            print(out)


def run_t5_sweep(cap: SerialCapture, gains: list[float], label: str = "T5"):
    print(f"\n=== {label}: SIMULATED EG53MA4 ASK/OOK SWEEP (10 frames/step) ===")
    summary = []
    for g in gains:
        cap.drain()
        res = run_sim([
            "--mode", "eg53ma4",
            "--id", "0x123456",
            "--psi", "31.9",
            "--temp-f", "77",
            "--flags", "0x058F2001",
            "--repeats", "2",
            "--count", "5",
            "--interval", "0.5",
            "--gain", str(g),
        ])
        time.sleep(0.5)
        lines = cap.drain()
        eg_lines = [l for l in lines if "EG53MA4 id" in l]
        other_lines = [l for l in lines if "MAN" in l or "DMAN" in l or "OOK bw" in l or "raw " in l]
        stats_lines = [l for l in lines if "bursts " in l]
        rssis = []
        for l in eg_lines:
            m = re.search(r"rssi\s+(-?\d+)\s+dBm", l)
            if m:
                rssis.append(int(m.group(1)))
        rssi_str = f"{min(rssis)}..{max(rssis)} dBm" if rssis else "n/a"
        print(f"gain={g:4.1f} dB -> decoded {len(eg_lines)}/10 (rc={res.returncode}), rssi={rssi_str}, non_eg={len(other_lines)}")
        if eg_lines:
            print("  sample:", eg_lines[0])
        if stats_lines:
            print("  stats :", stats_lines[-1])
        if res.returncode != 0:
            print("  SIM ERR:", res.stdout, res.stderr)
        summary.append((g, len(eg_lines), rssis, len(other_lines)))

    # Second synthetic sensor check at strongest gain that decoded (or gains[0])
    best_g = next((g for g, n, _, _ in summary if n >= 6), gains[0])
    cap.drain()
    res2 = run_sim([
        "--mode", "eg53ma4",
        "--id", "0xABCDEF",
        "--psi", "35.0",
        "--temp-f", "68",
        "--flags", "0x058F2002",
        "--repeats", "2",
        "--count", "3",
        "--interval", "0.5",
        "--gain", str(best_g),
    ])
    time.sleep(0.5)
    lines2 = cap.drain()
    eg2 = [l for l in lines2 if "EG53MA4 id ABCDEF" in l]
    print(f"2nd sensor (ID ABCDEF, 35.0 psi, 68 F) @ gain={best_g:.1f} dB -> decoded {len(eg2)}/6 (rc={res2.returncode})")
    if eg2:
        print("  sample:", eg2[0])

    # If 0 decodes at gains[0], do a 1-burst raw pulse dump diagnostic
    if summary and summary[0][1] == 0:
        print("\n--- Diagnostic raw pulse dump ('r') at strong gain ---")
        cap.send(b"r")
        time.sleep(0.1)
        cap.drain()
        run_sim(["--mode", "eg53ma4", "--id", "0x123456", "--repeats", "1", "--count", "1", "--interval", "0.3", "--gain", str(gains[0])])
        time.sleep(0.5)
        raw_lines = cap.drain()
        cap.send(b"r")
        for l in raw_lines[:40]:
            print(" ", l)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--port", default="/dev/ttyUSB0")
    p.add_argument("--t4", action="store_true")
    p.add_argument("--t5", action="store_true")
    p.add_argument("--idle-sec", type=float, default=0.0)
    p.add_argument("--label", default="T5")
    p.add_argument("--cw-gains", default="15,25,35,45")
    p.add_argument("--tx-gains", default="50,40,30,20,10,0")
    args = p.parse_args()

    cap = SerialCapture(args.port)
    try:
        if args.idle_sec > 0:
            print(f"\n=== IDLE CHECK ({args.idle_sec:.1f} s) ===")
            cap.drain()
            time.sleep(args.idle_sec)
            cap.send(b"d")
            time.sleep(0.3)
            for l in cap.drain():
                print(" ", l)
        if args.t4:
            run_t4_cw(cap, [float(x) for x in args.cw_gains.split(",")])
        if args.t5:
            run_t5_sweep(cap, [float(x) for x in args.tx_gains.split(",")], label=args.label)
    finally:
        cap.close()


if __name__ == "__main__":
    main()

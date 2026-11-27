"""Live RF Bench backend for 04-viewer: ESP32 serial monitor + USRP B205mini TX runner."""

from __future__ import annotations

import glob
import re
import subprocess
import threading
import time
from collections import deque
from datetime import datetime
from pathlib import Path

try:
    import serial
except ImportError:  # pragma: no cover - verified installed on Linux host
    serial = None

ROOT = Path(__file__).resolve().parents[1]
SIM_SCRIPT = ROOT / "02-firmware" / "bringup" / "tools" / "b205_sim_tpms.py"


def build_eg53ma4_payload(sensor_id: int, psi: float, temp_f: int, flags: int) -> bytes:
    """Build 10-byte Schrader EG53MA4 payload with 8-bit sum checksum."""
    kpa = psi * 6.894757
    pressure_raw = max(0, min(255, round(kpa / 2.5)))
    temp_byte = max(0, min(255, int(temp_f)))
    b = bytearray([
        (flags >> 24) & 0xFF,
        (flags >> 16) & 0xFF,
        (flags >> 8) & 0xFF,
        flags & 0xFF,
        (sensor_id >> 16) & 0xFF,
        (sensor_id >> 8) & 0xFF,
        sensor_id & 0xFF,
        pressure_raw,
        temp_byte,
        0,
    ])
    b[9] = sum(b[:9]) & 0xFF
    return bytes(b)


def list_serial_ports() -> list[str]:
    ports = sorted(glob.glob("/dev/ttyUSB*") + glob.glob("/dev/ttyACM*"))
    return ports


def now_hms() -> str:
    return datetime.now().strftime("%H:%M:%S.%f")[:-3]


class RfBenchManager:
    """Thread-safe coordinator between ESP32 serial telemetry and USRP B205mini TX bursts."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._ser = None
        self._stop = False
        self._reader_thread: threading.Thread | None = None
        self._tx_thread: threading.Thread | None = None
        self._next_tx_id = 1
        self._next_rx_id = 1
        self._tx_active = False
        self._last_dump_at = 0.0

        self.esp = {
            "connected": False,
            "port": "",
            "baud": 115200,
            "error": "",
            "raw_dump": False,
            "squelch": None,
            "mode_idx": 0,
            "mode_name": "OOK bw203k 16kBd",
            "cc_ok": None,
            "partnum": "",
            "version": "",
            "marcstate": "",
            "rssi_dbm": None,
            "noise_floor_dbm": None,
            "gdo0": None,
            "gdo2": None,
            "bursts": 0,
            "frames": 0,
            "edges": 0,
            "dropped": 0,
            "uptime_s": 0,
            "regs": {},
        }
        self.usrp = {
            "detected": False,
            "serial": "",
            "product": "",
            "name": "",
            "tx_busy": False,
            "last_checked": "",
            "error": "",
        }
        self.rssi_history: deque[dict] = deque(maxlen=150)
        self.tx_log: deque[dict] = deque(maxlen=100)
        self.rx_frames: deque[dict] = deque(maxlen=150)
        self.rx_other: deque[dict] = deque(maxlen=60)
        self.serial_log: deque[dict] = deque(maxlen=250)

        self.probe_usrp()

    def _append_serial(self, line: str, kind: str = "info") -> None:
        self.serial_log.append({"ts": now_hms(), "kind": kind, "line": line})

    def probe_usrp(self) -> dict:
        try:
            res = subprocess.run(
                ["uhd_find_devices"],
                capture_output=True,
                text=True,
                timeout=6.0,
            )
            out = (res.stdout or "") + "\n" + (res.stderr or "")
            m_ser = re.search(r"serial:\s*(\S+)", out)
            m_prod = re.search(r"product:\s*(\S+)", out)
            m_name = re.search(r"name:\s*(\S+)", out)
            detected = res.returncode == 0 and bool(m_ser)
            with self._lock:
                self.usrp["detected"] = detected
                self.usrp["serial"] = m_ser.group(1) if m_ser else ""
                self.usrp["product"] = m_prod.group(1) if m_prod else ""
                self.usrp["name"] = m_name.group(1) if m_name else ""
                self.usrp["last_checked"] = now_hms()
                self.usrp["error"] = "" if detected else "No UHD Devices Found"
        except Exception as exc:
            with self._lock:
                self.usrp["detected"] = False
                self.usrp["last_checked"] = now_hms()
                self.usrp["error"] = str(exc)
        return self.get_state()["usrp"]

    def connect(self, port: str, baud: int = 115200) -> dict:
        if serial is None:
            return {"ok": False, "error": "pyserial is not installed"}
        if not port:
            ports = list_serial_ports()
            if not ports:
                return {"ok": False, "error": "No /dev/ttyUSB* or /dev/ttyACM* device found"}
            port = ports[0]

        self.disconnect()
        try:
            ser = serial.Serial(port, baud, timeout=0.05)
            ser.dtr = False
            ser.rts = False
            time.sleep(0.15)
            ser.reset_input_buffer()
        except Exception as exc:
            with self._lock:
                self.esp["connected"] = False
                self.esp["port"] = port
                self.esp["error"] = str(exc)
            return {"ok": False, "error": str(exc)}

        with self._lock:
            self._ser = ser
            self._stop = False
            self._last_dump_at = 0.0
            self.esp["connected"] = True
            self.esp["port"] = port
            self.esp["baud"] = baud
            self.esp["error"] = ""
            self._append_serial(f"[viewer] Connected to {port} @ {baud}", "sys")

        self._reader_thread = threading.Thread(target=self._reader_loop, daemon=True)
        self._reader_thread.start()
        return {"ok": True, "port": port}

    def disconnect(self) -> dict:
        self._stop = True
        t = self._reader_thread
        if t and t.is_alive():
            t.join(timeout=1.0)
        self._reader_thread = None
        with self._lock:
            if self._ser is not None:
                try:
                    self._ser.close()
                except Exception:
                    pass
                self._ser = None
            if self.esp["connected"]:
                self._append_serial("[viewer] Disconnected", "sys")
            self.esp["connected"] = False
        return {"ok": True}

    def send_cmd(self, cmd: str) -> dict:
        with self._lock:
            ser = self._ser
            if not ser or not self.esp["connected"]:
                return {"ok": False, "error": "ESP32 serial not connected"}
            try:
                if cmd == "reset":
                    ser.dtr = False
                    ser.rts = True
                    time.sleep(0.1)
                    ser.rts = False
                    self._append_serial("[viewer] ESP32 hardware reset pulsed", "sys")
                    return {"ok": True}
                if cmd in ("d", "p", "r", "g", "h"):
                    ser.write(cmd.encode("ascii"))
                    ser.flush()
                    return {"ok": True}
                return {"ok": False, "error": f"Unknown command: {cmd}"}
            except Exception as exc:
                self.esp["error"] = str(exc)
                return {"ok": False, "error": str(exc)}

    def _reader_loop(self) -> None:
        buf = ""
        while not self._stop:
            with self._lock:
                ser = self._ser
                raw_dump = self.esp["raw_dump"]
            if not ser:
                break
            try:
                now = time.monotonic()
                if not raw_dump and now - self._last_dump_at >= 1.0:
                    self._last_dump_at = now
                    ser.write(b"d")
                    ser.flush()
                chunk = ser.read(4096)
            except Exception as exc:
                with self._lock:
                    self.esp["connected"] = False
                    self.esp["error"] = str(exc)
                    self._append_serial(f"[viewer] Serial error: {exc}", "err")
                break

            if chunk:
                buf += chunk.decode("utf-8", errors="replace")
                while "\n" in buf:
                    line, buf = buf.split("\n", 1)
                    self._parse_line(line.rstrip("\r"))
            else:
                time.sleep(0.02)

    def _record_rssi(self, rssi: int, gdo2: int | None) -> None:
        self.rssi_history.append({
            "t": time.time(),
            "ts": now_hms(),
            "rssi": rssi,
            "gdo2": gdo2 if gdo2 is not None else self.esp.get("gdo2", 0),
            "tx_active": self._tx_active,
        })

    def _correlate_rx(self, rx: dict) -> None:
        now_epoch = rx["t"]
        rx_id_hex = rx["id"]
        best = None
        for tx in self.tx_log:
            if tx["mode"] != "eg53ma4":
                continue
            if now_epoch - tx["t"] > 15.0 or now_epoch < tx["t"] - 0.5:
                continue
            if tx["sensor_id"].upper() == rx_id_hex.upper():
                best = tx
                break
        if best is not None:
            best["rx_matched"] += 1
            rx["matched_tx_id"] = best["id"]
            rx["exact_match"] = (
                abs(best["psi"] - rx["psi"]) <= 0.4
                and best["temp_f"] == rx["temp_f"]
                and best["flags"].upper() == rx["flags"].upper()
            )
        else:
            rx["matched_tx_id"] = None
            rx["exact_match"] = False

    def _parse_line(self, line: str) -> None:
        if not line:
            return
        with self._lock:
            kind = "info"

            if m := re.search(r"CC1101:\s*PARTNUM\s+0x([0-9A-Fa-f]+)\s+VERSION\s+0x([0-9A-Fa-f]+)", line):
                pn, ver = f"0x{m.group(1).upper()}", f"0x{m.group(2).upper()}"
                self.esp["partnum"] = pn
                self.esp["version"] = ver
                self.esp["cc_ok"] = "NOT FOUND" not in line
                kind = "cc"

            elif m := re.search(r"CC1101:\s*state\s+0x([0-9A-Fa-f]+).*?noise floor\s+(-?\d+)\s+dBm", line):
                self.esp["marcstate"] = f"0x{m.group(1).upper()}"
                nf = int(m.group(2))
                self.esp["noise_floor_dbm"] = nf
                self.esp["rssi_dbm"] = nf
                self._record_rssi(nf, self.esp.get("gdo2"))
                kind = "cc"

            elif m := re.search(r"^mode\s+(\d+):\s*(.+?)(?:\s{2,}\((.+)\))?$", line):
                self.esp["mode_idx"] = int(m.group(1))
                self.esp["mode_name"] = m.group(2).strip()
                kind = "cc"

            elif m := re.search(
                r"CC1101 dump:\s*PARTNUM=(0x[0-9A-Fa-f]+)\s+VERSION=(0x[0-9A-Fa-f]+)\s+"
                r"MARCSTATE=(0x[0-9A-Fa-f]+)\s+RSSI=(-?\d+)\s+dBm\s+GDO0=(\d)\s+GDO2=(\d)",
                line,
            ):
                self.esp["cc_ok"] = True
                self.esp["partnum"] = "0x" + m.group(1)[2:].upper()
                self.esp["version"] = "0x" + m.group(2)[2:].upper()
                self.esp["marcstate"] = "0x" + m.group(3)[2:].upper()
                rssi = int(m.group(4))
                gdo0 = int(m.group(5))
                gdo2 = int(m.group(6))
                self.esp["rssi_dbm"] = rssi
                self.esp["gdo0"] = gdo0
                self.esp["gdo2"] = gdo2
                self._record_rssi(rssi, gdo2)
                # Keep register dump out of noisy console unless user asked or first dump
                return

            elif m := re.search(
                r"FREQ=(0x[0-9A-Fa-f]+)\s+MDMCFG4/3/2=([0-9A-Fa-fxX/]+)\s+"
                r"AGCCTRL2/1/0=([0-9A-Fa-fxX/]+)\s+FOCCFG=(0x[0-9A-Fa-f]+)\s+"
                r"FREND1=(0x[0-9A-Fa-f]+)\s+TEST0=(0x[0-9A-Fa-f]+)",
                line,
            ):
                self.esp["regs"] = {
                    "FREQ": m.group(1),
                    "MDMCFG4/3/2": m.group(2),
                    "AGCCTRL2/1/0": m.group(3),
                    "FOCCFG": m.group(4),
                    "FREND1": m.group(5),
                    "TEST0": m.group(6),
                }
                return

            elif m := re.search(
                r"\[(\d+)\s+s\]\s+bursts\s+(\d+)\s+frames\s+(\d+),\s+edges\s+(\d+)\s+\(noise\),\s+"
                r"dropped\s+(\d+),\s+RSSI(?:\s+now)?\s+(-?\d+)\s+dBm(?:,\s+GDO2=(\d))?",
                line,
            ):
                self.esp["uptime_s"] = int(m.group(1))
                self.esp["bursts"] = int(m.group(2))
                self.esp["frames"] = int(m.group(3))
                self.esp["edges"] = int(m.group(4))
                self.esp["dropped"] = int(m.group(5))
                rssi = int(m.group(6))
                gdo2 = int(m.group(7)) if m.group(7) is not None else self.esp.get("gdo2")
                self.esp["rssi_dbm"] = rssi
                if gdo2 is not None:
                    self.esp["gdo2"] = gdo2
                if sq := re.search(r"squelch=(on|off)", line):   # firmware with the 'g' toggle appends this
                    self.esp["squelch"] = sq.group(1)
                kind = "stat"

            elif m := re.search(
                r"([\d.]+)\s+s\s+EG53MA4\s+id\s+([0-9A-Fa-f]+)\s+([\d.]+)\s+kPa\s+=\s+([\d.]+)\s+psi\s+"
                r"(-?\d+)\s+F\s+\(\s*(-?\d+)\s+C\)\s+flags\s+([0-9A-Fa-f]+)\s+rssi\s+(-?\d+)\s+dBm",
                line,
            ):
                rx = {
                    "rx_id": self._next_rx_id,
                    "t": time.time(),
                    "ts": now_hms(),
                    "esp_s": float(m.group(1)),
                    "id": m.group(2).upper(),
                    "kpa": float(m.group(3)),
                    "psi": float(m.group(4)),
                    "temp_f": int(m.group(5)),
                    "temp_c": int(m.group(6)),
                    "flags": m.group(7).upper(),
                    "rssi": int(m.group(8)),
                }
                self._next_rx_id += 1
                self._correlate_rx(rx)
                self.rx_frames.appendleft(rx)
                self.esp["frames"] += 1
                kind = "rx"

            elif "raw dump on" in line:
                self.esp["raw_dump"] = True
                kind = "cc"
            elif "raw dump off" in line:
                self.esp["raw_dump"] = False
                kind = "cc"
            elif m := re.match(r"squelch (on|off)\b", line):
                self.esp["squelch"] = m.group(1)
                kind = "cc"
            elif re.search(r"pulses=\d+|^\s*(MAN|DMAN|chips|raw)\b", line):
                self.rx_other.appendleft({"ts": now_hms(), "line": line.strip()})
                kind = "other"

            self._append_serial(line, kind)

    def start_tx(self, params: dict) -> dict:
        if not SIM_SCRIPT.exists():
            return {"ok": False, "error": f"Missing {SIM_SCRIPT}"}

        mode = params.get("mode", "eg53ma4")
        if mode not in ("eg53ma4", "cw"):
            return {"ok": False, "error": f"Invalid mode: {mode}"}

        try:
            gain = float(params.get("gain", 25.0))
            gain = max(0.0, min(55.0, gain))
            count = max(1, min(10, int(params.get("count", 3))))
            repeats = max(1, min(4, int(params.get("repeats", 2))))
            interval = max(0.1, min(5.0, float(params.get("interval", 0.6))))
            sensor_id = int(str(params.get("id", "0x123456")), 0) & 0xFFFFFF
            psi = max(0.0, min(90.0, float(params.get("psi", 31.9))))
            temp_f = max(0, min(200, int(params.get("temp_f", 77))))
            flags = int(str(params.get("flags", "0x058F2001")), 0) & 0xFFFFFFFF
            cw_ms = max(50, min(2000, int(params.get("cw_ms", 400))))
        except Exception as exc:
            return {"ok": False, "error": f"Invalid TX parameter: {exc}"}

        with self._lock:
            if self.usrp["tx_busy"]:
                return {"ok": False, "error": "USRP TX already in progress"}
            payload = build_eg53ma4_payload(sensor_id, psi, temp_f, flags)
            tx_id = self._next_tx_id
            self._next_tx_id += 1
            tx_rec = {
                "id": tx_id,
                "t": time.time(),
                "ts": now_hms(),
                "mode": mode,
                "freq_mhz": 315.0,
                "gain_db": gain,
                "sensor_id": f"{sensor_id:06X}",
                "psi": round(psi, 1),
                "kpa": round(payload[7] * 2.5, 1),
                "temp_f": temp_f,
                "flags": f"{flags:08X}",
                "payload_hex": payload.hex().upper(),
                "repeats": repeats if mode == "eg53ma4" else 1,
                "count": count,
                "expected_frames": count * repeats if mode == "eg53ma4" else 0,
                "rx_matched": 0,
                "status": "transmitting",
                "error": "",
            }
            self.tx_log.appendleft(tx_rec)
            self.usrp["tx_busy"] = True
            self._tx_active = True

        cmd = [
            "python3", "-s", str(SIM_SCRIPT),
            "--mode", mode,
            "--gain", str(gain),
            "--count", str(count),
            "--interval", str(interval),
        ]
        if mode == "eg53ma4":
            cmd += [
                "--id", f"0x{sensor_id:06X}",
                "--psi", str(psi),
                "--temp-f", str(temp_f),
                "--flags", f"0x{flags:08X}",
                "--repeats", str(repeats),
            ]
        else:
            cmd += ["--cw-ms", str(cw_ms)]

        def worker():
            try:
                res = subprocess.run(cmd, capture_output=True, text=True, timeout=30.0)
                ok = res.returncode == 0
                err = "" if ok else ((res.stderr or res.stdout or "TX failed").strip().splitlines()[-1])
                with self._lock:
                    tx_rec["status"] = "sent" if ok else "error"
                    tx_rec["error"] = err
                    if ok:
                        self.usrp["detected"] = True
                        self.usrp["error"] = ""
                    elif "No devices found" in (res.stderr or "") or "LookupError" in (res.stderr or ""):
                        self.usrp["detected"] = False
                        self.usrp["error"] = err
                    self._append_serial(
                        f"[TX #{tx_id}] {mode.upper()} gain={gain:.0f}dB "
                        + (f"id={sensor_id:06X} psi={psi:.1f} -> {tx_rec['status']}" if mode == "eg53ma4" else f"cw={cw_ms}ms -> {tx_rec['status']}"),
                        "tx" if ok else "err",
                    )
            except Exception as exc:
                with self._lock:
                    tx_rec["status"] = "error"
                    tx_rec["error"] = str(exc)
            finally:
                with self._lock:
                    self._tx_active = False
                    self.usrp["tx_busy"] = False

        self._tx_thread = threading.Thread(target=worker, daemon=True)
        self._tx_thread.start()
        return {"ok": True, "tx": tx_rec}

    def clear_logs(self) -> dict:
        with self._lock:
            self.tx_log.clear()
            self.rx_frames.clear()
            self.rx_other.clear()
            self.serial_log.clear()
            self.rssi_history.clear()
        return {"ok": True}

    def get_state(self) -> dict:
        ports = list_serial_ports()
        with self._lock:
            tx_expected = sum(t["expected_frames"] for t in self.tx_log if t["mode"] == "eg53ma4" and t["status"] != "error")
            tx_matched = sum(t["rx_matched"] for t in self.tx_log if t["mode"] == "eg53ma4")
            return {
                "ports": ports,
                "esp": {**self.esp, "regs": dict(self.esp["regs"])},
                "usrp": dict(self.usrp),
                "summary": {
                    "tx_bursts": len(self.tx_log),
                    "tx_expected_frames": tx_expected,
                    "tx_matched_frames": tx_matched,
                    "rx_total_frames": len(self.rx_frames),
                    "match_pct": round(100.0 * tx_matched / tx_expected, 1) if tx_expected else None,
                },
                "rssi_history": list(self.rssi_history),
                "tx_log": list(self.tx_log),
                "rx_frames": list(self.rx_frames),
                "rx_other": list(self.rx_other),
                "serial_log": list(self.serial_log),
            }

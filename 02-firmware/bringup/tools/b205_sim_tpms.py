#!/usr/bin/python3 -s
"""USRP B205mini 315 MHz simulated ASK/OOK TPMS transmitter for bench testing.

Generates exact GM/Schrader EG53MA4 frames (matching 02-firmware/bringup/src/eg53ma4.cpp)
or pulsed CW carriers for CC1101 RSSI / GDO2 carrier-sense verification.

SAFETY: Never cable the B205mini TX output directly into the E07-M1101D RX input
without at least 40-50 dB of inline RF attenuation. Use low-gain over-the-air
bench transmission with antennas separated on the desk.
"""

import argparse
import sys
import time
import numpy as np

CHIP_US = 123
SAMPLE_RATE = 1_000_000.0  # 1 MS/s -> 1 sample = 1 us


def build_eg53ma4_payload(sensor_id: int, psi: float, temp_f: int, flags: int) -> bytes:
    """Build 10-byte EG53MA4 payload with 8-bit modular checksum."""
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


def encode_eg53ma4_chips(payload: bytes) -> list[int]:
    """Encode 40-bit zero preamble + 80-bit payload using Manchester (0->[0,1], 1->[1,0])."""
    if len(payload) != 10:
        raise ValueError("EG53MA4 payload must be 10 bytes")
    bits = [0] * 40
    for byte in payload:
        for shift in range(7, -1, -1):
            bits.append((byte >> shift) & 1)
    chips = []
    for bit in bits:
        chips.extend((bit, bit ^ 1))
    # Leading/trailing 0-chips merge into surrounding idle silence
    while chips and chips[0] == 0:
        chips.pop(0)
    while chips and chips[-1] == 0:
        chips.pop()
    return chips


def build_eg53ma4_iq(
    payload: bytes,
    repeats: int = 2,
    gap_us: int = 1000,
    pad_us: int = 5000,
    amp: float = 0.7,
) -> tuple[np.ndarray, list[tuple[int, int]]]:
    """Build complex64 OOK baseband IQ array (1 MS/s) and run-length list (level, us)."""
    chips = encode_eg53ma4_chips(payload)
    msg_runs: list[tuple[int, int]] = []
    i = 0
    while i < len(chips):
        k = i
        while k < len(chips) and chips[k] == chips[i]:
            k += 1
        msg_runs.append((chips[i], (k - i) * CHIP_US))
        i = k

    runs: list[tuple[int, int]] = [(0, pad_us)]
    for m in range(repeats):
        if m > 0:
            runs.append((0, gap_us))
        runs.extend(msg_runs)
    runs.append((0, pad_us))

    total_samples = sum(us for _, us in runs)
    env = np.zeros(total_samples, dtype=np.float32)
    idx = 0
    for level, us in runs:
        if level:
            env[idx : idx + us] = amp
        idx += us
    iq = env.astype(np.complex64)
    return iq, runs


def build_cw_iq(on_ms: int = 200, off_ms: int = 200, amp: float = 0.5) -> np.ndarray:
    """Build pulsed CW complex64 IQ array (1 MS/s)."""
    on_n = int(on_ms * 1000)
    off_n = int(off_ms * 1000)
    env = np.concatenate([
        np.zeros(20_000, dtype=np.float32),
        np.full(on_n, amp, dtype=np.float32),
        np.zeros(off_n, dtype=np.float32),
    ])
    return env.astype(np.complex64)


def run_self_test() -> int:
    """Offline verification of generated EG53MA4 packet and OOK baseband timing."""
    payload = build_eg53ma4_payload(0x123456, 31.9, 77, 0x058F2001)
    assert len(payload) == 10
    assert payload[4:7] == b"\x12\x34\x56"
    assert payload[7] == 88, f"expected 88 (220.0 kPa), got {payload[7]}"
    assert payload[8] == 77
    assert (sum(payload[:9]) & 0xFF) == payload[9]

    iq, runs = build_eg53ma4_iq(payload, repeats=2, gap_us=1000, pad_us=5000, amp=0.7)
    assert iq.dtype == np.complex64
    # First and last runs are 5000 us silence; active pulses must be multiples of 123 us (123 or 246 us)
    active_runs = [r for r in runs[1:-1] if r[1] != 1000]
    assert active_runs[0][0] == 1 and active_runs[-1][0] == 1
    for lvl, us in active_runs:
        assert lvl in (0, 1)
        assert us in (CHIP_US, 2 * CHIP_US), f"unexpected pulse duration {us} us"

    # Re-slice envelope from IQ samples and verify every bit against payload
    on = np.abs(iq) > 0.35
    edges = np.flatnonzero(on[1:] != on[:-1]) + 1
    bounds = np.concatenate(([0], edges, [len(on)]))
    pulses = [(int(on[s]), int(e - s)) for s, e in zip(bounds[:-1], bounds[1:])]
    # Drop leading/trailing 5000 us quiet pads
    assert pulses[0] == (0, 5000) and pulses[-1] == (0, 5000)
    inner = pulses[1:-1]

    # Split on 1000 us gap and decode Manchester zero-bit exactly like eg53ma4.cpp
    msgs = []
    cur = []
    for lvl, us in inner:
        if lvl == 0 and us > 300:
            if cur:
                msgs.append(cur)
                cur = []
        else:
            cur.append((lvl, us))
    if cur:
        msgs.append(cur)
    assert len(msgs) == 2, f"expected 2 repeated messages, got {len(msgs)}"

    for msg in msgs:
        bits = [0]
        since = 0
        for i in range(0, len(msg), 2):
            pulse = msg[i][1]
            gap = msg[i + 1][1] if i + 1 < len(msg) else 0
            if 2 * (pulse + since) > 3 * CHIP_US:
                bits.append(1)
                since = 0
            else:
                since += pulse
            if i + 1 < len(msg):
                if 2 * (gap + since) > 3 * CHIP_US:
                    bits.append(0)
                    since = 0
                else:
                    since += gap
        assert len(bits) == 120, f"expected 120 bits, got {len(bits)}"
        assert all(b == 0 for b in bits[:40]), "preamble not all zeros"
        dec = bytearray(10)
        for idx, b in enumerate(bits[40:]):
            if b:
                dec[idx // 8] |= 0x80 >> (idx % 8)
        assert bytes(dec) == payload, f"decoded {dec.hex()} != {payload.hex()}"

    print(f"b205_sim_tpms self-test OK: {len(iq)} samples, 2x120-bit EG53MA4 payload={payload.hex().upper()}")
    return 0


def transmit(args: argparse.Namespace) -> int:
    if args.gain > 60.0 and not args.allow_high_gain:
        print("ERROR: --gain > 60 dB blocked for RX safety (pass --allow-high-gain to override).", file=sys.stderr)
        return 2

    import uhd

    print("WARNING: Keep TX over-the-air or use >=40-50 dB inline attenuation before E07-M1101D RX.")
    usrp = uhd.usrp.MultiUSRP(args.args)
    usrp.set_tx_rate(SAMPLE_RATE, 0)
    tune_req = uhd.types.TuneRequest(args.freq, args.lo_offset)
    tune_res = usrp.set_tx_freq(tune_req, 0)
    usrp.set_tx_gain(args.gain, 0)
    if args.antenna:
        usrp.set_tx_antenna(args.antenna, 0)

    print(
        f"USRP TX ready: actual_rf={usrp.get_tx_freq(0)/1e6:.6f} MHz, "
        f"rate={usrp.get_tx_rate(0)/1e6:.3f} MS/s, gain={usrp.get_tx_gain(0):.1f} dB, "
        f"lo_offset={args.lo_offset/1e3:.1f} kHz ({tune_res.actual_dsp_freq/1e3:.1f} kHz DSP)"
    )

    st_args = uhd.usrp.StreamArgs("fc32", "sc16")
    tx_stream = usrp.get_tx_stream(st_args)

    if args.mode == "cw":
        buf = build_cw_iq(on_ms=args.cw_ms, off_ms=200, amp=args.amp)
        print(f"Transmitting {args.count} CW pulses ({args.cw_ms} ms ON) at {args.freq/1e6:.3f} MHz...")
    else:
        payload = build_eg53ma4_payload(args.id, args.psi, args.temp_f, args.flags)
        buf, _ = build_eg53ma4_iq(payload, repeats=args.repeats, amp=args.amp)
        print(
            f"Transmitting {args.count} EG53MA4 bursts: id={args.id:06X} "
            f"psi={args.psi:.1f} temp={args.temp_f}F payload={payload.hex().upper()}"
        )

    max_samps = tx_stream.get_max_num_samps()
    for n in range(args.count):
        md = uhd.types.TXMetadata()
        md.start_of_burst = True
        md.end_of_burst = False
        sent = 0
        total = len(buf)
        while sent < total:
            chunk = buf[sent : sent + max_samps]
            if sent + len(chunk) >= total:
                md.end_of_burst = True
            tx_stream.send(chunk, md)
            md.start_of_burst = False
            sent += len(chunk)
        # Wait for burst to finish + interval before next burst
        time.sleep(len(buf) / SAMPLE_RATE + args.interval)
        print(f"  burst {n + 1}/{args.count} sent")

    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="USRP B205mini 315 MHz simulated TPMS ASK/OOK transmitter")
    p.add_argument("--mode", choices=("eg53ma4", "cw"), default="eg53ma4")
    p.add_argument("--args", default="type=b200", help="UHD device args")
    p.add_argument("--freq", type=float, default=315.0e6, help="Center frequency in Hz")
    p.add_argument("--lo-offset", type=float, default=250e3, help="TX LO offset in Hz (keeps LO leakage out of 203 kHz RX BW)")
    p.add_argument("--gain", type=float, default=25.0, help="TX gain in dB (0..89.75; default 25 dB for safe OTA bench)")
    p.add_argument("--allow-high-gain", action="store_true", help="Allow TX gain > 60 dB")
    p.add_argument("--amp", type=float, default=0.7, help="Baseband amplitude (0..1)")
    p.add_argument("--antenna", default="TX/RX", help="USRP TX antenna port")
    p.add_argument("--count", type=int, default=5, help="Number of bursts to transmit")
    p.add_argument("--interval", type=float, default=0.8, help="Gap between bursts in seconds")
    p.add_argument("--repeats", type=int, default=2, help="EG53MA4 message repeats per burst")
    p.add_argument("--id", type=lambda s: int(s, 0), default=0x123456, help="24-bit sensor ID")
    p.add_argument("--psi", type=float, default=31.9, help="Simulated pressure in psi")
    p.add_argument("--temp-f", type=int, default=77, help="Simulated temperature in F")
    p.add_argument("--flags", type=lambda s: int(s, 0), default=0x058F2001, help="32-bit flags")
    p.add_argument("--cw-ms", type=int, default=250, help="CW pulse duration in ms")
    p.add_argument("--self-test", action="store_true", help="Run offline waveform self-test without USRP")
    args = p.parse_args()

    if args.self_test:
        return run_self_test()
    return transmit(args)


if __name__ == "__main__":
    raise SystemExit(main())

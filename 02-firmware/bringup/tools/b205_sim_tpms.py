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
SAMPLE_RATE = 500_000.0  # 500 kS/s (2 us/sample): clean USB 2.0/3.0 streaming with zero underflows


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

    total_us = sum(us for _, us in runs)
    total_samples = int(round(total_us * SAMPLE_RATE / 1e6))
    env = np.zeros(total_samples, dtype=np.float32)
    t_us = 0
    for level, us in runs:
        s0 = int(round(t_us * SAMPLE_RATE / 1e6))
        t_us += us
        s1 = int(round(t_us * SAMPLE_RATE / 1e6))
        if level and s1 > s0:
            env[s0:s1] = amp
    iq = np.ascontiguousarray(env, dtype=np.complex64)
    return iq, runs


def build_cw_iq(on_ms: int = 200, off_ms: int = 200, amp: float = 0.5) -> np.ndarray:
    """Build pulsed CW complex64 IQ array."""
    pad_n = int(round(0.020 * SAMPLE_RATE))
    on_n = int(round((on_ms / 1000.0) * SAMPLE_RATE))
    off_n = int(round((off_ms / 1000.0) * SAMPLE_RATE))
    env = np.concatenate([
        np.zeros(pad_n, dtype=np.float32),
        np.full(on_n, amp, dtype=np.float32),
        np.zeros(off_n, dtype=np.float32),
    ])
    return np.ascontiguousarray(env, dtype=np.complex64)


def run_self_test() -> int:
    """Offline verification of all presets and OOK baseband timing."""
    presets = [
        (0x123456, 31.9, 77, 0x058F2001, 88),
        (0xABCDEF, 35.0, 68, 0x058F2002, 97),
        (0x2FC871, 33.0, 72, 0x058F2001, 91),
        (0x3495AC, 24.0, 80, 0x058F2001, 66),
    ]
    for sid, psi, temp_f, flags, exp_p in presets:
        payload = build_eg53ma4_payload(sid, psi, temp_f, flags)
        assert len(payload) == 10
        assert payload[7] == exp_p, f"expected {exp_p}, got {payload[7]}"
        assert (sum(payload[:9]) & 0xFF) == payload[9]

        iq, runs = build_eg53ma4_iq(payload, repeats=2, gap_us=1000, pad_us=5000, amp=0.7)
        assert iq.dtype == np.complex64 and iq.flags["C_CONTIGUOUS"]
        active_runs = [r for r in runs[1:-1] if r[1] != 1000]
        assert active_runs[0][0] == 1 and active_runs[-1][0] == 1
        for lvl, us in active_runs:
            assert lvl in (0, 1)
            assert us in (CHIP_US, 2 * CHIP_US), f"unexpected pulse duration {us} us"

        # Re-slice envelope from IQ samples and verify every bit against payload
        on = np.abs(iq) > 0.35
        edges = np.flatnonzero(on[1:] != on[:-1]) + 1
        bounds = np.concatenate(([0], edges, [len(on)]))
        pulses = [(int(on[s]), int(round((e - s) * 1e6 / SAMPLE_RATE))) for s, e in zip(bounds[:-1], bounds[1:])]
        assert pulses[0] == (0, 5000) and pulses[-1] == (0, 5000)
        inner = pulses[1:-1]

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

    print(f"b205_sim_tpms self-test OK: 4 presets verified @ {SAMPLE_RATE/1e3:.0f} kS/s")
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
    underflows = 0
    for n in range(args.count):
        md = uhd.types.TXMetadata()
        md.start_of_burst = True
        md.end_of_burst = False
        md.has_time_spec = True
        md.time_spec = usrp.get_time_now() + uhd.types.TimeSpec(0.05)
        sent = 0
        total = len(buf)
        while sent < total:
            chunk = buf[sent : sent + max_samps]
            if sent + len(chunk) >= total:
                md.end_of_burst = True
            n_sent = tx_stream.send(chunk, md, 5.0)
            if n_sent <= 0:
                raise RuntimeError(f"UHD TX send returned {n_sent} at sample {sent}/{total}")
            sent += n_sent
            md.start_of_burst = False
            md.has_time_spec = False

        # Wait for scheduled burst ACK / check for underflow or late packet
        async_md = uhd.types.TXAsyncMetadata()
        deadline = time.time() + (len(buf) / SAMPLE_RATE) + 0.5
        while time.time() < deadline:
            if not tx_stream.recv_async_msg(async_md, 0.05):
                continue
            code = async_md.event_code
            if code == uhd.types.TXMetadataEventCode.underflow:
                underflows += 1
                print(f"  WARNING: burst {n + 1} UHD underflow", file=sys.stderr)
            elif code == uhd.types.TXMetadataEventCode.time_error:
                print(f"  WARNING: burst {n + 1} UHD time_error", file=sys.stderr)
            elif code == uhd.types.TXMetadataEventCode.burst_ack:
                break

        time.sleep(args.interval)
        print(f"  burst {n + 1}/{args.count} sent ({total} samples)")

    if underflows:
        print(f"WARNING: {underflows} TX underflow(s) detected", file=sys.stderr)
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="USRP B205mini 315 MHz simulated TPMS ASK/OOK transmitter")
    p.add_argument("--mode", choices=("eg53ma4", "cw"), default="eg53ma4")
    p.add_argument("--args", default="type=b200", help="UHD device args")
    p.add_argument("--freq", type=float, default=315.0e6, help="Center frequency in Hz")
    p.add_argument("--lo-offset", type=float, default=150e3, help="TX LO offset in Hz (keeps LO leakage out of 203 kHz RX BW)")
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

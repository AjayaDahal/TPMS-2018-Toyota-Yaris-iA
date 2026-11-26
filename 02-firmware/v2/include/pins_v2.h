#pragma once
// ESP32 pin map of the v2 carrier board (100 x 100 mm, 6-layer), rev A.
//
// This file is the single source of truth: the firmware includes it and 01-hardware/v2/check_pinmap.py audits it
// (strapping pins, input-only pins, boot-time glitches, ADC1 use, duplicates, and the pins shared with the v1 panel).
//
// Tags in the trailing comment, read by the audit script: [dir,flag,...]
//   dir:  in | out | analog | io | usb | nc
//   v1        same pin and function as the v1 panel (02-firmware/bringup/include/pins.h)
//   poll      polled, never used as an interrupt (ESP32 errata 3.11: GPIO36/39 glitch low for ~80 ns)
//   power     controls a power rail; must not glitch at boot
//   bootlow   the net is low or floating at reset (required on strapping pin GPIO2)
//   pullup / pulldown   external resistor fitted on the board
//
// Board-side notes (carrier rev A, 01-hardware/v2/carrier):
//   - The Pi's 5 V regulator (on-board TPS54560B buck, 5.17 V) is ON by default whenever ACC is present: its EN
//     divider (1 M / 150 k: starts at 8.0 V) has 10 uF on it, a 1.2-1.4 s start delay. The ESP32 can only delay it
//     via PIN_PI_INHIBIT (a 2N7002 pulling EN low), and at start-up it reads PIN_PI_PGOOD first: a rail that is
//     already up means a running Pi, which is left on (PiPowerSequencer, railUp). So an ESP32 crash, reset or
//     firmware update never cuts power to the Pi.
//   - Every GPIO reaches its circuit through one series resistor next to the DevKit socket (a cut point for
//     rework). check_pinmap.py checks the carrier netlist against this file.
//   - All GPIOs of the 30-pin DevKit are assigned. GPIO12 must stay unconnected (flash-voltage strapping pin).

// Shared VSPI bus: CC1101 (same pins as v1)
constexpr int PIN_SPI_SCK = 18;     // [out,v1]
constexpr int PIN_SPI_MISO = 19;    // [in,v1]
constexpr int PIN_SPI_MOSI = 23;    // [out,v1]

// CC1101 315 MHz receiver (same pins as v1)
constexpr int PIN_CC_CS = 5;        // [out,v1]  strapping pin, idles high: fine
constexpr int PIN_CC_GDO0 = 34;     // [in,v1]   OOK data, asynchronous serial mode
constexpr int PIN_CC_GDO2 = 35;     // [in,v1]   carrier sense

// I2C (same pins as v1, 4.7 k pull-ups): TMP75 board temperature (LM75 compatible, 0x48), TCA9534 I/O expander
// (0x20: P0 AUX input, P1 fan, P2 Pi spare line), INA226 monitors 0x40 (12 V in) and 0x41 (5V_PI), optional VL6180X
constexpr int PIN_I2C_SDA = 21;     // [io,v1]
constexpr int PIN_I2C_SCL = 22;     // [io,v1]

// Alerts
constexpr int PIN_BUZZER = 13;      // [out,v1,pulldown]  12 V active piezo inside the dash unit (behind the bezel's right
                                    //                    slots), low-side MOSFET, active high; the beeps mute themselves
constexpr int PIN_LED_L = 25;       // [out,pulldown]     left amber BSM LED, PWM through a low-side MOSFET
constexpr int PIN_LED_R = 14;       // [out,pulldown]     right amber BSM LED; GPIO14's boot-time PWM only flickers it
constexpr int PIN_STATUS_LED = 2;   // [out,bootlow]      DevKit blue LED; its resistor holds GPIO2 low at reset

// Inputs
constexpr int PIN_BTN = 4;          // [in,v1,pullup]     optional mute / acknowledge button, active low (v1 RC). v2 fits
                                    //                    none: the beeps mute themselves, the touch screen mutes
constexpr int PIN_BLINK_L = 36;     // [in,poll,pullup]   LTV-357T opto output, active low (left lamp lit = low)
constexpr int PIN_BLINK_R = 39;     // [in,poll,pullup]   LTV-357T opto output, active low (right lamp lit = low)
constexpr int PIN_ACC_SENSE = 32;   // [analog]           ADC1_CH4: 100 k / 10 k divider from 12V_PROT, clamped

// u-blox NEO-M8N GPS, UART1 remapped: the speed gate's fallback (the OBD-II dongle's speed comes over Bluetooth,
// no pins)
constexpr int PIN_GPS_RX = 33;      // [in]   <- GPS TX (NMEA, 9600 Bd)
constexpr int PIN_GPS_TX = 27;      // [out]  -> GPS RX (configuration only)

// Raspberry Pi link and power, UART2
constexpr int PIN_PI_UART_RX = 16;  // [in]   <- Pi GPIO14 TXD through 1 k
constexpr int PIN_PI_UART_TX = 17;  // [out]  -> Pi GPIO15 RXD through 4.7 k; keep disabled while the Pi is off
constexpr int PIN_PI_INHIBIT = 26;  // [out,power,pulldown]  high = hold the Pi 5 V regulator off
constexpr int PIN_PI_PGOOD = 15;    // [in,pulldown]  5V_PI rail sense, 22 k / 33 k divider: 3.1 V when the rail is up.
                                    //   Strapping pin: low at boot (rail off) only mutes the ROM log

// Fixed by the DevKit
constexpr int PIN_USB_TX = 1;       // [usb]  UART0 to the DevKit's USB bridge (log, flashing)
constexpr int PIN_USB_RX = 3;       // [usb]
constexpr int PIN_UNUSED_GPIO12 = 12;  // [nc]  flash-voltage strapping pin: keep unconnected

#pragma once
// Pin map of the TPMS panel PCB. Must match hardware/scripts/design.py (the ESP32 pin nets).

// Shared VSPI bus: CC1101 + OLED (the OLED is write-only)
constexpr int PIN_SPI_SCK = 18;
constexpr int PIN_SPI_MISO = 19;
constexpr int PIN_SPI_MOSI = 23;

// CC1101 module (U1 / J2)
constexpr int PIN_CC_CS = 5;
constexpr int PIN_CC_GDO0 = 34;   // input-only: demodulated data in asynchronous serial mode
constexpr int PIN_CC_GDO2 = 35;   // input-only: carrier sense

// NHD-2.7-12864WDW3 OLED (SSD1322, 4-wire SPI)
constexpr int PIN_OLED_CS = 15;
constexpr int PIN_OLED_DC = 27;
constexpr int PIN_OLED_RES = 26;

// Tyre LEDs, active high through 220 ohm
constexpr int PIN_LED_FL = 25;
constexpr int PIN_LED_FR = 33;
constexpr int PIN_LED_RL = 32;
constexpr int PIN_LED_RR = 14;

// EC11 encoder: 10 k pull-ups + RC filters on the board, active low
constexpr int PIN_ENC_A = 16;
constexpr int PIN_ENC_B = 17;
constexpr int PIN_ENC_SW = 4;

constexpr int PIN_BUZZER = 13;     // active high, MMBT3904 low-side switch, 5 V active buzzer
constexpr int PIN_MX05_DATA = 36;  // input-only: optional MX-05V through R9/R10 (floats if not fitted)

constexpr int PIN_I2C_SDA = 21;    // J4 expansion
constexpr int PIN_I2C_SCL = 22;

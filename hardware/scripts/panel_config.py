"""Panel geometry and component placement for the TPMS monitor PCB.

All values are in millimetres. Coordinate system: x to the right, y downwards, origin at the
top-centre of the panel, looking at the FRONT (display side) of the board.

The outline and front-panel feature positions were scaled from Figure 3.6 of the project report,
using the NHD-2.7-12864WDW3 display module (82.0 x 47.5 mm) as the size reference. Replace them
with measured dimensions when available and re-run build_tpms_panel.py.
"""

# Set to True only after the real panel dimensions (outline, notch, USB holes, mounting holes) have been
# entered below. While False, the build prints a reminder and names the Gerber zip "..._DRAFT_...".
DIMENSIONS_CONFIRMED = False

# ---------------------------------------------------------------- outline (trapezoid)
TOP_WIDTH = 191.0
BOTTOM_WIDTH = 123.0
HEIGHT = 129.0
NOTCH_Y = 34.0          # semicircular notch on the right edge: centre distance from top edge
NOTCH_R = 4.0
CORNER_RADIUS = 0.0     # 0 = sharp corners (as in the report render)

# ---------------------------------------------------------------- front-panel features
DISPLAY_CENTER = (0.0, 35.25)                 # NHD-2.7-12864WDW3 module centre
# Tyre LEDs: 2x2 "car" layout centred under the display (FL FR / RL RR)
LED_POSITIONS = ((-8.5, 66.0), (8.5, 66.0), (-8.5, 86.0), (8.5, 86.0))
LED_LABELS = ("FL", "FR", "RL", "RR")
CAR_OUTLINE = True                            # silkscreen car silhouette between the LEDs

# User input on the right of the display:
#   "encoder" - one EC11 rotary encoder with push switch: rotate = up/down, push = OK,
#               BACK is a menu entry on the display (and/or long-press)
#   "buttons" - 4 tactile buttons UP / OK / DOWN / BACK in a column (the report's original layout)
INPUT_STYLE = "encoder"
ENCODER_CENTER = (57.0, 42.0)                 # encoder courtyard centre (shaft is 0.25 mm to the right)
KNOB_DIAMETER = 24.0                          # only used for the 3D render
BUTTON_X = 50.0                               # right-hand button column
BUTTON_YS = (24.5, 40.0, 55.5, 71.0)
BUTTON_LABELS = ("UP", "OK", "DOWN", "BACK")
USB_HOLE_CENTERS = ((-40.4, 103.0), (40.4, 103.0))
USB_HOLE_DIAMETER = 22.0                      # cut-out for panel-mount USB sockets (measure yours!)
USB_NUT_DIAMETER = 29.0                       # front copper keep-out under the nut
USB_BACK_KEEPOUT_DIAMETER = 26.0              # back-side keep-out around connector body
MOUNT_HOLES = ((-88.0, 5.5), (88.0, 5.5), (-57.0, 123.0), (57.0, 123.0))
MOUNT_HOLE_DIAMETER = 3.2                     # M3

# Where the panel origin sits on the KiCad page (A4 landscape)
PAGE_ORIGIN = (150.0, 35.0)

# ---------------------------------------------------------------- ESP32 dev board
# DOIT ESP32 DEVKIT V1 (30-pin). Both 0.9" (22.86 mm) and 1.0" (25.4 mm) row-spacing variants
# exist; the footprint provides both GPIO23..3V3 rows so either board fits.
ESP32_ROW_SPACINGS = (22.86, 25.4)

# ---------------------------------------------------------------- component placement
# ref: (side, x, y, rotation)
#   side      'F' = front (display side), 'B' = back
#   x, y      centre of the footprint courtyard in panel coordinates
#   rotation  degrees counter-clockwise, applied after mirroring for back-side parts
PLACEMENT = {
    # front panel
    "U2": ("F", DISPLAY_CENTER[0], DISPLAY_CENTER[1], 0),
    "D1": ("F", LED_POSITIONS[0][0], LED_POSITIONS[0][1], 0),
    "D2": ("F", LED_POSITIONS[1][0], LED_POSITIONS[1][1], 0),
    "D3": ("F", LED_POSITIONS[2][0], LED_POSITIONS[2][1], 0),
    "D4": ("F", LED_POSITIONS[3][0], LED_POSITIONS[3][1], 0),
    "H1": ("F", MOUNT_HOLES[0][0], MOUNT_HOLES[0][1], 0),
    "H2": ("F", MOUNT_HOLES[1][0], MOUNT_HOLES[1][1], 0),
    "H3": ("F", MOUNT_HOLES[2][0], MOUNT_HOLES[2][1], 0),
    "H4": ("F", MOUNT_HOLES[3][0], MOUNT_HOLES[3][1], 0),
    "H5": ("F", USB_HOLE_CENTERS[0][0], USB_HOLE_CENTERS[0][1], 0),
    "H6": ("F", USB_HOLE_CENTERS[1][0], USB_HOLE_CENTERS[1][1], 0),
    # back: MCU (antenna to the right, USB to the left, IO23..3V3 row on top)
    "A1": ("B", 0.0, 37.0, 270),
    # back: display support
    "JP1": ("B", 19.05, 9.5, 0),
    "C8": ("B", 24.5, 9.5, 90),
    "C9": ("B", 28.5, 9.5, 90),
    # back: LED resistors, next to the 2x2 LED group
    "R1": ("B", LED_POSITIONS[0][0] - 8.5, LED_POSITIONS[0][1], 0),
    "R2": ("B", LED_POSITIONS[1][0] + 8.5, LED_POSITIONS[1][1], 0),
    "R3": ("B", LED_POSITIONS[2][0] - 8.5, LED_POSITIONS[2][1], 0),
    "R4": ("B", LED_POSITIONS[3][0] + 8.5, LED_POSITIONS[3][1], 0),
    # back: CC1101 radio on the left, SMA pointing DOWN (rot 0). In the car the top edge sits right under the
    # HVAC controls, so nothing can leave through it; the SMA end (y ~85) leaves room for a 90 deg adapter or
    # extension cable that goes straight back into the console pocket. Decoupling between radio and J4.
    "U1": ("B", -64.0, 59.25, 0),
    "C6": ("B", -54.0, 46.6, 90),
    "C7": ("B", -54.0, 51.4, 90),
    # back: alternative CC1101 header, top-left (optional, DNP)
    "J2": ("B", -70.0, 31.0, 90),
    # back: optional MX-05V superregenerative receiver socket + level divider, top-right
    "J3": ("B", 58.0, 14.0, 90),
    "R9": ("B", 58.0, 23.0, 0),
    "R10": ("B", 58.0, 26.5, 0),
    # back: expansion header (vertical) right of the radio, where the console pocket is deep; I2C pull-ups
    "J4": ("B", -50.0, 55.0, 0),
    "R13": ("B", -42.0, 81.0, 0),
    "R14": ("B", -42.0, 84.5, 0),
    # back: buzzer driver, top-left (only ~10 mm tall)
    "BZ1": ("B", -70.0, 16.5, 0),
    "R11": ("B", -56.0, 11.0, 0),
    "Q1": ("B", -56.0, 16.5, 0),
    "R12": ("B", -56.0, 22.0, 0),
    "D7": ("B", -56.0, 26.5, 0),
    # back: power input 12 V -> 5 V -> 3.3 V (screw terminal wire entry faces the bottom edge)
    "J1": ("B", -12.0, 122.6, 0),
    "F1": ("B", -12.0, 112.0, 0),
    "D6": ("B", -2.0, 112.0, 0),
    "D5": ("B", 8.0, 112.0, 0),
    "C1": ("B", 8.0, 121.5, 0),
    "C2": ("B", 17.0, 121.5, 0),
    "U3": ("B", 17.5, 104.0, 0),
    "C3": ("B", 22.5, 113.5, 0),
    "U4": ("B", -15.0, 100.0, 0),
    "C4": ("B", -5.0, 101.5, 90),
    "C5": ("B", -23.5, 100.0, 90),
}

if INPUT_STYLE == "encoder":
    ex, ey = ENCODER_CENTER
    PLACEMENT.update({
        "SW1": ("F", ex, ey, 0),                     # EC11 encoder: A/C/B pins left, switch pins right
        # back: pull-ups + RC filters (Bourns-recommended 10k / 10k / 10 nF) and switch debounce
        "R5": ("B", ex - 14.0, ey - 5.5, 0),
        "R15": ("B", ex - 14.0, ey - 2.0, 0),
        "R6": ("B", ex - 14.0, ey + 1.5, 0),
        "R16": ("B", ex - 14.0, ey + 5.0, 0),
        "C10": ("B", ex - 19.5, ey - 3.5, 90),
        "C11": ("B", ex - 19.5, ey + 3.5, 90),
        "R7": ("B", ex + 14.0, ey - 2.0, 0),
        "C12": ("B", ex + 14.0, ey + 2.5, 0),
    })
else:
    PLACEMENT.update({f"SW{i + 1}": ("F", BUTTON_X, y, 0) for i, y in enumerate(BUTTON_YS)})
    # back: button pull-ups
    PLACEMENT.update({f"R{i + 5}": ("B", BUTTON_X - 7.4, y, 0) for i, y in enumerate(BUTTON_YS)})

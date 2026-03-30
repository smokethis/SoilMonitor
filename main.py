"""
E-Paper Display Test — Waveshare 2.66" (B) on Raspberry Pi Pico 2 W
=====================================================================
This test script verifies your wiring and driver by drawing a simple
test pattern using all three colors: black, white, and red.

Upload this file along with epaper_2in66b.py to your Pico 2 W.
Run it and you should see the display refresh after ~15 seconds.

Wiring summary (directly from Pico to display header):
    Pico GP10  →  CLK   (SPI clock)
    Pico GP11  →  DIN   (SPI MOSI / data in)
    Pico GP9   →  CS    (chip select)
    Pico GP8   →  DC    (data/command toggle)
    Pico GP12  →  RST   (hardware reset)
    Pico GP13  →  BUSY  (refresh status)
    Pico 3V3   →  VCC   (3.3V power)
    Pico GND   →  GND   (ground)
"""

from machine import Pin, SPI
import time
from epaper_2in66b import EPD_2in66_B

# ──────────────────────────────────────────────
# 1. Set up SPI and create the display driver
# ──────────────────────────────────────────────
# SPI(1) on the Pico 2 W uses GP10 for SCK and GP11 for MOSI by default.
# We run it at 4 MHz — the display controller is comfortable up to ~10 MHz,
# but 4 MHz is a safe starting speed that gives clean signals even on
# breadboard wiring (long jumper wires add capacitance and noise).

spi = SPI(
    1,
    baudrate=4_000_000,
    polarity=0,     # Clock idles LOW (SPI mode 0)
    phase=0,        # Data sampled on rising edge
    sck=Pin(10),
    mosi=Pin(11),
    miso=None       # E-paper is write-only — no data comes back over SPI
)

epd = EPD_2in66_B(
    spi=spi,
    cs_pin=9,
    dc_pin=8,
    rst_pin=12,
    busy_pin=13
)

# ──────────────────────────────────────────────
# 2. Initialize the display
# ──────────────────────────────────────────────
print("Initializing display...")
epd.init()

# ──────────────────────────────────────────────
# 3. Clear to white first
# ──────────────────────────────────────────────
# On a fresh power-up the display may show random noise or its last
# image. A clear cycle ensures a clean starting state.
print("Clearing display to white...")
epd.clear(color_black=0xFF, color_red=0x00)
epd.display(buf_black=None, buf_red=None)
# Note: clear() writes directly to the controller's RAM, then display()
# triggers the refresh. This initial clear takes ~15 seconds.
time.sleep(2)

# ──────────────────────────────────────────────
# 4. Draw a test pattern
# ──────────────────────────────────────────────
print("Drawing test pattern...")

# Start with a white canvas
epd.fill_black(0xFF)  # All white in the B/W buffer
epd.fill_red(0x00)    # No red anywhere

# --- Black border around the entire screen ---
# This verifies that all edges of the display are reachable
# and that the pixel coordinate system is oriented correctly.
epd.rect(0, 0, epd.width, epd.height, color='black')
epd.rect(1, 1, epd.width - 2, epd.height - 2, color='black')

# --- Three color bands ---
# Divide the screen into horizontal thirds to test each color.
# The display is 296 pixels tall, so roughly 99 pixels per band.
band_height = epd.height // 3

# Top third: black filled rectangle (with margin)
epd.fill_rect(10, 10, epd.width - 20, band_height - 15, color='black')

# Middle third: red filled rectangle
epd.fill_rect(10, band_height + 5, epd.width - 20, band_height - 15, color='red')

# Bottom third: checkerboard pattern in black
# This tests individual pixel placement and makes it easy to
# spot any bit-ordering issues in the driver.
checker_y_start = 2 * band_height + 5
checker_size = 8  # 8×8 pixel squares
for row in range(0, band_height - 15, checker_size):
    for col in range(0, epd.width - 20, checker_size):
        # Only fill alternating squares
        if (row // checker_size + col // checker_size) % 2 == 0:
            epd.fill_rect(
                10 + col,
                checker_y_start + row,
                min(checker_size, epd.width - 20 - col),
                min(checker_size, band_height - 15 - row),
                color='black'
            )

# --- Small red squares in the corners ---
# These help verify orientation: if you know which corner has
# the red dot, you can confirm the display isn't rotated or mirrored.
corner_size = 12
epd.fill_rect(4, 4, corner_size, corner_size, color='red')                                         # Top-left
epd.fill_rect(epd.width - corner_size - 4, 4, corner_size, corner_size, color='red')                # Top-right
epd.fill_rect(4, epd.height - corner_size - 4, corner_size, corner_size, color='red')               # Bottom-left
epd.fill_rect(epd.width - corner_size - 4, epd.height - corner_size - 4, corner_size, corner_size, color='red')  # Bottom-right

# ──────────────────────────────────────────────
# 5. Send buffers to the display and refresh
# ──────────────────────────────────────────────
print("Refreshing display (this takes ~15 seconds for tri-color)...")
epd.display(buf_black=epd.buffer_black, buf_red=epd.buffer_red)
print("Done! You should see:")
print("  - A black border around the full screen")
print("  - Top band: solid black")
print("  - Middle band: solid red")
print("  - Bottom band: black & white checkerboard")
print("  - Small red squares in all four corners")

# ──────────────────────────────────────────────
# 6. Put the display to sleep to save power
# ──────────────────────────────────────────────
# The image will persist on screen with zero power draw.
# For your soil sensor project, you'll want to sleep between
# readings to maximize battery life.
print("Putting display to sleep.")
epd.sleep()
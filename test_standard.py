"""
E-Paper Display Test — Rewritten Driver
=========================================
Tests the corrected driver that matches Waveshare's reference
implementation. Should produce a clean image with no shift and
no red artifacts.
"""

from machine import Pin, SPI
import time
from epaper_2in66 import EPD_2in66

spi = SPI(
    1,
    baudrate=4_000_000,
    polarity=0,
    phase=0,
    sck=Pin(10),
    mosi=Pin(11),
    miso=None
)

epd = EPD_2in66(
    spi=spi,
    cs_pin=9,
    dc_pin=8,
    rst_pin=12,
    busy_pin=13
)

# ── Initialize ──
print("Initializing display...")
epd.init()

# ── Clear to white ──
print("Clearing display...")
epd.clear()
print("Waiting 2 seconds...")
time.sleep(2)

# ── Draw test pattern ──
print("Drawing test pattern...")
epd.fill_black(0xFF)  # White canvas

# Border — should be flush with all 4 edges, no gap
epd.rect(0, 0, epd.width, epd.height, color='black')
epd.rect(1, 1, epd.width - 2, epd.height - 2, color='black')

# Top half: solid black rectangle
epd.fill_rect(10, 10, epd.width - 20, epd.height // 2 - 20, color='black')

# Bottom half: checkerboard
checker_y = epd.height // 2 + 10
checker_size = 10
for row in range(0, epd.height // 2 - 20, checker_size):
    for col in range(0, epd.width - 20, checker_size):
        if (row // checker_size + col // checker_size) % 2 == 0:
            epd.fill_rect(
                10 + col,
                checker_y + row,
                min(checker_size, epd.width - 20 - col),
                min(checker_size, epd.height // 2 - 20 - row),
                color='black'
            )

# ── Refresh ──
print("Refreshing display...")
epd.display(buf_black=epd.buffer_black)
print("Done! Check for:")
print("  - Border flush with all edges (no shifted gap)")
print("  - No red pixels anywhere")
print("  - Clean checkerboard with sharp squares")

epd.sleep()
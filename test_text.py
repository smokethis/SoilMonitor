"""
E-Paper Text Test
==================
Demonstrates text rendering at different scales, along with
a mock-up of what a soil sensor readout might look like.
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

print("Initializing display...")
epd.init()

print("Clearing display...")
epd.clear()
time.sleep(2)

print("Drawing text...")
epd.fill_black(0xFF)  # White canvas

# ── Title at 2× scale ──
epd.text("Soil Sensor", 4, 4, color='black', scale=2)

# ── Separator line ──
epd.hline(0, 26, epd.width, color='black')

# ── Mock sensor readings at 1× scale ──
y_pos = 34
epd.text("Moisture:  42%", 4, y_pos, color='black', scale=1)

y_pos += 12
epd.text("Temp:      21.5C", 4, y_pos, color='black', scale=1)

y_pos += 12
epd.text("Humidity:  65%", 4, y_pos, color='black', scale=1)

y_pos += 12
epd.text("Light:     830 lx", 4, y_pos, color='black', scale=1)

# ── Another separator ──
y_pos += 14
epd.hline(0, y_pos, epd.width, color='black')
y_pos += 4

# ── Status section ──
epd.text("Status: OK", 4, y_pos, color='black', scale=1)
y_pos += 12
epd.text("Battery: 87%", 4, y_pos, color='black', scale=1)

# ── Larger reading for at-a-glance viewing ──
y_pos += 20
epd.text("MOISTURE", 4, y_pos, color='black', scale=1)
y_pos += 12
epd.text("42%", 4, y_pos, color='black', scale=3)

# ── A scale/font sampler at the bottom ──
y_pos += 32
epd.hline(0, y_pos, epd.width, color='black')
y_pos += 4
epd.text("1x", 4, y_pos, scale=1)
epd.text("2x", 24, y_pos, scale=2)
epd.text("3x", 64, y_pos, scale=3)

# ── Refresh ──
print("Refreshing display...")
epd.display(buf_black=epd.buffer_black)
print("Done!")

epd.sleep()
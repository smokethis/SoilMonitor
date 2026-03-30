"""
Soil Moisture Monitor — Waveshare 2.66" Tri-Color E-Paper
============================================================
Reads a capacitive soil moisture sensor on ADC0 (GP26) and
displays a live dashboard with:

  - Large at-a-glance moisture percentage (red if out of range)
  - Raw ADC value for calibration/debugging
  - A horizontal gauge bar with red danger zones
  - A rolling history bar chart of recent readings

The display refreshes every few minutes. Tri-color e-paper
takes ~15 seconds per refresh (the controller has to cycle
voltages to move both black and red pigment particles), so
we sample the sensor frequently but only redraw periodically.

Wiring summary:
    Sensor AOUT →  Pico GP26     (pin 31, ADC0)
    Sensor VCC  →  Pico 3V3(OUT) (pin 36)
    Sensor GND  →  Pico GND      (pin 38)

    Display CLK  →  Pico GP10
    Display DIN  →  Pico GP11
    Display CS   →  Pico GP9
    Display DC   →  Pico GP8
    Display RST  →  Pico GP12
    Display BUSY →  Pico GP13
    Display VCC  →  Pico 3V3
    Display GND  →  Pico GND

    Button       →  Pico GP16    (pin 21, other leg to GND)
"""

from machine import Pin, SPI, ADC
import time
from epaper_2in66 import EPD_2in66

# ──────────────────────────────────────────────
# Configuration
# ──────────────────────────────────────────────

# Sensor calibration — adjust these after running test_soil_sensor.py
# with the probe in air and in water
AIR_VALUE = 52000     # ADC reading in dry air  (= 0% moisture)
WATER_VALUE = 25000   # ADC reading in water    (= 100% moisture)

# Danger thresholds (moisture percentage)
# Below DRY_THRESHOLD  → too dry, display in red
# Above WET_THRESHOLD  → waterlogged, display in red
DRY_THRESHOLD = 20
WET_THRESHOLD = 80

# Timing
SAMPLE_INTERVAL_S = 30    # Seconds between sensor reads
DISPLAY_INTERVAL_S = 300  # Seconds between display refreshes (5 min)
MAX_HISTORY = 20          # Number of readings to keep for the graph

# ──────────────────────────────────────────────
# Hardware setup
# ──────────────────────────────────────────────

soil_adc = ADC(Pin(26))

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

# ── Refresh button ──
# Wired between GP16 and GND. We enable the internal pull-up
# resistor so the pin reads HIGH (1) normally and goes LOW (0)
# when the button is pressed — no external resistor needed.
#
# An interrupt fires on the falling edge (the moment of press).
# We set a flag and debounce in software: the ISR ignores any
# edges within 300ms of the last one. This matters because
# mechanical buttons "bounce" — the contacts physically vibrate
# open and closed for a few milliseconds, generating dozens of
# false edges from a single press. 300ms is generous enough to
# swallow all of that without feeling sluggish.
_refresh_requested = False
_last_button_ms = 0

def _button_isr(pin):
    """Interrupt handler — sets a flag, main loop acts on it."""
    global _refresh_requested, _last_button_ms
    now = time.ticks_ms()
    if time.ticks_diff(now, _last_button_ms) > 300:
        _refresh_requested = True
        _last_button_ms = now

button = Pin(16, Pin.IN, Pin.PULL_UP)
button.irq(trigger=Pin.IRQ_FALLING, handler=_button_isr)


# ──────────────────────────────────────────────
# Sensor reading
# ──────────────────────────────────────────────

def read_moisture():
    """
    Read the soil sensor, return (raw_adc, moisture_percent).

    Takes 10 samples over ~100ms and averages them to smooth
    out ADC noise (the Pico 2 W's WiFi radio shares references
    with the ADC, which adds jitter).
    """
    total = 0
    for _ in range(10):
        total += soil_adc.read_u16()
        time.sleep_ms(10)

    raw = total // 10

    # Invert: lower voltage = wetter soil = higher percentage
    pct = (AIR_VALUE - raw) / (AIR_VALUE - WATER_VALUE) * 100
    pct = max(0.0, min(100.0, pct))

    return raw, pct


def moisture_status(pct):
    """Return a human-readable status and whether it's in a danger zone."""
    if pct < DRY_THRESHOLD:
        return "TOO DRY!", True
    elif pct > WET_THRESHOLD:
        return "TOO WET!", True
    elif pct < 35:
        return "Dry", False
    elif pct < 65:
        return "Good", False
    else:
        return "Moist", False


# ──────────────────────────────────────────────
# Display layout
# ──────────────────────────────────────────────
# The screen is 152px wide × 296px tall.
#
#  Y    Content
#  ───  ──────────────────────────────────
#   0   "SOIL" title (scale 3)
#  28   ── separator ──
#  33   Large moisture percentage (scale 4)
#  68   Status text + raw ADC (scale 1)
#  92   ── separator ──
#  97   Gauge bar labels: "0%"  "50%"  "100%"
# 108   Gauge bar (16px tall)
# 128   ── separator ──
# 133   "HISTORY" label
# 145   History bar chart (~130px tall)
# 280   ── separator ──
# 285   Reading counter / uptime

MARGIN = 4
BAR_LEFT = MARGIN
BAR_RIGHT = 148     # epd.width - MARGIN
BAR_WIDTH = BAR_RIGHT - BAR_LEFT  # 144px


def draw_dashboard(epd, pct, raw, status, is_danger, history, reading_num):
    """Redraw the entire dashboard to the local buffers."""

    # Start with clean white canvas, no red
    epd.fill_black(0xFF)
    epd.fill_red(0x00)

    # ── Title ──
    # "SOIL" in big letters; red if in danger, black otherwise
    title_color = 'red' if is_danger else 'black'
    epd.text("SOIL", MARGIN, 2, color=title_color, scale=3)
    # Smaller subtitle to the right
    epd.text("monitor", 80, 10, color='black', scale=1)

    # ── Separator ──
    y = 28
    epd.hline(0, y, epd.width, color='black')

    # ── Large moisture percentage ──
    # This is the number you see from across the room
    y = 33
    pct_str = "{:.0f}%".format(pct)
    pct_color = 'red' if is_danger else 'black'
    # Center it horizontally
    pct_w = epd.text_width(pct_str, scale=4)
    pct_x = (epd.width - pct_w) // 2
    epd.text(pct_str, pct_x, y, color=pct_color, scale=4)

    # ── Status + raw ADC ──
    y = 68
    status_color = 'red' if is_danger else 'black'
    epd.text(status, MARGIN, y, color=status_color, scale=1)
    # Right-align the raw ADC value
    raw_str = "ADC:{}".format(raw)
    raw_w = epd.text_width(raw_str, scale=1)
    epd.text(raw_str, epd.width - raw_w - MARGIN, y, color='black', scale=1)

    # ── Info line ──
    y += 12
    epd.text("Dry<{}%  Wet>{}%".format(DRY_THRESHOLD, WET_THRESHOLD),
             MARGIN, y, color='black', scale=1)

    # ── Separator ──
    y = 92
    epd.hline(0, y, epd.width, color='black')

    # ── Gauge bar ──
    draw_gauge(epd, y + 3, pct)

    # ── Separator ──
    y = 130
    epd.hline(0, y, epd.width, color='black')

    # ── History graph ──
    draw_history(epd, 133, history)

    # ── Separator ──
    y = 280
    epd.hline(0, y, epd.width, color='black')

    # ── Footer ──
    epd.text("Reading #{}".format(reading_num), MARGIN, 285, color='black', scale=1)


def draw_gauge(epd, y_top, pct):
    """
    Draw a horizontal moisture gauge bar.

    The bar is divided into three zones:
      [RED: 0–20%] [BLACK: 20–80%] [RED: 80–100%]

    The filled portion shows the current reading. Unfilled
    area is white with a thin outline. The current position
    gets a small triangle marker above the bar.

    Why red for both extremes: the sensor is meant to help
    you keep soil in the sweet spot. Too dry means the plant
    is stressed; too wet means root rot risk. Both deserve
    your immediate attention.
    """
    bar_h = 16
    bar_y = y_top + 12  # Leave room for labels above

    # Labels above the bar
    epd.text("0", BAR_LEFT, y_top, color='black', scale=1)
    epd.text("50", BAR_LEFT + BAR_WIDTH // 2 - 6, y_top, color='black', scale=1)
    epd.text("100", BAR_RIGHT - 18, y_top, color='black', scale=1)

    # Bar outline
    epd.rect(BAR_LEFT, bar_y, BAR_WIDTH, bar_h, color='black')

    # Red danger zone backgrounds (thin strips inside the bar)
    # Left zone: 0% to DRY_THRESHOLD
    dry_px = int(BAR_WIDTH * DRY_THRESHOLD / 100)
    for row in range(1, bar_h - 1):
        for col in range(1, dry_px):
            epd.pixel(BAR_LEFT + col, bar_y + row, 'red')

    # Right zone: WET_THRESHOLD to 100%
    wet_px = int(BAR_WIDTH * WET_THRESHOLD / 100)
    for row in range(1, bar_h - 1):
        for col in range(wet_px, BAR_WIDTH - 1):
            epd.pixel(BAR_LEFT + col, bar_y + row, 'red')

    # Fill bar up to current reading
    fill_px = int(BAR_WIDTH * pct / 100)
    fill_px = max(1, min(fill_px, BAR_WIDTH - 2))

    # Choose fill color: red if in danger zone, black if normal
    if pct < DRY_THRESHOLD or pct > WET_THRESHOLD:
        fill_color = 'red'
    else:
        fill_color = 'black'

    # Draw filled portion (overwrites the danger zone tint)
    for row in range(2, bar_h - 2):
        for col in range(1, fill_px):
            epd.pixel(BAR_LEFT + col, bar_y + row, fill_color)

    # Triangle marker above the bar at current position
    marker_x = BAR_LEFT + fill_px
    marker_x = max(BAR_LEFT + 2, min(marker_x, BAR_RIGHT - 2))
    for i in range(3):
        epd.pixel(marker_x - i, bar_y - 1 - i, 'black')
        epd.pixel(marker_x + i, bar_y - 1 - i, 'black')
        if i > 0:
            for fill in range(-i + 1, i):
                epd.pixel(marker_x + fill, bar_y - 1 - i, 'black')


def draw_history(epd, y_top, history):
    """
    Draw a bar chart of recent moisture readings.

    Each reading becomes a vertical bar. The bar height is
    proportional to moisture %, drawn from a baseline at the
    bottom. Bars in the danger zone are red; normal bars are
    black. The most recent reading is on the right.

    With 20 bars at 6px wide + 1px gap = 7px each, the chart
    is 140px wide — fits nicely in the 144px available width.
    """
    epd.text("HISTORY", MARGIN, y_top, color='black', scale=1)

    chart_top = y_top + 12
    chart_h = 120       # Max bar height in pixels
    chart_bottom = chart_top + chart_h

    # Baseline
    epd.hline(BAR_LEFT, chart_bottom, BAR_WIDTH, color='black')

    if not history:
        epd.text("No data yet", MARGIN + 20, chart_top + 50,
                 color='black', scale=1)
        return

    # Bar dimensions — evenly space whatever readings we have
    num_bars = len(history)
    bar_w = 6
    gap = 1
    total_chart_w = num_bars * (bar_w + gap) - gap
    # Center the bars in the available width
    chart_left = BAR_LEFT + (BAR_WIDTH - total_chart_w) // 2

    for i, pct in enumerate(history):
        bar_x = chart_left + i * (bar_w + gap)
        bar_h_px = int(chart_h * pct / 100)
        bar_h_px = max(1, bar_h_px)  # At least 1px tall

        # Red if in danger zone, black otherwise
        if pct < DRY_THRESHOLD or pct > WET_THRESHOLD:
            bar_color = 'red'
        else:
            bar_color = 'black'

        epd.fill_rect(bar_x, chart_bottom - bar_h_px, bar_w, bar_h_px,
                       color=bar_color)

    # Scale labels on the left edge
    epd.text("0", 0, chart_bottom - 6, color='black', scale=1)
    epd.text("50", 0, chart_top + chart_h // 2 - 4, color='black', scale=1)

    # Dashed midline at 50%
    mid_y = chart_top + chart_h // 2
    for x in range(BAR_LEFT, BAR_RIGHT, 4):
        epd.pixel(x, mid_y, 'black')


# ──────────────────────────────────────────────
# Main loop
# ──────────────────────────────────────────────

def main():
    print("Soil Moisture Monitor")
    print("=" * 40)

    # Initialize display
    print("Initializing display...")
    epd.init()

    print("Clearing display...")
    epd.clear()
    time.sleep(2)

    history = []
    reading_num = 0
    last_display_time = 0  # Force immediate first draw

    print("Starting monitoring loop...")
    print("  Sample every {}s, refresh display every {}s".format(
        SAMPLE_INTERVAL_S, DISPLAY_INTERVAL_S))
    print()

    while True:
        # ── Take a reading ──
        raw, pct = read_moisture()
        reading_num += 1
        status, is_danger = moisture_status(pct)

        # Add to history, keeping only the most recent readings
        history.append(pct)
        if len(history) > MAX_HISTORY:
            history.pop(0)

        print("#{:>4d}  ADC:{:>6d}  Moisture:{:>5.1f}%  {}".format(
            reading_num, raw, pct, status))

        # ── Update display if enough time has passed or button pressed ──
        global _refresh_requested
        now = time.ticks_ms()
        elapsed = time.ticks_diff(now, last_display_time)
        button_pressed = _refresh_requested

        if elapsed >= DISPLAY_INTERVAL_S * 1000 or reading_num == 1 or button_pressed:
            if button_pressed:
                print("  -> Button press — refreshing now!")
                _refresh_requested = False
            print("  -> Refreshing display...")
            draw_dashboard(epd, pct, raw, status, is_danger,
                           history, reading_num)
            epd.display()
            last_display_time = time.ticks_ms()
            print("  -> Done!")

        # ── Wait for next sample ──
        # Instead of one long sleep, we use short 250ms chunks
        # so we can react to a button press quickly. When the
        # button fires mid-sleep, we break out, take a fresh
        # reading, and immediately refresh the display — so the
        # screen always shows current data, not stale numbers.
        for _ in range(SAMPLE_INTERVAL_S * 4):
            time.sleep_ms(250)
            if _refresh_requested:
                break


# Run it!
main()
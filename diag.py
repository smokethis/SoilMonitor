"""
E-Paper Diagnostic Script
==========================
Run this BEFORE the main test to check whether the display
is actually responding to commands. It tests two things:

1. Is the BUSY pin behaving correctly?
   - If BUSY is stuck HIGH, the driver will timeout on every
     operation and the display will ignore everything.
   - If BUSY is stuck LOW, the driver races ahead before the
     controller has finished processing commands.

2. Does a hardware reset + software reset produce a BUSY pulse?
   - After a software reset (command 0x12), the controller should
     pull BUSY HIGH for a moment while it resets, then release it.
     If we see that pulse, we know SPI communication is working
     and the controller is alive.
"""

from machine import Pin, SPI
import time

# ── Pin setup (must match your wiring) ──
spi = SPI(
    1,
    baudrate=4_000_000,
    polarity=0,
    phase=0,
    sck=Pin(10),
    mosi=Pin(11),
    miso=None
)

cs   = Pin(9, Pin.OUT, value=1)
dc   = Pin(8, Pin.OUT, value=0)
rst  = Pin(12, Pin.OUT, value=1)
busy = Pin(13, Pin.IN)


def send_command(cmd):
    dc.value(0)
    cs.value(0)
    spi.write(bytearray([cmd]))
    cs.value(1)


def send_data(data):
    dc.value(1)
    cs.value(0)
    spi.write(bytearray([data]))
    cs.value(1)


# ─────────────────────────────────────
# Test 1: Check BUSY pin resting state
# ─────────────────────────────────────
print("=" * 50)
print("TEST 1: BUSY pin resting state")
print("=" * 50)

# Read BUSY several times over 500ms to see if it's stable
readings = []
for i in range(10):
    readings.append(busy.value())
    time.sleep_ms(50)

if all(r == 0 for r in readings):
    print("BUSY reads LOW (0) — this is the expected idle state.")
    print("The display should be ready to accept commands.")
elif all(r == 1 for r in readings):
    print("BUSY reads HIGH (1) — the display thinks it's busy!")
    print("This could mean:")
    print("  - The BUSY wire isn't connected")
    print("  - The pin has a pull-up and nothing is driving it")
    print("  - The display hasn't been reset yet (try power cycling)")
else:
    print("BUSY is fluctuating:", readings)
    print("This is unusual — check your wiring.")

print()

# ─────────────────────────────────────
# Test 2: Hardware reset pulse
# ─────────────────────────────────────
print("=" * 50)
print("TEST 2: Hardware reset")
print("=" * 50)

print("Sending hardware reset pulse...")
rst.value(1)
time.sleep_ms(50)
rst.value(0)
time.sleep_ms(2)
rst.value(1)
time.sleep_ms(10)

# Sample BUSY rapidly after reset
busy_after_reset = busy.value()
print(f"BUSY immediately after reset: {busy_after_reset}")

# Wait up to 3 seconds for BUSY to settle
start = time.ticks_ms()
went_high = False
went_low_again = False

while time.ticks_diff(time.ticks_ms(), start) < 3000:
    val = busy.value()
    if val == 1 and not went_high:
        went_high = True
        print(f"  BUSY went HIGH at {time.ticks_diff(time.ticks_ms(), start)}ms")
    if val == 0 and went_high and not went_low_again:
        went_low_again = True
        elapsed = time.ticks_diff(time.ticks_ms(), start)
        print(f"  BUSY returned LOW at {elapsed}ms — controller is alive!")
        break
    time.sleep_ms(10)

if not went_high:
    print("  BUSY never went HIGH after reset.")
    print("  The controller may not be responding to the reset pin.")
if went_high and not went_low_again:
    print("  BUSY went HIGH but never came back LOW.")
    print("  The controller might be stuck. Try power cycling.")

print()

# ─────────────────────────────────────
# Test 3: Software reset via SPI
# ─────────────────────────────────────
print("=" * 50)
print("TEST 3: Software reset (SPI command 0x12)")
print("=" * 50)

# Wait for any existing busy state to clear
timeout = 5000
start = time.ticks_ms()
while busy.value() == 1:
    if time.ticks_diff(time.ticks_ms(), start) > timeout:
        print("Timed out waiting for BUSY to clear before SW reset.")
        break
    time.sleep_ms(50)

print("Sending software reset command (0x12)...")
send_command(0x12)
time.sleep_ms(10)

# Watch for BUSY response
start = time.ticks_ms()
saw_busy = False
saw_ready = False

while time.ticks_diff(time.ticks_ms(), start) < 5000:
    val = busy.value()
    if val == 1 and not saw_busy:
        saw_busy = True
        print(f"  BUSY went HIGH at {time.ticks_diff(time.ticks_ms(), start)}ms — command received!")
    if val == 0 and saw_busy and not saw_ready:
        saw_ready = True
        elapsed = time.ticks_diff(time.ticks_ms(), start)
        print(f"  BUSY returned LOW at {elapsed}ms — reset complete!")
        break
    time.sleep_ms(10)

if saw_busy and saw_ready:
    print("\nSPI communication is working! The display controller")
    print("received the reset command and processed it.")
elif not saw_busy:
    print("\nBUSY never went HIGH after the software reset command.")
    print("Possible causes:")
    print("  - SPI data isn't reaching the display (check DIN/CLK wiring)")
    print("  - CS isn't selecting the display (check CS wiring)")
    print("  - The BUSY pin isn't connected properly")
else:
    print("\nBUSY went HIGH but never returned LOW (stuck in reset).")

print()
print("=" * 50)
print("SUMMARY")
print("=" * 50)
if saw_busy and saw_ready:
    print("Display is communicating! The issue is likely in the")
    print("refresh command sequence, not the wiring.")
    print("Try the updated driver with the corrected refresh sequence.")
elif not saw_busy and all(r == 0 for r in readings):
    print("BUSY stays LOW through everything. Either:")
    print("  1. BUSY wire is disconnected (check GP13 to BUSY)")
    print("  2. SPI isn't reaching the display (check CLK and DIN)")
elif all(r == 1 for r in readings):
    print("BUSY is stuck HIGH. The display controller isn't releasing it.")
    print("Try: power cycle the Pico, reseat the ribbon cable,")
    print("or check that RST is wired to GP12.")
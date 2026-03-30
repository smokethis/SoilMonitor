"""
Soil Moisture Sensor Test
==========================
Reads a capacitive soil moisture sensor on ADC0 (GP26) and
prints the raw ADC value plus a rough percentage.

Wiring:
    Sensor VCC  →  Pico 3V3(OUT) (pin 36)
    Sensor GND  →  Pico GND      (pin 38)
    Sensor AOUT →  Pico GP26     (pin 31, ADC0)

How capacitive soil sensors work:
    The probe is essentially one plate of a capacitor, and the
    soil around it is the dielectric. Water has a very high
    dielectric constant (~80) compared to dry soil (~4) or air
    (~1), so as the soil gets wetter, the capacitance increases.

    The sensor's onboard circuit (usually a 555 timer or similar
    oscillator) converts that capacitance into a voltage:
      - DRY soil   → higher voltage  → higher ADC reading
      - WET soil   → lower voltage   → lower ADC reading

    This is the opposite of what you might expect! The percentage
    calculation below inverts this so that higher % = wetter.

Calibration:
    Every sensor is slightly different, and soil type matters too
    (clay holds water differently than sandy soil). To get accurate
    readings you need two reference points:

    1. AIR_VALUE:  Hold the sensor in open air (bone dry).
                   This is your 0% moisture reading.

    2. WATER_VALUE: Submerge the sensor in a glass of water
                    (just the prongs, not the electronics!).
                    This is your 100% moisture reading.

    Run this script in both conditions and note the raw ADC
    values, then update the constants below.
"""

from machine import Pin, ADC
import time

# ── ADC setup ──
# The Pico's ADC is 12-bit internally (0–4095) but MicroPython's
# read_u16() scales it to 16-bit (0–65535) for consistency across
# different microcontrollers. We'll work with the raw u16 values.
soil_adc = ADC(Pin(26))

# ── Calibration constants ──
# These are rough starting values for a typical capacitive sensor
# powered at 3.3V. You WILL need to adjust these for your specific
# sensor — run the script and note what you get in air vs water.
AIR_VALUE = 52000    # Raw ADC reading in dry air (0% moisture)
WATER_VALUE = 25000  # Raw ADC reading submerged in water (100%)

def read_moisture():
    """
    Read the soil moisture sensor and return (raw, percent).
    
    Takes 10 readings over ~100ms and averages them to smooth
    out noise. ADC readings on the Pico can jitter by a few
    hundred counts, especially on a breadboard with the WiFi
    radio nearby, so averaging helps a lot.
    """
    total = 0
    num_samples = 10
    for _ in range(num_samples):
        total += soil_adc.read_u16()
        time.sleep_ms(10)
    
    raw = total // num_samples
    
    # Convert to percentage (inverted — lower voltage = wetter)
    # Clamp to 0–100 range in case the reading is outside
    # the calibration bounds
    percent = (AIR_VALUE - raw) / (AIR_VALUE - WATER_VALUE) * 100
    percent = max(0, min(100, percent))
    
    return raw, percent


# ── Main loop: read and print every 2 seconds ──
print("Soil Moisture Sensor Test")
print("=" * 40)
print(f"Calibration: air={AIR_VALUE}, water={WATER_VALUE}")
print(f"Reading from ADC0 (GP26) every 2 seconds...")
print(f"{'Raw ADC':>10}  {'Moisture':>8}")
print("-" * 22)

while True:
    raw, pct = read_moisture()
    print(f"{raw:>10}  {pct:>7.1f}%")
    time.sleep(2)
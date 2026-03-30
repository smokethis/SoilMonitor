"""
Waveshare 2.66" e-Paper Display Driver for MicroPython
=======================================================
Resolution: 296 x 152 pixels
Interface: SPI

Based closely on Waveshare's official Python driver (epd2in66.py),
adapted for MicroPython on the Raspberry Pi Pico 2 W.

Key differences from Waveshare's CPython driver:
  - Uses machine.SPI and machine.Pin instead of RPi.GPIO/spidev
  - Includes a local pixel buffer and drawing primitives since
    MicroPython doesn't have PIL/Pillow
  - Clears red RAM (0x26) with 0x00 instead of 0xFF during clear()
    because this particular display has tri-color hardware that
    interprets 0x26 as the red layer (1 = red pixel)
"""

from machine import Pin, SPI
import time
from font5x8 import FONT, FONT_WIDTH, FONT_HEIGHT

EPD_WIDTH = 152
EPD_HEIGHT = 296


class EPD_2in66:
    """Driver for the Waveshare 2.66 inch e-Paper display."""

    def __init__(self, spi, cs_pin, dc_pin, rst_pin, busy_pin):
        self.spi = spi
        self.cs = Pin(cs_pin, Pin.OUT, value=1)
        self.dc = Pin(dc_pin, Pin.OUT, value=0)
        self.rst = Pin(rst_pin, Pin.OUT, value=1)
        self.busy = Pin(busy_pin, Pin.IN)

        self.width = EPD_WIDTH
        self.height = EPD_HEIGHT

        self._buffer_size = (self.width * self.height) // 8
        self.buffer_black = bytearray(self._buffer_size)

    def _send_command(self, cmd):
        """Send a command byte (DC=LOW)."""
        self.dc.value(0)
        self.cs.value(0)
        self.spi.write(bytearray([cmd]))
        self.cs.value(1)

    def _send_data(self, data):
        """Send one data byte (DC=HIGH)."""
        self.dc.value(1)
        self.cs.value(0)
        self.spi.write(bytearray([data]))
        self.cs.value(1)

    def _send_data_bulk(self, data):
        """Send a buffer of data bytes in one SPI transaction (DC=HIGH)."""
        self.dc.value(1)
        self.cs.value(0)
        self.spi.write(data)
        self.cs.value(1)

    def _wait_busy(self, timeout_ms=20000):
        """Block until BUSY goes LOW (idle)."""
        start = time.ticks_ms()
        while self.busy.value() == 1:
            time.sleep_ms(200)
            if time.ticks_diff(time.ticks_ms(), start) > timeout_ms:
                print("Warning: BUSY timeout after {}ms".format(timeout_ms))
                return False
        return True

    def hw_reset(self):
        """Hardware reset — matches Waveshare's 200ms/2ms/200ms timing."""
        self.rst.value(1)
        time.sleep_ms(200)
        self.rst.value(0)
        time.sleep_ms(2)
        self.rst.value(1)
        time.sleep_ms(200)

    def init(self):
        """
        Initialize the display controller.

        Register values match Waveshare's reference driver (full refresh
        mode, mode=0). Note the X address range starts at 0x01 (not 0x00)
        and the Y range ends at 0x0128 (not 0x0127) — getting these wrong
        shifts the image on screen.
        """
        self.hw_reset()

        self._send_command(0x12)  # Software reset
        time.sleep_ms(300)        # Waveshare uses a fixed 300ms delay here
        self._wait_busy()

        # Data entry mode: X increment, Y increment
        self._send_command(0x11)
        self._send_data(0x03)

        # RAM X address range: 0x01 to 0x13
        # (19 bytes = 152 pixels, but 1-indexed on this controller)
        self._send_command(0x44)
        self._send_data(0x01)
        self._send_data(0x13)

        # RAM Y address range: 0x0000 to 0x0128 (296 decimal)
        self._send_command(0x45)
        self._send_data(0x00)
        self._send_data(0x00)
        self._send_data(0x28)
        self._send_data(0x01)

        # Border waveform: 0x01 for full refresh mode
        self._send_command(0x3C)
        self._send_data(0x01)

    def _set_cursor(self):
        """
        Set RAM cursor to the start position for writing image data.

        Waveshare's reference sets this to X=0x01, Y=0x0127 before
        every write. The cursor position combined with the data entry
        mode (0x03) and address ranges determines how pixel data maps
        to physical display locations.
        """
        self._send_command(0x4E)
        self._send_data(0x01)

        self._send_command(0x4F)
        self._send_data(0x27)
        self._send_data(0x01)

    def _turn_on_display(self):
        """
        Trigger the display refresh.

        Waveshare's reference just sends command 0x20 (master activation)
        with no preceding 0x22 — the controller uses its OTP-stored
        lookup table by default.
        """
        self._send_command(0x20)
        self._wait_busy()

    def clear(self):
        """
        Clear the display to white.

        Writes 0xFF (white) to the B/W RAM (0x24) and 0x00 (no red)
        to the red RAM (0x26).

        On Waveshare's reference driver for pure B/W displays, both
        buffers get 0xFF. But on tri-color hardware, buffer 0x26
        controls red pixels where 1=red, so we write 0x00 to suppress
        any red output.
        """
        self._set_cursor()

        # B/W buffer: all white
        buf_white = bytearray([0xFF] * self._buffer_size)
        self._send_command(0x24)
        self._send_data_bulk(buf_white)

        # Red buffer: no red (0x00 = no red pixels)
        buf_clear = bytearray(self._buffer_size)  # defaults to 0x00
        self._send_command(0x26)
        self._send_data_bulk(buf_clear)

        self._turn_on_display()

    def display(self, buf_black=None):
        """
        Write the B/W image buffer to the display and refresh.

        Only writes to 0x24 (B/W RAM). Does NOT touch 0x26 (red RAM)
        — after clear() has zeroed it out, it stays clean.
        """
        self._set_cursor()

        self._send_command(0x24)
        if buf_black:
            self._send_data_bulk(buf_black)
        else:
            self._send_data_bulk(self.buffer_black)

        self._turn_on_display()

    # ── Drawing primitives ──────────────────────────────

    def fill_black(self, value=0xFF):
        """Fill the local buffer. 0xFF=white, 0x00=black."""
        for i in range(len(self.buffer_black)):
            self.buffer_black[i] = value

    def pixel(self, x, y, color='black'):
        """
        Set a single pixel in the local buffer.

        Args:
            x: Column (0 to 151)
            y: Row (0 to 295)
            color: 'black' or 'white'
        """
        if x < 0 or x >= self.width or y < 0 or y >= self.height:
            return

        byte_index = (y * (self.width // 8)) + (x // 8)
        bit_mask = 0x80 >> (x % 8)

        if color == 'black':
            self.buffer_black[byte_index] &= ~bit_mask
        elif color == 'white':
            self.buffer_black[byte_index] |= bit_mask

    def hline(self, x, y, width, color='black'):
        """Draw a horizontal line."""
        for i in range(width):
            self.pixel(x + i, y, color)

    def vline(self, x, y, height, color='black'):
        """Draw a vertical line."""
        for i in range(height):
            self.pixel(x, y + i, color)

    def rect(self, x, y, w, h, color='black'):
        """Draw a rectangle outline."""
        self.hline(x, y, w, color)
        self.hline(x, y + h - 1, w, color)
        self.vline(x, y, h, color)
        self.vline(x + w - 1, y, h, color)

    def fill_rect(self, x, y, w, h, color='black'):
        """Draw a filled rectangle."""
        for row in range(h):
            self.hline(x, y + row, w, color)

    def text(self, string, x, y, color='black', scale=1):
        """
        Draw a string of text at position (x, y).

        Uses the 5×8 bitmap font from font5x8.py. Each character
        is 5 pixels wide with 1 pixel spacing, so the effective
        character cell is 6px wide (6 × scale).

        Args:
            string: Text to draw
            x: Left edge pixel position
            y: Top edge pixel position
            color: 'black' or 'white'
            scale: Integer multiplier (1 = 5×8, 2 = 10×16, etc.)
        """
        cursor_x = x
        for char in string:
            if char == '\n':
                # Newline: move down by one character height + 1px spacing
                y += (FONT_HEIGHT + 1) * scale
                cursor_x = x
                continue

            # Look up the character's column data, fall back to a solid block
            glyph = FONT.get(char, (0x7F, 0x7F, 0x7F, 0x7F, 0x7F))

            # Draw each column of the character
            for col_idx in range(FONT_WIDTH):
                col_data = glyph[col_idx]
                for row_idx in range(FONT_HEIGHT):
                    if col_data & (1 << row_idx):
                        # Scale up: each font pixel becomes a scale×scale block
                        if scale == 1:
                            self.pixel(cursor_x + col_idx, y + row_idx, color)
                        else:
                            for sx in range(scale):
                                for sy in range(scale):
                                    self.pixel(
                                        cursor_x + col_idx * scale + sx,
                                        y + row_idx * scale + sy,
                                        color
                                    )

            # Advance cursor by character width + 1px spacing
            cursor_x += (FONT_WIDTH + 1) * scale

    def text_width(self, string, scale=1):
        """Calculate the pixel width a string would occupy."""
        if not string:
            return 0
        # Each char is FONT_WIDTH pixels + 1px gap, minus the trailing gap
        num_chars = len(string.split('\n')[0])  # Width of first line
        return num_chars * (FONT_WIDTH + 1) * scale - scale

    def sleep(self):
        """Enter deep sleep. Call init() to wake."""
        self._send_command(0x10)
        self._send_data(0x01)
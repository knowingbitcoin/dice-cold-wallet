"""Controlador de la Raspberry Pi Zero con la pantalla Waveshare 1.3" LCD HAT.

Pantalla ST7789 de 240x240 por SPI y botones por GPIO. Las librerías del
hardware (spidev y gpiozero) se importan solo aquí y solo al arrancar, para
que en el Mac el resto del programa funcione sin ellas.

PINES (numeración BCM). Son los de la ficha y los ejemplos de Waveshare para el
1.3inch LCD HAT, pero HAY QUE CONFIRMARLOS con la ficha de la placa que llegue
(https://www.waveshare.com/wiki/1.3inch_LCD_HAT) antes de dar nada por bueno:
  Pantalla: SPI0 con CE0 (GPIO 8), DC = 25, RST = 27, luz de fondo (BL) = 24.
  Joystick: arriba = 6, abajo = 19, izquierda = 5, derecha = 26, pulsar = 13.
  Botones:  KEY1 = 21, KEY2 = 20, KEY3 = 16.
Los botones van a masa al pulsarlos: se leen con resistencia interna a 3,3 V.

PREPARACIÓN DE LA RASPBERRY (fuera de este programa, pero imprescindible):
- Activar SPI (raspi-config → Interface Options → SPI).
- Quitar la memoria de intercambio, para que la semilla nunca pase a la tarjeta
  SD: `sudo dphys-swapfile swapoff && sudo systemctl disable dphys-swapfile`.
- Registros del sistema solo en memoria: Storage=volatile en
  /etc/systemd/journald.conf. Este programa no imprime nada, pero así ningún
  mensaje de error podría quedar en la tarjeta.
- Mejor aún, sistema de ficheros de solo lectura (raspi-config → Performance →
  Overlay File System).
- La Pi Zero v1.3 no tiene wifi ni Bluetooth: no conectar nunca un adaptador.
"""

from __future__ import annotations

import queue
import time

from PIL import Image, ImageChops

from coldwallet.ui.app import (
    DOWN,
    KEY1,
    KEY2,
    KEY3,
    LEFT,
    PRESS,
    RIGHT,
    UP,
    WalletApp,
)

# Pines BCM (ver el aviso de arriba: confirmar con la ficha de Waveshare).
PIN_DC = 25
PIN_RST = 27
PIN_BL = 24
SPI_BUS = 0
SPI_DEVICE = 0  # CE0
SPI_HZ = 40_000_000

BUTTON_PINS = {
    UP: 6,
    DOWN: 19,
    LEFT: 5,
    RIGHT: 26,
    PRESS: 13,
    KEY1: 21,
    KEY2: 20,
    KEY3: 16,
}

WIDTH = 240
HEIGHT = 240


class ST7789:
    """Controlador mínimo de la pantalla ST7789 (secuencia de los ejemplos de Waveshare)."""

    def __init__(self) -> None:
        import spidev  # solo existe en la Raspberry
        from gpiozero import DigitalOutputDevice

        self._spi = spidev.SpiDev()
        self._spi.open(SPI_BUS, SPI_DEVICE)
        self._spi.max_speed_hz = SPI_HZ
        self._spi.mode = 0b00
        self._dc = DigitalOutputDevice(PIN_DC)
        self._rst = DigitalOutputDevice(PIN_RST)
        self._bl = DigitalOutputDevice(PIN_BL)
        self._init_panel()
        self._bl.on()

    def _command(self, value: int) -> None:
        self._dc.off()
        self._spi.writebytes([value])

    def _data(self, *values: int) -> None:
        self._dc.on()
        self._spi.writebytes(list(values))

    def _init_panel(self) -> None:
        self._rst.on()
        time.sleep(0.01)
        self._rst.off()
        time.sleep(0.01)
        self._rst.on()
        time.sleep(0.12)
        self._command(0x36)  # orientación de la memoria
        self._data(0x70)
        self._command(0x3A)  # 16 bits por píxel (RGB565)
        self._data(0x05)
        self._command(0xB2)
        self._data(0x0C, 0x0C, 0x00, 0x33, 0x33)
        self._command(0xB7)
        self._data(0x35)
        self._command(0xBB)
        self._data(0x19)
        self._command(0xC0)
        self._data(0x2C)
        self._command(0xC2)
        self._data(0x01)
        self._command(0xC3)
        self._data(0x12)
        self._command(0xC4)
        self._data(0x20)
        self._command(0xC6)
        self._data(0x0F)
        self._command(0xD0)
        self._data(0xA4, 0xA1)
        self._command(0xE0)
        self._data(0xD0, 0x04, 0x0D, 0x11, 0x13, 0x2B, 0x3F, 0x54, 0x4C, 0x18, 0x0D, 0x0B, 0x1F, 0x23)
        self._command(0xE1)
        self._data(0xD0, 0x04, 0x0C, 0x11, 0x13, 0x2C, 0x3F, 0x44, 0x51, 0x2F, 0x1F, 0x1F, 0x20, 0x23)
        self._command(0x21)  # colores invertidos: este panel los necesita
        self._command(0x11)  # salir del reposo
        time.sleep(0.12)
        self._command(0x29)  # encender la pantalla

    def _window(self, x0: int, y0: int, x1: int, y1: int) -> None:
        self._command(0x2A)
        self._data(x0 >> 8, x0 & 0xFF, x1 >> 8, x1 & 0xFF)
        self._command(0x2B)
        self._data(y0 >> 8, y0 & 0xFF, y1 >> 8, y1 & 0xFF)
        self._command(0x2C)

    def show(self, image: Image.Image) -> None:
        """Envía una imagen de 240x240 a la pantalla."""
        buffer = to_rgb565(image)
        self._window(0, 0, WIDTH - 1, HEIGHT - 1)
        self._dc.on()
        chunk = 4096
        for start in range(0, len(buffer), chunk):
            self._spi.writebytes2(buffer[start : start + chunk])
        del buffer

    def blank(self) -> None:
        self.show(Image.new("RGB", (WIDTH, HEIGHT), (0, 0, 0)))


def to_rgb565(image: Image.Image) -> bytes:
    """Convierte la imagen a RGB565 (dos bytes por píxel) sin numpy.

    Se hace con tablas de PIL, que es rápido incluso en la Pi Zero:
    byte alto = rojo (5 bits) + verde (3 bits altos);
    byte bajo = verde (3 bits bajos) + azul (5 bits).
    """
    red, green, blue = image.convert("RGB").split()
    high = ImageChops.add(red.point(lambda v: v & 0xF8), green.point(lambda v: v >> 5))
    low = ImageChops.add(green.point(lambda v: (v << 3) & 0xE0), blue.point(lambda v: v >> 3))
    return Image.merge("LA", (high, low)).tobytes()


class Buttons:
    """Joystick y botones: cada pulsación entra en una cola de eventos."""

    def __init__(self) -> None:
        from gpiozero import Button

        self.events: queue.Queue[str] = queue.Queue()
        self._buttons = []
        for event, pin in BUTTON_PINS.items():
            button = Button(pin, pull_up=True, bounce_time=0.05)
            button.when_pressed = self._make_handler(event)
            self._buttons.append(button)

    def _make_handler(self, event: str):
        def handler() -> None:
            self.events.put(event)

        return handler


def run() -> None:
    """Bucle principal en la Raspberry."""
    display = ST7789()
    buttons = Buttons()
    app = WalletApp()
    try:
        display.show(app.render())
        while True:
            event = buttons.events.get()
            app.handle(event)
            display.show(app.render())
            if app.has_pending_work:
                app.run_pending_work()
                display.show(app.render())
    except Exception:
        # Sin detalles ni trazas: podrían contener datos secretos.
        app.reset()
        display.show(WalletApp.render_error())
        while True:
            time.sleep(3600)

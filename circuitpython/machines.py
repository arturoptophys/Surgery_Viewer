import json
import usb_cdc
import board
import digitalio
from supervisor import ticks_ms
import time
import rp2pio
import array
import adafruit_pioasm

from timing_utils import ticks_diff, ticks_less

data_serial = usb_cdc.data  # ensure data serial is on in boot.py

MAX_FPS = 150  # maximum fps for the camera
#some colors for the LED
RED = (255, 0, 0)
YELLOW = (255, 150, 0)
GREEN = (0, 255, 0)
CYAN = (0, 255, 255)
BLUE = (0, 0, 255)
PURPLE = (180, 0, 255)



class PIO_trigger:
    """Class to control a pulsing of a GPIO with a PIO state machine"""
    def __init__(self, board_pin: board.LED, name: str, fps: int = 10, verbose: bool = False):
        self.name = name
        self.verbose = verbose
        self.is_active = True  # switch for the Machine to be ignored in update loop
        self.board_pin = board_pin  # board pin
        self._fps = fps
        self.pulse_dur = 5  # in ms duration of on of each burst
        self.pulse_t0 = ticks_ms()  # for first call
        self.last_t = self.pulse_t0
        self._off_dur = int(1000 / self._fps - self.pulse_dur)
        self.pulse_active = False
        self.last_duration = 0
        self.blink = adafruit_pioasm.assemble(
            """
            .program frame_trigger
                pull block    ; These two instructions take the off_duration in cycles
                out y, 32     ; and store it in y
            forever:
                mov x, y
                set pins, 1  [24] ; Turn LED on   
                noop [24] ;  on for 50 cycles
                set pins, 0   ; Turn LED off
            lp2:
                jmp x-- lp2   ; Delay for the number of cycles again
                jmp forever   ; Blink forever!
            """
        )
        self.sm = None
        self.create_state_machine()

    @property
    def fps(self):
        """The frequency of the pulsing, in Hz."""
        return self._fps

    @fps.setter
    def fps(self, new_value: float):
        if self.pulse_active: # dont change the property if currently pulsing
            print('Cannot change FPS while pulsing')
            return
        if new_value > MAX_FPS:
            new_value = MAX_FPS
            if self.verbose:
                print(f'Input outside of range. Setting to {new_value}Hz')
        self._fps = new_value
        self._off_dur = int(1000 / self._fps - self.pulse_dur)
        self.create_state_machine()

    def create_state_machine(self):
        """Create the state machine for the PIO trigger."""
        if self.sm:
            self.sm.stop()
            self.sm.deinit()
        self.sm = rp2pio.StateMachine(
            self.blink,
            frequency=10_000,  #if freqency is changed number of on cycles have to be modified
            first_set_pin=self.board_pin,
            wait_for_txstall=False,
        )

    def start_pulsing(self) -> [bool, str]:
        """Start pulsing the GPIO at the set frequency."""
        if self.pulse_active:
            print('Already pulsing')
            return 0
        data = array.array("I", [self.sm.frequency // self.fps - 50])  # need to substract the off time
        if self.sm:
            self.sm.write(data)
            self.pulse_active = True
            self.pulse_t0 = ticks_ms()
            return f'Started pulsing at {self.fps} Hz'
        else:
            print('No state machine available')
            return 0

    def stop_pulsing(self) -> [bool, str]:
        """Stop pulsing the GPIO."""
        if not self.pulse_active:
            print('Not pulsing')
            return 0
        if self.sm:
            self.sm.stop()
            self.pulse_active = False
            self.last_t = ticks_ms()
            self.last_duration = ticks_diff(self.last_t, self.pulse_t0) / 1000
            return f'Stopped pulsing after {self.last_duration:0.1f} s'
        else:
            print('No state machine available')
            return 0

    def update(self):
        """Not implemneted as not needed for PIO"""
        pass


class FPS_trigger:
    def __init__(self, board_pin: digitalio.DigitalInOut, name: str, pulse_dur: int = 5, fps: int = 10,
                 verbose: bool = False):
        self.name = name
        self.verbose = verbose
        self.is_active = True  # switch for the Machine to be ignored in update loop
        self.board_pin = board_pin  # digital output pin
        self.pulse_dur = pulse_dur  # in ms duration of opening time of each burst
        self.nr_pulses_given = 0
        self._fps = fps
        self.pulse_t0 = ticks_ms()  # for first call
        self.last_t = self.pulse_t0
        self._off_dur = int(1000 / self._fps - self.pulse_dur)
        self.pulse_active = False
        self.graceful_stop = False  # reset
        self.last_duration = 0

    def __repr__(self):
        return f'{self.name} {"" if self.pulse_active else "Not"} pulsing at {self.fps} Hz'

    @property
    def fps(self):
        return self._fps

    @fps.setter
    def fps(self, new_value: float):
        if new_value > MAX_FPS:
            new_value = MAX_FPS
            if self.verbose:
                print(f'Input outside of range. Setting to {new_value}Hz')
        self._fps = new_value
        self._off_dur = int(1000 / self._fps - self.pulse_dur)

    @micropython.native
    def start_pulsing(self):
        # will start pulsing on next update loop
        self.pulse_active = True
        self.graceful_stop = False  # reset
        self.nr_pulses_given = 0
        self.board_pin.value = True  # drive pin_high
        self.pulse_t0 = ticks_ms()
        self.last_t = self.pulse_t0
        if self.verbose:
            print(f'Started pulsing {self.pulse_t0}')

    @micropython.native
    def stop_pulsing_immediatly(self):
        '''
        stops the pulsation immediately
        '''
        self.pulse_active = False
        self.board_pin.value = False
        self.last_duration = ticks_diff(ticks_ms(), self.pulse_t0) / 1000
        if self.verbose:
            print(f'Stopped pulsing after {self.last_duration:0.1f} s')

    @micropython.native
    def stop_pulsing_graceful(self):
        # finish_current cycle and then stop
        self.graceful_stop = True

    @micropython.native
    def update(self):
        # check if pulsation should be activated
        now = ticks_ms()
        if self.pulse_active:  # is actively pulsing
            if self.board_pin.value:  # pin is high
                if ticks_less(self.pulse_dur, ticks_diff(now, self.last_t)):  # was on long enough
                    self.board_pin.value = False
                    self.last_t += self.pulse_dur  # set time for next pulse event
                    if self.graceful_stop:  # if stopping is set turn off pulsing
                        self.stop_pulsing_immediatly()
            else:  # pin is low
                if self.graceful_stop:  # if stopping is set turn off pulsing
                    self.stop_pulsing_immediatly()
                    return
                if ticks_less(self._off_dur, ticks_diff(now, self.last_t)):  # was off long enough
                    self.board_pin.value = True
                    self.nr_pulses_given += 1  # count up
                    self.last_t += self._off_dur

    def return_last_train(self) -> [dict, None]:
        if not self.pulse_active:
            return {'fps': self.fps, 'nr_pulses': self.nr_pulses_given, 'duration': self.last_duration}
        else:
            return None


class LEDpixel:
    """Class to control a single LED pixel on feather boards or similar
    if not pixel is available, the class will not do anything"""
    def __init__(self, blink_freq=2):
        try:
            import neopixel
            self.pixels = neopixel.NeoPixel(board.NEO, 1, auto_write=True)[0]
            self.pixel_available = True
        except:  # could not find pixel ignore
            self.pixel_available = False

        self.is_blinking = False
        self.blink_freq = blink_freq
        self.blink_duration = int(1000 / self.blink_freq / 2) # blink duration in ms for 50 % duty cycle
        self.last_t = 0

    def indicate_connected(self):
        """sets the brightness of the pixel to 1 and color to green to indicate connection"""
        if not self.pixel_available:
            return
        self.pixels.fill(GREEN)
        self.pixels.brightness = 1

    def indicate_recording(self):
        """starts blinking the pixel  with red color to indicate recording"""
        if not self.pixel_available:
            return
        self.pixels.fill(RED)
        self.pixels.brightness = 1
        self.is_blinking = True
        self.last_t = ticks_ms()

    def turn_off(self):
        """sets the brightness of the pixel to 0 to turn it off"""
        if not self.pixel_available:
            return
        self.pixels.brightness = 0
        self.is_blinking = False

    def update(self):
        """updates the pixel state, if it is blinking it will change the brightness of the pixel
         according to the blink_freq"""

        if self.is_blinking and self.pixel_available:
            if ticks_less(self.blink_duration, ticks_diff(ticks_ms(), self.last_t)):  # was on long enough
                if self.pixels.brightness:
                    self.pixels.brightness = 0  # turn off
                else:
                    self.pixels.brightness = 1  # turn on
                self.last_t += self.blink_duration  # set time for next pulse event

class Display:
    def __init__(self):
        import adafruit_character_lcd.character_lcd_i2c as character_lcd
        # Modify this if you have a different sized Character LCD
        lcd_columns = 16
        lcd_rows = 2

        # Initialise I2C bus.
        i2c = board.I2C()  # uses board.SCL and board.SDA
        # i2c = board.STEMMA_I2C()  # For using the built-in STEMMA QT connector on a microcontroller

        # Initialise the lcd class
        self.lcd = character_lcd.Character_LCD_I2C(i2c, lcd_columns, lcd_rows)

    def backlight_on(self):
        self.lcd.backlight = True

    def backlight_off(self):
        self.lcd.backlight = False

    def display_message(self, message):
        self.lcd.message = message

    def clear(self):
        self.lcd.clear()

    def blink_cursor(self):
        self.lcd.blink = True

    def no_cursor(self):
        self.lcd.blink = False


class USBSerialReader:
    """ Read a line from USB Serial (up to end_char), non-blocking, with optional echo """

    def __init__(self):
        self.s = ''
        self.serial = data_serial

    def check_serial(self) -> bool:
        return self.serial.connected

    def read(self, end_char='\n', echo=True):
        n = data_serial.in_waiting
        if n > 0:  # we got bytes!
            s = data_serial.read(n)  # actually read it in
            if echo:
                data_serial.write(s)
            self.s = self.s + s.decode('utf-8')  # keep building the string up
            pieces = self.s.split(end_char)
            if len(pieces) > 1:
                rstr = pieces[0]
                self.s = self.s[len(rstr) + 1:]  # reset str to beginning
                return rstr  # .strip()
        return None

    @staticmethod
    def send_to_host(message: (dict, str), message_type: str = None):
        """Sends data back to host computer"""
        if data_serial.connected:
            if isinstance(message, dict):
                assert message_type, 'Message type needs to be specified for a dictionary'
                message.update(**{'message_type': message_type})
                message = json.dumps(message) + '\n'
                data_serial.write(message.encode('utf-8'))
            elif isinstance(message, str):
                data_serial.write((message + "\n").encode("utf-8"))
        else:
            print('No serial connection established!!')

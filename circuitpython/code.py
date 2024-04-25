import random
import gc
import board
import busio
import digitalio
import json
import time
import supervisor
import usb_cdc
import audiobusio
import pwmio
from timing_utils import ticks_ms, ticks_diff, ticks_less
from machines import USBSerialReader, FPS_trigger, PIO_trigger, LEDpixel #Display

PULSE_ON = 5 # ms
COMMS_REFRESH = 100 # ms
GARBAGE_REFRESH = 5000 # ms

OUT_PIN = board.GP15

def main_loop():
    trigger_pin = digitalio.DigitalInOut(OUT_PIN)
    trigger_pin.direction = digitalio.Direction.OUTPUT
    trigger_pin.value = False
    trigger = FPS_trigger(trigger_pin, 'trigger', pulse_dur=PULSE_ON, fps=100, verbose=True)
    comms = USBSerialReader()
    comms_t = ticks_ms()
    garbage_t = ticks_ms()

    #display = Display()
    while True:
        trigger.update()
        if ticks_less(COMMS_REFRESH, ticks_diff(ticks_ms(), comms_t)):
            comms_t = ticks_ms()
            data = comms.read(echo=False)
            if data is not None:
                if data.startswith('Q'):  # stop pulsing
                    trigger.stop_pulsing_graceful()
                    continue
                elif data.startswith('S'):  # start pulsing
                    try:
                        fps = int(data.rstrip().split('S')[1])
                    except ValueError:
                        print('Invalid fps value')
                        continue
                    trigger.fps = fps
                    trigger.start_pulsing()
                    continue
                elif data.startswith('P'):  # respond to ping
                    comms.send_to_host('PONG')
                    continue

        if not trigger.pulse_active and ticks_less(GARBAGE_REFRESH, ticks_diff(ticks_ms(), garbage_t)):
            gc.collect()
            garbage_t = ticks_ms()


def main_loop_alternative():
    trigger = PIO_trigger(OUT_PIN, 'trigger_PIO', fps=100, verbose=True)
    comms = USBSerialReader()
    comms_t = ticks_ms()
    pixel = LEDpixel()
    garbage_t = ticks_ms()

    # display = Display()
    while True:
        trigger.update()
        pixel.update()
        if ticks_less(COMMS_REFRESH, ticks_diff(ticks_ms(), comms_t)):
            comms_t = ticks_ms()
            if not trigger.pulse_active:
                if comms.check_serial():
                    pixel.indicate_connected()
                else:
                    pixel.turn_off()
            data = comms.read(echo=False)
            if data is not None:
                if data.startswith('Q'):  # stop pulsing
                    trigger.stop_pulsing()
                    pixel.turn_off()
                    continue
                elif data.startswith('S'):  # start pulsing
                    try:
                        fps = int(data.rstrip().split('S')[1])
                    except ValueError:
                        print('Invalid fps value')
                        continue
                    trigger.fps = fps
                    if trigger.start_pulsing():
                        pixel.indicate_recording()

                    continue
                elif data.startswith('P'):  # respond to ping
                    comms.send_to_host('PONG')
                    continue

        if not trigger.pulse_active and ticks_less(GARBAGE_REFRESH, ticks_diff(ticks_ms(), garbage_t)):
            gc.collect()
            garbage_t = ticks_ms()

#main_loop()

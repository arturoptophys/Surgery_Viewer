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
from machines import USBSerialReader, FPS_trigger #Display

PULSE_ON = 5 # ms
COMMS_REFRESH = 100 # ms
GARBAGE_REFRESH = 5000 # ms

trigger_pin = digitalio.DigitalInOut(board.GP15)
trigger_pin.direction = digitalio.Direction.OUTPUT
trigger_pin.value = False


def main_loop():
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

    #update display
main_loop()

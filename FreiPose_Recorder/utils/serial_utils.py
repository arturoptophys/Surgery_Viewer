from PyQt6 import QtSerialPort
from PyQt6.QtCore import QObject, pyqtSignal, QIODevice, pyqtSlot
import logging

from FreiPose_Recorder.configs.params import MAX_FPS


class QtPicoSerial(QObject):
    """Class to manage a serial connection to a CircuitPython sketch using Qt
    QSerialPort object for data transport.  The data protocol is based on lines
    of text."""

    # class variable with Qt signal used to communicate between background thread and serial port thread
    _threadedWrite = pyqtSignal(bytes, name='threadedWrite')

    def __init__(self, main, comm=None):
        super(QtPicoSerial, self).__init__()
        self._portname = None
        self._buffer = b''
        self._port = None
        self.log = logging.getLogger('pico')
        # self.log.setLevel(logging.INFO)
        self.log.setLevel(logging.DEBUG)
        self.main = main
        self._fps = 30
        self.is_pulsing = False

    def is_open(self):
        return self._port is not None

    @staticmethod
    def available_ports():
        """Return a list of names of available serial ports."""
        return [port.portName() for port in QtSerialPort.QSerialPortInfo.availablePorts()]

    def set_port(self, name):
        self._portname = name

    def open(self):
        """Open the serial port and initialize communications.  If the port is already
        open, this will close it first.  If the current name is None, this will not open
        anything.  Returns True if the port is open, else False."""
        if self._port is not None:
            self.close()

        if self._portname is None:
            self.log.debug("No port name provided so not opening port.")
            return False
        # todo add open and close of the port using pyserial.. soe weird is happening on windoof
        self._port = QtSerialPort.QSerialPort()
        self._port.setBaudRate(115200)
        self._port.setPortName(self._portname)

        # open the serial port
        if self._port.open(QIODevice.OpenModeFlag.ReadWrite):
            self.log.info("Opened serial port %s", self._port.portName())
            # always process data as it becomes available
            self._port.readyRead.connect(self.read_input)

            # initialize the slot used to receive data from background threads
            self._threadedWrite.connect(self._data_send)
            self._port.clear(QtSerialPort.QSerialPort.Direction.AllDirections)  # Clear queues on connection
            return True

        else:
            # Error codes: https://doc.qt.io/qt-5/qserialport.html#SerialPortError-enum
            errcode = self._port.error()
            if errcode == QtSerialPort.QSerialPort.SerialPortError.PermissionError:
                self.log.warning(
                    "Failed to open serial port %s with a QSerialPort PermissionError, which could involve an already running control process, a stale lock file, or dialout group permissions.",
                    self._port.portName())
            else:
                self.log.warning("Failed to open serial port %s with a QSerialPort error code %d.",
                                 self._port.portName(), errcode)
            self._port = None
            return False

    def set_and_open_port(self, name):
        self.set_port(name)
        self.open()

    def close(self):
        """Shut down the serial connection to the Pico."""
        if self._port is not None:
            self.log.info("Closing serial port %s", self._port.portName())
            self._port.close()
            self._port = None
        return

    def write(self, data):
        if self._port is not None:
            res = self._port.write(data)
            self._port.flush()
            # self.log.debug(f"writen{res} to serial")
        else:
            self.log.error("Serial port not open during write.")

    @pyqtSlot(bytes)
    def _data_send(self, data):
        """Slot to receive serial data on the main thread."""
        self.write(data)

    def thread_safe_write(self, data):
        """Function to receive data to transmit from a background thread, then send it as a signal to a slot on the main thread."""
        self._threadedWrite.emit(data)

    def read_input(self):
        # Read as much input as available; callback from Qt event loop.
        data = self._port.readAll()
        if len(data) > 0:
            self.data_received(data)
        else:
            logging.debug("no data received")
        return

    def _parse_serial_input(self, data):
        # parse a single line of status input provided as a bytestring
        tokens = data.split()
        self.log.debug("Received serial data: %s", tokens)
        self.main.pico_data_received(data)

    def data_received(self, data):
        # Manage the possibility of partial reads by appending new data to any previously received partial line.
        # The data arrives as a PyQT5.QtCore.QByteArray.
        self._buffer += bytes(data)

        # Process all complete newline-terminated lines.
        while b'\n' in self._buffer:
            first, self._buffer = self._buffer.split(b'\n', 1)
            first = first.rstrip()
            self._parse_serial_input(first)

    def send(self, string):
        self.log.debug("Sending to serial port: %s", string)
        self.write(string.encode() + b'\n')

    def ping(self):
        self.send('P')

    def start_trigger(self):
        self.send(f'S{self.fps}')
        self.is_pulsing = True

    def stop_trigger(self):
        self.send(f'Q')
        self.is_pulsing = False

    @property
    def fps(self):
        return self._fps

    @fps.setter
    def fps(self, fps:int):
        fps = int(fps)
        if fps < 1 or fps > MAX_FPS:
            print('Invalid fps value', fps)
            return
        self._fps = fps
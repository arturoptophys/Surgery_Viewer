"""
Tool to record videos from multiple Basler cameras synchronously

Author: Artur artur.schneider@biologie.uni-freiburg.de

Planned features:
- device discovery
- connection to cameras
- grabbing of frames in free run mode
- setting autogain/auto exposure for each camera
- setting gain_exposuretime for each camera
- saving settings to file

"""

import json
import logging
import sys
import numpy as np
from queue import Queue, Empty
from threading import Event

from PyQt6.QtWidgets import QApplication, QMainWindow, QFileDialog
from PyQt6.QtCore import Qt, QTimer
from PyQt6 import uic, QtGui
import pyqtgraph as pg

from pathlib import Path
from datetime import datetime
from core.Recorder_my import Recorder

log = logging.getLogger('main')
log.setLevel(logging.DEBUG)

#logging.basicConfig(filename='GUI_run.log', filemode='w', format='%(asctime)s - %(levelname)s - %(message)s')

VERSION = "0.0.0"


class BASLER_GUI(QMainWindow):
    def __init__(self):
        super(BASLER_GUI, self).__init__()
        self.path2file = Path(__file__)
        uic.loadUi(self.path2file.parent / 'GUI' / 'GUI_design.ui', self)
        self.setWindowTitle('FreiPose Recorder v.%s' % VERSION)
        self.log = logging.getLogger('GUI')
        self.log.setLevel(logging.DEBUG)
        self.ConnectSignals()
        self.basler_recorder = Recorder()

        # list of gui elements for access via loops
        self.gain_spin_list = [self.Gain_spin_0, self.Gain_spin_1, self.Gain_spin_2, self.Gain_spin_3]
        self.exposure_spin_list = [self.ExposureTime_spin_0, self.ExposureTime_spin_1, self.ExposureTime_spin_2,
                                   self.ExposureTime_spin_3]


    ### Device Connectivity ####
    def scan_cams(self):
        found_cams = self.basler_recorder.get_cam_info()
        if len(found_cams) > 0:
            found_cams = '\n'.join(found_cams)
            self.Devices_textEdit.clear()
            self.Devices_textEdit.setText(f"Found cameras SN:\n{found_cams}")

            self.ConnectButton.setEnabled(True)
            self.ScanDevButton.setEnabled(False)
        else:
            self.Devices_textEdit.clear()
            self.Devices_textEdit.setText(f"Found no cameras !!")


    def connect_to_cams(self):
        self.basler_recorder.connect_cams()
        for item_id in range(self.CameraSettings.count()):
            self.CameraSettings.setItemEnabled(item_id, False)

        for c_id, cam in enumerate(self.basler_recorder.cam_array):
            self.CameraSettings.setItemText(c_id, cam.DeviceInfo.GetUserDefinedName())
            self.CameraSettings.setItemEnabled(c_id, True)

        self.RUNButton.setEnabled(True)
        self.RECButton.setEnabled(True)

    def run_cams(self):
        self.STOPButton.setEnabled(True)
        self.RUNButton.setEnabled(False)
        self.RECButton.setEnabled(False)
        self.ShowSingleCamButton.setEnabled(False)
        pass

    def start_recording(self):
        self.STOPButton.setEnabled(True)
        self.RUNButton.setEnabled(False)
        self.RECButton.setEnabled(False)
        self.ShowSingleCamButton.setEnabled(False)
        pass

    def stop_cams(self):
        self.stop_event.set()
        self.basler_recorder.single_view_queue.join()
        self.single_view_timer.stop()
        self.STOPButton.setEnabled(False)
        self.RUNButton.setEnabled(True)
        self.RECButton.setEnabled(True)
        self.ShowSingleCamButton.setEnabled(True)

    def show_single_cam(self):
        current_camid = self.get_current_tab()
        self.stop_event = Event()
        self.basler_recorder.fps = self.FrameRateSpin.value()
        self.basler_recorder.run_single_cam_show(current_camid, self.stop_event)
        self.single_view_timer = QTimer()
        self.single_view_timer.timeout.connect(self.update_single_view)
        self.single_view_timer.start(int(800 / self.FrameRateSpin.value()))  # dependign on frame rate ..
        self.STOPButton.setEnabled(True)
        self.RUNButton.setEnabled(False)
        self.RECButton.setEnabled(False)
        self.ShowSingleCamButton.setEnabled(False)

    def update_single_view(self):
        currentImg = self.basler_recorder.single_view_queue.get()
        self.ViewWidget.updateView(currentImg)

    #### SETTIGNS ###
    def save_settings(self):
        pass
    def load_settings(self):
        pass

    ## IMAGE CONTROL ####
    def get_current_tab(self) -> int:
        """Returns the ID of currently open tab"""
        return self.CameraSettings.currentIndex()

    # those functions are now blocking ? maybe make sure they r not ? create threads for actual adjustments ?
    def auto_expose(self):
        """Runs autoexposure routine for given/all camera"""
        if self.All_cams_checkBox.isChecked():
            for current_camid in range(len(self.basler_recorder.cam_array)):
                final_exp = self.basler_recorder.run_auto_exposure(current_camid)
                self.exposure_spin_list[current_camid].setValue(final_exp)
        else:
            current_camid = self.get_current_tab()
            final_exp = self.basler_recorder.run_auto_exposure(current_camid)
            self.exposure_spin_list[current_camid].setValue(final_exp)

    def auto_gain(self):
        """Runs autogain routine for given/all camera"""
        if self.All_cams_checkBox.isChecked():
            for current_camid in range(len(self.basler_recorder.cam_array)):
                final_gain = self.basler_recorder.run_auto_gain(current_camid)
                self.gain_spin_list[current_camid].setValue(final_gain)
        else:
            current_camid = self.get_current_tab()
            final_gain = self.basler_recorder.run_auto_gain(current_camid)
            self.gain_spin_list[current_camid].setValue(final_gain)

    def white_balance(self):
        """Runs auto white balance routine for given/all camera"""
        if self.All_cams_checkBox.isChecked():
            for current_camid in range(len(self.basler_recorder.cam_array)):
                self.basler_recorder.run_white_balance(current_camid)

        else:
            current_camid = self.get_current_tab()
            self.basler_recorder.run_white_balance(current_camid)

    def set_gain_exposure(self):
        """set the gain and exposure time for the current camera"""
        current_camid = self.get_current_tab()

    def flip_x(self):
        current_camid = self.get_current_tab()
        self.basler_recorder.flip_image_x(current_camid)

    def flip_y(self):
        current_camid = self.get_current_tab()
        self.basler_recorder.flip_image_y(current_camid)

    #### APP MAINTANCE #######
    def ConnectSignals(self):
        self.ScanDevButton.clicked.connect(self.scan_cams)
        self.ConnectButton.clicked.connect(self.connect_to_cams)
        self.RUNButton.clicked.connect(self.run_cams)
        self.RECButton.clicked.connect(self.start_recording)
        self.STOPButton.clicked.connect(self.stop_cams)

        self.SettingsSaveButton.clicked.connect(self.save_settings)
        self.SettingsLoadButton.clicked.connect(self.load_settings)

        self.AutoExposeButton.clicked.connect(self.auto_expose)
        self.AutoGainButton.clicked.connect(self.auto_gain)
        self.WhiteBalanceButton.clicked.connect(self.white_balance)
        self.FlipXButton.clicked.connect(self.flip_x)
        self.FlipYButton.clicked.connect(self.flip_y)

        self.ShowSingleCamButton.clicked.connect(self.show_single_cam)


    def app_is_exiting(self):
        # todo check if recording is running
        # close and realize cameras
        if self.basler_recorder.cam_array:  # close cameras if those were open
            self.basler_recorder.cam_array.Close()
        pass

    def closeEvent(self, event):
        self.log.info("Received window close event.")
        # todo add a check if recording is running ? prevent from closing ? or open dialog
        self.app_is_exiting()
        # self.disable_console_logging()
        super(BASLER_GUI, self).closeEvent(event)

def start_gui():
    app = QApplication([])
    win = BASLER_GUI()
    win.show()
    app.exec()


if __name__ == '__main__':
    logging.info('Starting via __main__')
    sys.exit(start_gui())
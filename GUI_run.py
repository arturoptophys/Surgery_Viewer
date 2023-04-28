"""
Tool to record videos from multiple Basler cameras synchronously

Author: Artur artur.schneider@biologie.uni-freiburg.de

Planned features:
- visualization of set of cameras
- save timestamps from taken frames

TODO
- fix queue bug of frame shuffling ?
- fix frames not filling the imageviews
- test recording speeds / loosing frames
- test hardware triggering
- implement visualization using HW_trig
"""

import json
import logging
import sys
import time

import numpy as np
from queue import Queue, Empty
from threading import Event, Thread

from PyQt6.QtWidgets import QApplication, QMainWindow, QFileDialog, QMessageBox
from PyQt6.QtCore import Qt, QTimer, QThread
from PyQt6 import uic, QtGui
import pyqtgraph as pg

from pathlib import Path
from datetime import datetime
from core.Recorder_my import Recorder
from ImageViewer import SingleCamViewer
from utils.StitchedImage import StitchedImage

log = logging.getLogger('main')
log.setLevel(logging.DEBUG)

# logging.basicConfig(filename='GUI_run.log', filemode='w', format='%(asctime)s - %(levelname)s - %(message)s')

VERSION = "0.0.0"


class BASLER_GUI(QMainWindow):
    def __init__(self):
        super(BASLER_GUI, self).__init__()
        self.single_camviewer = None
        self.multi_view_timer = None
        self.stop_event = None
        self.single_view_timer = None
        self.path2file = Path(__file__)
        uic.loadUi(self.path2file.parent / 'GUI' / 'GUI_design.ui', self)
        self.setWindowTitle('FreiPose Recorder v.%s' % VERSION)
        self.log = logging.getLogger('GUI')
        self.log.setLevel(logging.DEBUG)

        # list of gui elements for access via loops
        # todo create via loops...
        self.gain_spin_list = [self.Gain_spin_0, self.Gain_spin_1, self.Gain_spin_2, self.Gain_spin_3, self.Gain_spin_4,
                               self.Gain_spin_5]
        self.exposure_spin_list = [self.ExposureTime_spin_0, self.ExposureTime_spin_1, self.ExposureTime_spin_2,
                                   self.ExposureTime_spin_3, self.ExposureTime_spin_4, self.ExposureTime_spin_5]
        self.ViewWidget_list = [self.ViewWidget_1, self.ViewWidget_2, self.ViewWidget_3, self.ViewWidget_4,
                                self.ViewWidget_5, self.ViewWidget_6]
        self.ConnectSignals()
        self.basler_recorder = Recorder()
        self.scan_cams()

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

            self.exposure_spin_list[c_id].blockSignals(True)  # block triggering of events
            self.gain_spin_list[c_id].blockSignals(True)
            self.exposure_spin_list[c_id].setValue(self.basler_recorder.get_cam_exposureTime(cam))
            gain_limits, exp_limits = self.basler_recorder.get_cam_limits(cam)
            if exp_limits:
                self.exposure_spin_list[c_id].setMinimum(exp_limits[0])
                self.exposure_spin_list[c_id].setMaximum(exp_limits[1])
            if gain_limits:
                self.gain_spin_list[c_id].setMinimum(gain_limits[0])
                self.gain_spin_list[c_id].setMaximum(gain_limits[1])
            self.gain_spin_list[c_id].setValue(self.basler_recorder.get_cam_gain(cam))
            self.exposure_spin_list[c_id].blockSignals(False)
            self.gain_spin_list[c_id].blockSignals(False)

        self.CameraSettings.setCurrentIndex(0)
        self.RUNButton.setEnabled(True)
        self.RECButton.setEnabled(True)

    def run_cams(self):
        self.stop_event = Event()
        self.basler_recorder.fps = self.FrameRateSpin.value()
        self.number_cams = self.basler_recorder.cam_array.GetSize()
        self.basler_recorder.run_multi_cam_show(self.stop_event)

        self.multi_view_timer = QTimer()
        self.multi_view_timer.timeout.connect(self.update_multi_view)
        self.multi_view_timer.start(10)  # dependign on frame rate ..
        # self.singleview_thread = Thread(target = self.update_single_view)
        # self.singleview_thread.start()
        self.STOPButton.setEnabled(True)
        self.RUNButton.setEnabled(False)
        self.RECButton.setEnabled(False)
        self.ShowSingleCamButton.setEnabled(False)

    def update_multi_view(self):
        # todo.. call this from a thread ?
        try:
            t0 = time.monotonic()
            for c_id in range(self.number_cams):
                curr_image = self.basler_recorder.multi_view_queue[c_id].get_nowait()
                # TODO the assigment to queues doesnt seem to be consistent !
                self.ViewWidget_list[c_id].updateView(curr_image)
            # self.log.debug(f"Nr elements in q {self.basler_recorder.single_view_queue.qsize()}")
            # t0 = time.monotonic()
            # stitched_image = StitchedImage(image_list).image
            print(f'It took {(time.monotonic() - t0):0.3f} s to put all images up')
        except Empty:
            return
        self.statusbar.showMessage(f"In Q :{self.basler_recorder.multi_view_queue[0].qsize()}")
        # self.ViewWidget.updateView(currentImg)
        # self.ViewWidget.updateView(stitched_image)

    def update_multi_view_singlewindow(self):
        # todo.. call this from a thread ?
        try:
            image_list = []  # * self.number_cams
            for c_id in range(self.number_cams):
                image_list.append(self.basler_recorder.multi_view_queue[c_id].get_nowait())
            # self.log.debug(f"Nr elements in q {self.basler_recorder.single_view_queue.qsize()}")
            t0 = time.monotonic()
            stitched_image = StitchedImage(image_list).image
            print(f'It took {(time.monotonic() - t0):0.3f} s to stitch images')
        except Empty:
            return
        self.statusbar.showMessage(f"In Q :{self.basler_recorder.multi_view_queue[0].qsize()}")
        # self.ViewWidget.updateView(currentImg)
        self.ViewWidget.updateView(stitched_image)

    def start_recording(self):
        self.stop_event = Event()
        self.basler_recorder.fps = self.FrameRateSpin.value()
        self.number_cams = self.basler_recorder.cam_array.GetSize()
        self.basler_recorder.run_multi_cam_record(self.stop_event)

        self.multi_view_timer = QTimer()
        self.multi_view_timer.timeout.connect(self.update_multi_view)
        self.multi_view_timer.start(10)  # dependign on frame rate ..

        self.STOPButton.setEnabled(True)
        self.RUNButton.setEnabled(False)
        self.RECButton.setEnabled(False)
        self.ShowSingleCamButton.setEnabled(False)

        self.AutoExposeButton.setEnabled(False)
        self.AutoGainButton.setEnabled(False)
        self.WhiteBalanceButton.setEnabled(False)
        self.FlipXButton.setEnabled(False)
        self.FlipYButton.setEnabled(False)
        self.CameraSettings.setEnabled(False)
        self.All_cams_checkBox.setEnabled(False)
        self.SettingsSaveButton.setEnabled(False)
        self.SettingsLoadButton.setEnabled(False)
        self.FrameRateSpin.setEnabled(False)
        # todo Implement

    def stop_cams(self):
        if self.stop_event:
            self.stop_event.set()
        self.log.debug('Stopping grabbing')
        # self.basler_recorder.single_view_queue.join() # as this its not being emptied in a thread.. queue is not emptied but stucks here
        if self.single_view_timer:
            self.single_view_timer.stop()
            self.single_view_timer = None
            self.basler_recorder.stop_single_cam_show()

        if self.multi_view_timer:
            self.multi_view_timer.stop()
            self.multi_view_timer = None
            if self.basler_recorder.is_recording:
                self.basler_recorder.stop_multi_cam_record()
            else:
                self.basler_recorder.stop_multi_cam_show()

        if self.single_camviewer:
            if self.single_camviewer.isVisible():
                self.single_camviewer.close()

        # do i want to show remaining images ? not really..
        # maybe instead add an indicator of how many frames are in buffer ?
        self.STOPButton.setEnabled(False)
        self.RUNButton.setEnabled(True)
        self.RECButton.setEnabled(True)
        self.ShowSingleCamButton.setEnabled(True)

        self.AutoExposeButton.setEnabled(True)
        self.AutoGainButton.setEnabled(True)
        self.WhiteBalanceButton.setEnabled(True)
        self.FlipXButton.setEnabled(True)
        self.FlipYButton.setEnabled(True)
        self.CameraSettings.setEnabled(True)
        self.All_cams_checkBox.setEnabled(True)
        self.SettingsSaveButton.setEnabled(True)
        self.SettingsLoadButton.setEnabled(True)
        self.FrameRateSpin.setEnabled(True)

    def show_single_cam(self):
        self.All_cams_checkBox.setChecked(False)  # uncheck to not mess up with settings

        current_camid = self.get_current_tab()
        self.stop_event = Event()
        self.basler_recorder.fps = self.FrameRateSpin.value()
        self.basler_recorder.run_single_cam_show(current_camid, self.stop_event)

        self.single_camviewer = SingleCamViewer(self, self.basler_recorder.cam_array[
            current_camid].DeviceInfo.GetUserDefinedName())
        self.single_camviewer.show()

        self.single_view_timer = QTimer()
        self.single_view_timer.timeout.connect(self.update_single_view)
        self.single_view_timer.start(10)  # dependign on frame rate ..
        # self.singleview_thread = Thread(target = self.update_single_view)
        # self.singleview_thread.start()
        self.STOPButton.setEnabled(True)
        self.RUNButton.setEnabled(False)
        self.RECButton.setEnabled(False)
        self.ShowSingleCamButton.setEnabled(False)

    def update_single_view(self):
        # todo.. call this from a thread ?
        try:
            currentImg = self.basler_recorder.single_view_queue.get_nowait()
            # self.log.debug(f"Nr elements in q {self.basler_recorder.single_view_queue.qsize()}")
            self.statusbar.showMessage(f"In Q :{self.basler_recorder.single_view_queue.qsize()}")
        except Empty:
            return
        # self.ViewWidget.updateView(currentImg)
        self.single_camviewer.updateView(currentImg)

    #### SETTIGNS ###
    def save_settings(self):
        if not self.basler_recorder.cams_connected:
            self.log.info('Not connected to cameras cant save settings')

            QMessageBox.information(self,
                                    "Info",
                                    "Not connected to cameras, cant save settings",
                                    buttons=QMessageBox.StandardButton.Ok)

            # open message dialog !
            return
        # get active camera settings.. save those to json with cam name
        cam_lib = {}
        for cam in self.basler_recorder.cam_array:
            cam_settings = self.basler_recorder.get_cam_settings(cam)
            cam_lib.update(**cam_settings)

        # open file dialog for whre to save
        settings_file = QFileDialog.getSaveFileName(self, 'Save settings file', "",
                                                    "Settings files name (*.settings.json)")
        if settings_file[0]:
            with open(settings_file[0], 'w') as fi:
                json.dump(cam_lib, fi, indent=4)

    def load_settings(self, file=None):
        if not self.basler_recorder.cams_connected:
            self.log.info('Not connected to cameras cant save settings')

            QMessageBox.information(self,
                                    "Info",
                                    "Not connected to cameras, cant save settings",
                                    buttons=QMessageBox.StandardButton.Ok)
            return

        if file is None or not file:
            settings_file = QFileDialog.getOpenFileName(self, 'Open settings file', "",
                                                        "Settings files (*.settings.json)")
            if settings_file[0]:
                file = settings_file[0]
            else:
                return
            
        with open(file, 'r') as fi:
            cam_lib = json.load(fi)

        for cam in self.basler_recorder.cam_array:
            try:
                settings = cam_lib[cam.DeviceInfo.GetUserDefinedName()]
            except KeyError:
                self.log.info(f'No settings found for cam: {cam.DeviceInfo.GetUserDefinedName()} '
                              f'with SN: {cam.DeviceInfo.GetSerialNumber()}')
                continue
            self.basler_recorder.set_cam_settings(cam, settings)


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
        exp_time = self.exposure_spin_list[current_camid].value()
        gain = self.gain_spin_list[current_camid].value()
        self.basler_recorder.set_gain_exposure(current_camid, gain, exp_time)

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

        for spinbox in self.exposure_spin_list:
            spinbox.valueChanged.connect(self.set_gain_exposure)
        for spinbox in self.gain_spin_list:
            spinbox.valueChanged.connect(self.set_gain_exposure)

    def app_is_exiting(self):
        # check if recording is running stop if does.
        # close and realize cameras
        self.stop_cams()  # stop any grabbing still ongoing
        if self.basler_recorder.cam_array:  # close cameras if those were open
            self.basler_recorder.cam_array.Close()
        pass

    def closeEvent(self, event):
        self.log.info("Received window close event.")
        if self.basler_recorder.is_recording:
            self.log.warning('Recording still running. Not exiting')
            return
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

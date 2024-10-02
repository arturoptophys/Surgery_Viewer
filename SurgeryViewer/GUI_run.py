"""
Tool to view close ups from a Basler camera

Author: Artur artur.schneider@biologie.uni-freiburg.de
"""

import datetime
import json
import logging
import sys
import time
import shutil

from queue import Empty
from threading import Event

from PyQt6.QtWidgets import QApplication, QMainWindow, QFileDialog, QMessageBox
from PyQt6.QtCore import QTimer
from PyQt6 import uic, QtGui, QtCore

from pathlib import Path
from SurgeryViewer.core.Recorder import Recorder
from SurgeryViewer.configs.params import *


log = logging.getLogger('main')
log.setLevel(logging.DEBUG)

#make the logging to file
log_path = Path('logs')
log_path.mkdir(exist_ok=True)
if LOG2FILE:
    logging.basicConfig(filename=log_path / f'GUI_run{datetime.datetime.now().strftime("%m%d_%H%M")}.log', filemode='w',
                        format='%(asctime)s - %(levelname)s - %(message)s')

VERSION = "0.0.0"


class BASLER_GUI(QMainWindow):
    def __init__(self):
        super(BASLER_GUI, self).__init__()
        self.MultiViewWidget = None  # is loaded from the GUI_design.ui
        self.CameraSettings = None   # is loaded from the GUI_design.ui
        self.session_path = None  # path to the current session
        self.files_copied = False  # flag to check if files have been copied
        self.timer_update_counter = 0
        self.rec_start_time = None  # time when recording started
        self.session_id = "test_sess"
        self.multi_view_timer = None
        self.stop_event = None
        self.path2file = Path(__file__)
        uic.loadUi(self.path2file.parent / 'GUI' / 'GUI_design.ui', self)
        self.setWindowTitle(f'SurgeryViewer v.{VERSION}')
        self.log = logging.getLogger('GUI')
        self.log.setLevel(logging.DEBUG)

        self.Codec_comboBox.addItems(codec_to_try)

        #Setting icons for some buttons for prettiness
        self.RUNButton.setIcon(QtGui.QIcon("GUI/icons/play.svg"))
        self.RECButton.setIcon(QtGui.QIcon("GUI/icons/record.svg"))
        self.STOPButton.setIcon(QtGui.QIcon("GUI/icons/stop.svg"))
        self.ConnectButton.setIcon(QtGui.QIcon("GUI/icons/connect.svg"))
        self.Save_pathButton.setIcon(QtGui.QIcon("GUI/icons/folder.svg"))
        self.FlipXButton.setIcon(QtGui.QIcon("GUI/icons/ArrowsRightLeft.svg"))
        self.FlipYButton.setIcon(QtGui.QIcon("GUI/icons/ArrowsUpDown.svg"))
        self.Rec_status.setPixmap(QtGui.QIcon("GUI/icons/VideoCameraSlash.svg").pixmap(64))

        self.ConnectSignals()
        self.basler_recorder = Recorder(write_timestamps=SAVE_TIMESTAMPS)
        self.scan_cams()

    ### Device Connectivity ####
    def scan_cams(self):
        found_cams = self.basler_recorder.get_cam_info()
        nr_cams = len(found_cams)
        if nr_cams > 0:
            found_cams = '\n'.join(found_cams)
            self.Devices_textEdit.clear()
            self.Devices_textEdit.setText(f"Found cameras SN:\n{found_cams}")

            self.ConnectButton.setEnabled(True)
            self.ScanDevButton.setEnabled(False)  #Y only scan once ?

            self.connect_to_cams()
        else:
            self.Devices_textEdit.clear()
            self.Devices_textEdit.setText(f"Found no cameras !!\n (Re-)Connect a camera and try again.")

        self.MultiViewWidget.num_cameras = nr_cams
        self.CameraSettings.num_cameras = nr_cams

    def connect_to_cams(self):
        self.basler_recorder.connect_cams()

        for c_id, cam in enumerate(self.basler_recorder.cam_array):
            self.CameraSettings.toolbox.setItemText(c_id, cam.DeviceInfo.GetUserDefinedName())
            self.CameraSettings.exposure_spin_list[c_id].blockSignals(True)  # block triggering of events
            self.CameraSettings.gain_spin_list[c_id].blockSignals(True)
            self.CameraSettings.color_mode_list[c_id].blockSignals(True)
            self.CameraSettings.exposure_spin_list[c_id].setValue(self.basler_recorder.get_cam_exposureTime(cam))
            self.CameraSettings.gain_spin_list[c_id].setValue(self.basler_recorder.get_cam_gain(cam))
            gain_limits, exp_limits, colormodes = self.basler_recorder.get_cam_limits(cam)
            if exp_limits:
                self.CameraSettings.exposure_spin_list[c_id].setMinimum(exp_limits[0])
                self.CameraSettings.exposure_spin_list[c_id].setMaximum(exp_limits[1])
            if gain_limits:
                self.CameraSettings.gain_spin_list[c_id].setMinimum(gain_limits[0])
                self.CameraSettings.gain_spin_list[c_id].setMaximum(gain_limits[1])
            # add color modes to list
            self.CameraSettings.color_mode_list[c_id].clear()
            self.CameraSettings.color_mode_list[c_id].addItems(colormodes)
            self.CameraSettings.exposure_spin_list[c_id].blockSignals(False)  # unblock triggering of events
            self.CameraSettings.gain_spin_list[c_id].blockSignals(False)
            self.CameraSettings.color_mode_list[c_id].blockSignals(False)

        self.CameraSettings.toolbox.setCurrentIndex(0)
        self.RUNButton.setEnabled(True)
        self.RECButton.setEnabled(True)

        self.ConnectButton.setEnabled(False)

        # need to connect beforehand
        try:
            self.load_settings('default_settings.settings.json')
        except FileNotFoundError:
            try:
                self.load_settings('default.settings.json')
            except FileNotFoundError:
                self.log.warning('No default settings file found')



    def start_recording(self):
        self.files_copied = False
        self.stop_event = Event()
        session_id = self.SessionIDlineEdit.text()
        if session_id:
            self.session_id = session_id
        self.basler_recorder.fps = self.FrameRateSpin.value()
        self.basler_recorder.codec = self.Codec_comboBox.currentText()
        self.basler_recorder.crf = self.crf_spinBox.value()
        self.number_cams = self.basler_recorder.cam_array.GetSize()
        use_hw_trigger = False

        self.basler_recorder.run_multi_cam_record(self.stop_event, filename=self.session_id,
                                                  use_hw_trigger=use_hw_trigger)

        self.multi_view_timer = QTimer()
        self.multi_view_timer.timeout.connect(self.update_multi_view)
        self.multi_view_timer.start(5)  # dependign on frame rate ..

        self.STOPButton.setEnabled(True)
        self.RUNButton.setEnabled(False)
        self.RECButton.setEnabled(False)

        self.AutoExposeButton.setEnabled(False)
        self.AutoGainButton.setEnabled(False)
        self.WhiteBalanceButton.setEnabled(False)
        self.FlipXButton.setEnabled(False)
        self.FlipYButton.setEnabled(False)
        self.CameraSettings.toolbox.setEnabled(False)
        self.All_cams_checkBox.setEnabled(False)

        self.FrameRateSpin.setEnabled(False)
        self.Rec_status.setPixmap(QtGui.QIcon("GUI/icons/VideoCamera.svg").pixmap(64))
        # change the pixmap color to red
        self.Rec_status.setStyleSheet("background-color: rgb(255, 0, 0);")

        self.rec_start_time = time.monotonic()
        # create a time that executes the trigger after 500 ms delay to make sure cameras are ready



    def stop_cams(self):
        if self.stop_event:
            self.stop_event.set()
        self.log.debug('Stopping grabbing')


        if self.multi_view_timer:
            self.multi_view_timer.stop()
            self.multi_view_timer = None
            if self.basler_recorder.is_recording:
                self.basler_recorder.stop_multi_cam_record()
            else:
                self.basler_recorder.stop_multi_cam_show()


        self.statusbar.showMessage("Stopped Recording")
        # do i want to show remaining images ? not really..
        # maybe instead add an indicator of how many frames are in buffer ?
        self.STOPButton.setEnabled(False)
        self.Rec_status.setPixmap(QtGui.QIcon("GUI/icons/VideoCameraSlash.svg").pixmap(64))
        # change the pixmap color back to none
        self.Rec_status.setStyleSheet("background-color: none")
        self.RUNButton.setEnabled(True)
        self.RECButton.setEnabled(True)

        self.AutoExposeButton.setEnabled(True)
        self.AutoGainButton.setEnabled(True)
        self.WhiteBalanceButton.setEnabled(True)
        self.FlipXButton.setEnabled(True)
        self.FlipYButton.setEnabled(True)
        self.CameraSettings.toolbox.setEnabled(True)
        self.All_cams_checkBox.setEnabled(True)

        self.FrameRateSpin.setEnabled(True)

        for color_mode in self.CameraSettings.color_mode_list:
            color_mode.setEnabled(True)

    def show_multiple_cam(self):
        self.stop_event = Event()
        self.basler_recorder.fps = self.FrameRateSpin.value()
        self.number_cams = self.basler_recorder.cam_array.GetSize()
        use_hw_trigger = False
        self.basler_recorder.run_multi_cam_show(self.stop_event, use_hw_trigger)

        self.multi_view_timer = QTimer()
        self.multi_view_timer.timeout.connect(self.update_multi_view)
        self.multi_view_timer.start(int(1000 // (self.FrameRateSpin.value() * 1.2)))

        self.STOPButton.setEnabled(True)
        self.RUNButton.setEnabled(False)
        self.RECButton.setEnabled(False)
        self.FrameRateSpin.setEnabled(False)  # or implement on the go change of the framerate...
        self.Rec_status.setPixmap(QtGui.QIcon("GUI/icons/VideoCamera.svg").pixmap(64))
        # change the pixmap color to green
        self.Rec_status.setStyleSheet("background-color: rgb(0, 255, 0);")
        for color_mode in self.CameraSettings.color_mode_list:
            color_mode.setEnabled(False)

        self.rec_start_time = time.monotonic()
        # create a time that executes the trigger after 500 ms delay to make sure cameras are ready

    def update_multi_view(self):
        # call this from a thread ? or maybe not
        if self.basler_recorder.error_event.is_set():  # if an error occured
            self.log.error('Error in Basler recorder')
            self.stop_cams()
            return

        self.timer_update_counter += 1
        if self.timer_update_counter >= 20:
            self.update_rec_timer()  # dont call this too often ?
            self.timer_update_counter = 0
        try:
            for c_id in range(self.number_cams):
                curr_image = self.basler_recorder.multi_view_queue[c_id].get_nowait()
                self.MultiViewWidget.cam_viewers[c_id].updateView(curr_image)
        except Empty:
            return

        writerstatus = f"\tVideoWriter {self.basler_recorder.video_writer_list[0].get_state()}" if len(
            self.basler_recorder.video_writer_list) >= 1 else "not recording"

        display_string = ""
        for i in range(len(self.basler_recorder.multi_view_queue)):
            display_string += f"Q{i}: {self.basler_recorder.multi_view_queue[i].qsize()}"
        display_string += f"{writerstatus}"

        self.statusbar.showMessage(display_string)

        if not self.basler_recorder.is_recording and not self.basler_recorder.is_viewing:
            self.log.error('Basler recording stopped internally')

    def update_rec_timer(self):
        current_run_time = time.monotonic() - self.rec_start_time
        if current_run_time >= 60:
            self.recording_duration_label.setText(f"{(current_run_time // 60):.0f}m:{(current_run_time % 60):2.0f}s")
        else:
            self.recording_duration_label.setText(f"{current_run_time:.0f}s")

    #### SETTINGS ###
    def save_settings(self):
        """
        Save current camera settings to a json file
        """
        if not self.basler_recorder.cams_connected:
            self.log.info('Not connected to cameras cant save settings')

            QMessageBox.information(self,
                                    "Info",
                                    "Not connected to cameras, cant save settings",
                                    buttons=QMessageBox.StandardButton.Ok)
            return

        # get active camera settings.. save those to json with cam name
        cam_lib = {}
        for cam in self.basler_recorder.cam_array:
            cam_settings = self.basler_recorder.get_cam_settings(cam)
            cam_lib.update(**cam_settings)

        cam_lib.update(**{'save_path': self.basler_recorder.save_path, 'fps': self.FrameRateSpin.value(),
                          "HW_trigg": False, 'codec': self.Codec_comboBox.currentText(),
                          "crf": self.crf_spinBox.value()})

        # open file dialog for where to save
        settings_file = QFileDialog.getSaveFileName(self, 'Save settings file', "",
                                                    "Settings files name (*.settings.json)")
        if settings_file[0]:
            filename = settings_file[0]
            if len(filename.split(".")) < 2:
                filename += '.settings.json'
            with open(filename, 'w') as fi:
                json.dump(cam_lib, fi, indent=4)

    def load_settings(self, file: (str, Path, None) = None):
        """
        Load camera settings from a json file
        """
        if not self.basler_recorder.cams_connected:
            self.log.warning('Not connected to cameras cant load settings')

            QMessageBox.information(self,
                                    "Info",
                                    "Not connected to cameras, cant load settings",
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

        for c_id, cam in enumerate(self.basler_recorder.cam_array):
            try:
                settings = cam_lib[cam.DeviceInfo.GetUserDefinedName()]
            except KeyError:
                self.log.info(f'No settings found for cam: {cam.DeviceInfo.GetUserDefinedName()} '
                              f'with SN: {cam.DeviceInfo.GetSerialNumber()}')
                continue
            self.basler_recorder.set_cam_settings(cam, settings)
            self.CameraSettings.exposure_spin_list[c_id].blockSignals(True)
            self.CameraSettings.gain_spin_list[c_id].blockSignals(True)
            self.CameraSettings.color_mode_list[c_id].blockSignals(True)
            self.CameraSettings.exposure_spin_list[c_id].setValue(settings['exp_time'])
            self.CameraSettings.gain_spin_list[c_id].setValue(settings['gain'])
            self.CameraSettings.color_mode_list[c_id].setCurrentText(settings['color_mode'])
            self.CameraSettings.exposure_spin_list[c_id].blockSignals(False)
            self.CameraSettings.gain_spin_list[c_id].blockSignals(False)
            self.CameraSettings.color_mode_list[c_id].blockSignals(False)

        try:
            self.crf_spinBox.setValue(cam_lib['crf'])
            self.Codec_comboBox.setCurrentText(cam_lib['codec'])
            self.FrameRateSpin.setValue(cam_lib['fps'])
            self.set_save_path(cam_lib['save_path'])
            #self.basler_recorder.save_path = cam_lib['save_path']
        except KeyError:
            self.log.info('No-full general settings found in file')

    def set_save_path(self, save_path: (str, Path, None) = None):
        """
        Set the path where to save the recordings
        """
        if save_path is None or not save_path:
            save_path = QFileDialog.getExistingDirectory(self, "Select Directory where videos should be saved")
        if save_path:
            self.basler_recorder.save_path = save_path
            self.log.debug(f'Save path set to {save_path}')
            self.SavePath_label.setText(f'Save path:\n{save_path}')

    ## IMAGE CONTROL ####
    def get_current_tab(self) -> int:
        """Returns the ID of currently open tab"""
        return self.CameraSettings.toolbox.currentIndex()

    # those functions are now blocking ? maybe make sure they r not ? create threads for actual adjustments ?
    def auto_expose(self):
        """Runs autoexposure routine for given/all camera"""
        if self.All_cams_checkBox.isChecked():
            for current_camid in range(len(self.basler_recorder.cam_array)):
                final_exp = self.basler_recorder.run_auto_exposure(current_camid)
                # todo block triggerign of setting values !
                self.CameraSettings.exposure_spin_list[current_camid].setValue(final_exp)
        else:
            current_camid = self.get_current_tab()
            final_exp = self.basler_recorder.run_auto_exposure(current_camid)
            self.CameraSettings.exposure_spin_list[current_camid].setValue(final_exp)

    def auto_gain(self):
        """Runs autogain routine for given/all camera"""
        if self.All_cams_checkBox.isChecked():
            for current_camid in range(len(self.basler_recorder.cam_array)):
                final_gain = self.basler_recorder.run_auto_gain(current_camid)
                self.CameraSettings.gain_spin_list[current_camid].setValue(final_gain)
        else:
            current_camid = self.get_current_tab()
            final_gain = self.basler_recorder.run_auto_gain(current_camid)
            self.CameraSettings.gain_spin_list[current_camid].setValue(final_gain)

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
        exp_time = self.CameraSettings.exposure_spin_list[current_camid].value()
        gain = self.CameraSettings.gain_spin_list[current_camid].value()
        self.basler_recorder.set_gain_exposure(current_camid, gain, exp_time)

    def set_color_mode(self, color_mode: str):
        """set the colormode for the current camera, this is poorly used by ImageViewer.py"""
        current_camid = self.get_current_tab()
        self.basler_recorder.set_color_mode(current_camid, color_mode)
        # exp_time = self.CameraSettings.exposure_spin_list[current_camid]

    def flip_x(self):
        """
        Flip image on x axis
        """
        current_camid = self.get_current_tab()
        self.basler_recorder.flip_image_x(current_camid)

    def flip_y(self):
        """
        Flip image on y axis
        """
        current_camid = self.get_current_tab()
        self.basler_recorder.flip_image_y(current_camid)

    #### APP MAINTANCE #######
    def ConnectSignals(self):
        self.ScanDevButton.clicked.connect(self.scan_cams)
        self.ConnectButton.clicked.connect(self.connect_to_cams)
        self.RUNButton.clicked.connect(self.show_multiple_cam)
        self.RECButton.clicked.connect(self.start_recording)
        self.STOPButton.clicked.connect(self.stop_cams)
        self.AutoExposeButton.clicked.connect(self.auto_expose)
        self.AutoGainButton.clicked.connect(self.auto_gain)
        self.WhiteBalanceButton.clicked.connect(self.white_balance)
        self.FlipXButton.clicked.connect(self.flip_x)
        self.FlipYButton.clicked.connect(self.flip_y)
        self.Save_pathButton.clicked.connect(self.set_save_path)

        self.markerAddButton.clicked.connect(self.add_markers)
        self.markerClearButton.clicked.connect(self.clear_markers)
        self.GridButton.clicked.connect(self.toggle_grid)
        self.Grid_slider.valueChanged.connect(self.change_grid_size)

        self.ScreenshotButton.clicked.connect(self.take_screenshot)

    def take_screenshot(self):
        for viewer in self.MultiViewWidget.cam_viewers:
            image = viewer.image_view.getProcessedImage()
            view_box = viewer.image_view.getView()

            # Get the scene of the view box (which includes all the items)
            scene = view_box.scene()

            # Get the bounding rectangle of the view
            rect = view_box.sceneBoundingRect()

            # Create an image (QPixmap) of the appropriate size
            image = QtGui.QImage(int(rect.width()), int(rect.height()), QtGui.QImage.Format.Format_ARGB32)
            #image.fill(QtGui.QColor('white').rgba())  # Fill with white background

            # Create a QPainter to render the scene into the image
            painter = QtGui.QPainter(image)
            scene.render(painter, QtCore.QRectF(image.rect()), rect)
            painter.end()
            save_path = f'{self.session_id}{datetime.datetime.now().strftime("%Y%m%d_%H%M%S")}.png'
            image.save(save_path, "PNG")

    def add_markers(self):
        for viewer in self.MultiViewWidget.cam_viewers:
            viewer.add_markers_toggle = self.markerAddButton.isChecked()
        if self.markerAddButton.isChecked():
            self.markerAddButton.setText('Stop\nMarkers')
        else:
            self.markerAddButton.setText('Add\nMarkers')

    def clear_markers(self):
        for viewer in self.MultiViewWidget.cam_viewers:
            viewer.remove_markers()

    def toggle_grid(self):
        for viewer in self.MultiViewWidget.cam_viewers:
            viewer.toggle_grid_visibility()
        if self.GridButton.isChecked():
            self.GridButton.setText('Hide\nGrid')
        else:
            self.GridButton.setText('Show\nGrid')

    def change_grid_size(self,size):
        for viewer in self.MultiViewWidget.cam_viewers:
            viewer.update_grid_size(size)


    def app_is_exiting(self):
        """Routine to be run when the app is exiting, cleanup and release of resources"""
        # check if recording is running stop if does.
        self.stop_cams()  # stop any grabbing still ongoing
        self.basler_recorder.disconnect_cams()  # close and release cameras

    def closeEvent(self, event):
        """
        Overriden close event to make sure that all cameras are closed and all threads are stopped
        """
        self.log.info("Received window close event.")

        # If recording is still running, ask if user wants to abort
        if self.basler_recorder.is_recording:
            message_text = "Recording still running. Abort ?" if self.basler_recorder.is_recording \
                else "Remote mode is active. Abort ?"

            message = QMessageBox.information(self,
                                              "Really quit?",
                                              message_text,
                                              buttons=QMessageBox.StandardButton.No | QMessageBox.StandardButton.Yes)
            if message == QMessageBox.StandardButton.No or message == QMessageBox.StandardButton.Abort:
                event.ignore()
                return
            elif message == QMessageBox.StandardButton.Yes:
                self.log.info('Exiting')
        self.app_is_exiting()
        super(BASLER_GUI, self).closeEvent(event)


def start_gui():
    app = QApplication([])
    win = BASLER_GUI()
    win.show()
    app.exec()


if __name__ == '__main__':
    logging.info('Starting via __main__')
    sys.exit(start_gui())

import logging
from pathlib import Path
import pyqtgraph as pg
from pyqtgraph import ImageView, RawImageWidget, GraphicsView, ImageItem, GraphicsWidget, PlotWidget
from datetime import datetime
from PyQt6.QtWidgets import QWidget, QCheckBox, QLabel, QSpinBox, QHBoxLayout, QVBoxLayout, QDialog, QSizePolicy
from PyQt6 import uic, QtCore
import numpy as np

import cv2
import time

class ImageView_camera(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.image_view = ImageView(self)
        self.image_view.show()
        self.image_view.ui.histogram.hide()
        self.image_view.ui.menuBtn.hide()
        self.image_view.ui.roiBtn.hide()
        self.image_view.setImage(np.random.randint(0, 255, (128, 128), np.uint8))

        #self.image_view.autoRange()
        #self.image_view.ui.roiPlot.close()
        #self.layout = QVBoxLayout(self)
        #self.layout.addWidget(self.image_view)

        #self.image_view = RawImageWidget(self, scaled=True)
        #self.image_view.show()
        #self.setSizePolicy(QSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Maximum))

        #self.plot_widget = PlotWidget(self)
        #self.plot_widget.setRange(QtCore.QRectF(0, 0, 1024, 1024))
        #imagedata = np.random.random((256, 256))
        #self.image_view = ImageItem()
        #self.plot_widget.addItem(self.image_view)
        #self.plot_widget.hideAxis('left')
        #self.plot_widget.hideAxis('bottom')

    def updateView(self, img):
        self.image_view.setImage(img.T)


class SingleCamViewer(QDialog):
    def __init__(self, parent, cam_name):
        super(SingleCamViewer, self).__init__(parent)
        self.path2file = Path(__file__)
        uic.loadUi(self.path2file.parent / 'GUI' / 'SingleCameraView.ui', self)
        self.setWindowTitle(f"CamViewer {cam_name}")
        self.log = logging.getLogger('CamViewer')
        self.log.setLevel(logging.DEBUG)
        self.parent = parent
        self.ConnectSignals()

        self.is_showing = True

    def ConnectSignals(self):
        self.STOPButton.clicked.connect(self.stop_viewing)

        self.AutoExposeButton.clicked.connect(self.auto_expose)
        self.AutoGainButton.clicked.connect(self.auto_gain)
        self.WhiteBalanceButton.clicked.connect(self.white_balance)
        self.FlipXButton.clicked.connect(self.flip_x)
        self.FlipYButton.clicked.connect(self.flip_y)

    def updateView(self, img):
        self.CamViewer.updateView(img)
        if self.FocusCheckBox.isChecked():
            t0 = time.monotonic()
            self.calculate_blur(img)
            print(f'Blur value calculation with sciimage took {(time.monotonic()-t0):0.4f}')

    def calculate_blur(self, img):
        # to do only in a roi ?
        #blur_strength = int(100 - blur_effect(img) * 100)
        # TODO this need normalization
        # get first value and save it, then normalize values according to this one to be larger or smaller then 50
        blur_strength = cv2.Laplacian(img, cv2.CV_16S, 5).var()
        self.progressBar.setValue(blur_strength)

    def stop_viewing(self):
        self.log.debug('Indicating to main to stop grabbing')
        self.is_showing = False
        self.parent.stop_cams()
    def auto_expose(self):
        self.parent.auto_expose()
    def auto_gain(self):
        self.parent.auto_gain()
    def white_balance(self):
        self.parent.white_balance()
    def flip_x(self):
        self.parent.flip_x()
    def flip_y(self):
        self.parent.flip_y()

    def app_is_exiting(self):
        """routine to call for stop if window is closed"""
        self.stop_viewing()

    def closeEvent(self, event):
        if self.is_showing:
            self.log.debug("Received window close event.")
            self.app_is_exiting()
            super(SingleCamViewer, self).closeEvent(event)
        else:
            self.log.debug("Closed by parent")

#email rumschicken
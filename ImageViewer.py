import pyqtgraph as pg
from pyqtgraph import ImageView
from datetime import datetime
from PyQt6.QtWidgets import QWidget, QCheckBox, QLabel, QSpinBox, QHBoxLayout, QVBoxLayout


class ImageView_camera(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.image_view = ImageView()
        #self.layout = QVBoxLayout(self)
        #self.layout.addWidget(self.image_view)
        self.image_view.show()

    def updateView(self, img):
        self.image_view.setImage(img)
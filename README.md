# SurgeryViewer 
Based fork of https://github.com/Optophys-Lab/FreiPose_Recorder

It allows to view/record video from a camera rig using Basler cameras.
It includes a GUI for visualization of video stream as well as changing camera settings.
PyQTgraph - toolbox allows to mark certain points in the view, visualize a grid, and pan/zoom the view.



## Installation guide
Select and install suitable release of Pylon's libraries from:
    <https://www.baslerweb.com/de/downloads/downloads-software/#type=pylonsoftware>

(Optional) Create and activate a conda environment

    conda env create -n SurViewer python=3.11
    conda activate SurViewer

Install the following python packages (preferably in a virtual environment):

    git clone https://github.com/arturoptophys/Surgery_Viewer.git
    cd Surgery_Viewer
    pip install -e .

To Run the GUI from the commandline:

    #make sure conda env is activated
    #make sure $CWD is Surgery_Viewer
    python GUI_run.py


## User guide
### Camera names (optional)
To more easily identify your cameras you can give them custom names.

After first connection to the camera, the serial number is 
saved in the _cameras.json_ top level file.
This file is used to load the camera id on subsequent runs. It's a jsonized ditionary with SN as key and camera name and 
context as value. Context is an int which is used to identify the frames from each camera. Its being hashed from camera 
name to prevent duplicates.

After first connection to the camera you can modify _cameras.json_ to give your cameras unique names.

### general config
Can be found in _configs/params.py_ file. It contains the following fields:

TODO 

### Camera settings
Camera settings are loaded from the _default.settings.json_ file. Upon connection to the camera, the settings are loaded,
if this file is not available dialog asks for any other settings files.

_default.settings.json_ is an jsonized dictionary containing parameters for each camera (_exposure time_, _gain_, _colormode_,
_white balance_ values) and further general settings, such as _save path_ for videos, preferred _fps_(recording and play fps 
for free-running mode and only play fps for trigger mode, there the recording fps is dictated by the trigger frequency),
_codec_ used for video encoding, _crf_ defining the compression level(higher value - higher compression).




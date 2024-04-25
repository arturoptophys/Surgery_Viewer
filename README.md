# FreiPose_Recorder 
Based on RecordTool by Christian https://github.com/lmb-freiburg/RecordTool

It allows to record synchronous video from a multi camera rig using Basler cameras and an Arduino or MCC-DAQ for trigger generation.
It includes a GUI for visualization of video streams as well as changing camera settings.
GUI can be used in remote mode and be controlled via TCP/IP.

read the docs <https://optophys-lab.github.io/FreiPose_Recorder/>

## Installation guide
Select and install suitable release of Pylon's libraries from:
    <https://www.baslerweb.com/de/downloads/downloads-software/#type=pylonsoftware>

(Optional) Create and activate a conda environment

    conda env create -n Recorder_env python=3.9
    conda activate Recorder_env

Install the following python packages (preferably in a virtual environment):

    git clone https://github.com/Optophys-Lab/FreiPose_Recorder.git
    cd FreiPose_Recorder
    pip install -e .

To Run the GUI from the commandline:

    #make sure conda env is activated
    #make sure $CWD is FreiPose_Recorder
    python GUI_run.py


## User guide
### Camera names (optional)
To more easily identify your cameras you can give them custom names.

Cameras do not have to be manually added to the enums anymore. After first connection to the camera, the serial number is 
saved in the _cameras.json_ top level file.
This file is used to load the cameras on subsequent runs. Its a jsonized ditionary with SN as key and camera name and 
context as value. Context is an int which is used to identify the frames from each camera. Its being hashed from camera 
name to prevent duplicates.

After first connection to the camera you can modify _cameras.json_ to give your cameras unique names.

### general config
Can be found in _configs/params.py_ file. It contains the following fields:

- `ENABLE_REMOTE` Boolean to enable remote connection to control GUI via network. Set to False if not using this feature
- `USE_ARDUINO_TRIGGER` Boolean to use python board as trigger, requires serial connection to the board
- `CALIB_DURATION` duration of the calibration in ms
- `CALIB_WAIT`  waiting time before the calibration starts in ms
- `SAVE_TIMESTAMPS` Boolean to save the timestamps of the frames
- `TRIGGER_LINE_IN` Input-line on the GPIO cable for the camera for the trigger signal
- `MAX_FPS`  maximum fps for the camera
- `LOG2FILE` Boolean to log to a file
- `CONVERT2` Mono8 or RGB8 Colorformat for conversion

### Camera settings
Camera settings are loaded from the _default.settings.json_ file. Upon connection to the camera, the settings are loaded,
if this file is not available dialog asks for any other settings files.

_default.settings.json_ is an jsonized dictionary containing parameters for each camera (_exposure time_, _gain_, _colormode_,
_white balance_ values) and further general settings, such as _save path_ for videos, preferred _fps_(recording and play fps 
for free-running mode and only play fps for trigger mode, there the recording fps is dictated by the trigger frequency),
_codec_ used for video encoding, _crf_ defining the compression level(higher value - higher compression), and boolean 
to use _HW-triggermode_.





### Start the RecordTool
from activated environment run:

    python GUI_run.py    


Default settings to be loaded upon connection should be saved as FreiPose_Recorder/default_settings.settings.json
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

Add your cameras to configs.camera_enum.py. This gives your cameras unique names.

    #edit FreiPose_Recorder/configs/camera_enums.py
    #add the serial number of your cams and a name e.g. cam42 = '22561089'


Start the RecordTool
    
    python GUI_run.py    


Convert recorded videos to single frames

    python vid2frames.py recordings/take00/run000_cam5.avi --out-path ./recordings_frames/


Default settings to be loaded upon connection should be saved as FreiPose_Recorder/default_settings.settings.json
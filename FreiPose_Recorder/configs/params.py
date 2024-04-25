ENABLE_REMOTE = False  # Boolean to enable remote connection to control GUI via network
HOST = "10.4.26.118"  # if connecting to remote, use the IP of the current machine
PORT = 8881  # port for the remote connection
USE_ARDUINO_TRIGGER = False     # Boolean to enable the arduino trigger NOT IMPLEMENTED
CALIB_DURATION = 30000  # duration of the calibration in ms
CALIB_WAIT = 10000  # waiting time before the calibration starts in ms
SAVE_TIMESTAMPS = False     # Boolean to save the timestamps of the frames
TIME_STAMP_STRING = '%Y%m%d_%H%M%S'  # time format for the videos
VIDEO_FOLDER = "behav_vid"  # folder for the videos
TRIGGER_LINE_IN = "Line3"   # Input-line on the GPIO cable for the camera for the trigger signal
TRIGGER_LINE_OUT = "Line1"  # Outputline for the camera
MAX_FPS = 150    # maximum fps for the camera
codec_to_try = ["h264_nvenc", "libx264", "mpeg4", "mpeg2video", "libxvid", "libx264rgb"]
LOG2FILE = True  # Boolean to log to a file
CONVERT2 = 'RGB8' # Mono8 or RGB8 Colorformat for conversion
import logging, random
import os
import threading
# import cv2
import time
import datetime
import numpy as np
from collections import defaultdict
from threading import Event, Thread
from queue import Queue, Full

from pypylon import genicam
from pypylon import pylon

# from utils.general_util import my_mkdir
# from utils.VideoWriterFast import VideoWriterFast
# from utils.StitchedImage import StitchedImage

from config.camera_enums import CameraIdentificationSN


# Another way to get warnings when images are missing ... not used
class MyImageEventHandler(pylon.ImageEventHandler):
    def OnImagesSkipped(self, camera, countOfSkippedImages):
        print(f"Camera{camera} skipped {countOfSkippedImages} frames")


NUM_CAMERAS = 4  # simulated cameras
# setup demo environment with 10 cameras
os.environ["PYLON_CAMEMU"] = f"{NUM_CAMERAS}"


def rel_close(v, max_v, thresh=5.0):
    v_scaled = v / max_v * 100.0
    if 100.0 - v_scaled < thresh:
        return True
    return False


class Recorder(object):
    def __init__(self, verbosity=0):
        self.stop_event = None
        self.current_cam = None
        self.single_view_thread = None
        self.single_view_queue = None
        self.cams_connected = False
        self.cam_array = None
        self._verbosity = verbosity

        # self._camera_info = get_camera_infos()
        self._camera_list = list()
        self._camera_names_list = list()

        # self._take_name = 'take'
        self._rid = 0
        self.fps = 10
        self._trigger = None
        self.grab_timeout = 1000  #in ms

        self.log = logging.getLogger('BaslerRecorder')
        self.log.setLevel(logging.DEBUG)

    @property
    def fps(self):
        return self.__fps

    @fps.setter
    def fps(self, fps_new):
        if fps_new < 1:
            self.__fps = 1
        elif fps_new > 100:
            self.__fps = 100  # todo make parameters
        else:
            self.__fps = fps_new

    def get_cam_info(self) -> list:
        self.scan_cams()
        sns = list()
        for idx, cam in enumerate(self.cam_array):
            sns.append(cam.DeviceInfo.GetSerialNumber())
        return sns

    def scan_cams(self):
        """ Searches for attached Basler cams and puts them into our list of cameras. """
        # reset cams
        self._camera_list, self._camera_names_list = list(), list()

        # Get the transport layer factory.
        tlFactory = pylon.TlFactory.GetInstance()

        devices = tlFactory.EnumerateDevices()
        if len(devices) == 0:
            self.log.info('No cameras present')
            return

        self.log.debug(f'Found {len(devices)} cameras')

        self.cam_array = pylon.InstantCameraArray(len(devices))

        for idx, cam in enumerate(self.cam_array):
            cam.Attach(tlFactory.CreateDevice(devices[idx]))
            sn = cam.DeviceInfo.GetSerialNumber()
            try:
                CameraIdentificationSN(sn)
            except ValueError:
                self.log.info(f'Connected camera {sn} not found in Enum')
            # todo make an identinfication table to associate a camera with a defined name !

    def connect_cams(self):
        self.cam_array.Open()
        for idx, cam in enumerate(self.cam_array):
            camera_serial = cam.DeviceInfo.GetSerialNumber()
            try:
                self.log.debug(
                    f"set context {CameraIdentificationSN(camera_serial).context} for camera {camera_serial}")
                cam.SetCameraContext(CameraIdentificationSN(camera_serial).context)
                cam.DeviceInfo.SetUserDefinedName(CameraIdentificationSN(camera_serial).name)
            except ValueError:
                r_int = random.randint(10, 256)
                cam.SetCameraContext(r_int)  # for unknown cameras set random context
                cam.DeviceInfo.SetUserDefinedName(f"cam{r_int}")
        self.cams_connected = True
        self.log.debug(f'Connected to {self.cam_array.GetSize()} cameras')

    def disconnect_cams(self):
        # todo add a check if recording is running ?
        self.cam_array.Close()
        self.cams_connected = False

    def _config_cams_continuous(self, cam):
        # cam.RegisterImageEventHandler(MyImageEventHandler(),
        #                               pylon.RegistrationMode_Append,
        #                               pylon.Cleanup_Delete)

        if not cam.IsOpen():
            cam.Open()

        # some things are to be set as attributes ...
        try:
            cam.AcquisitionFrameRate = self.fps  # here we go to max fps in order to not be limited
        except genicam.LogicalErrorException:
            cam.AcquisitionFrameRateAbs = self.fps

        cam.AcquisitionFrameRateEnable = True

        cam.MaxNumBuffer.SetValue(16)  # how many buffers there are in total (empty and full)
        cam.OutputQueueSize.SetValue(
            8)  # maximal number of filled buffers (if another image is retrieved it replaces an old one and is called skipped)

        cam.AcquisitionMode = 'Continuous'
        # TODO add other options for color cameras !
        # nodemap.GetNode("PixelFormat").FromString("BGR8")
        # cam.DemosaicingMode.SetValue('BaslerPGI')
        cam.PixelFormat = 'Mono8'
        cam.TriggerMode = 'Off'

    def _config_cams_hw_trigger(self, cam):
        # cam.RegisterImageEventHandler(MyImageEventHandler(),
        #                               pylon.RegistrationMode_Append,
        #                               pylon.Cleanup_Delete)
        if not cam.IsOpen():
            cam.Open()
        try:
            cam.AcquisitionFrameRate = 200  # here we go to max fps in order to not be limited
        except genicam.LogicalErrorException:
            cam.AcquisitionFrameRateAbs = 200
        cam.AcquisitionFrameRateEnable = True
        # behavior wrt to these values is a bit strange to me. Important seems to be to use LastImages Strategy and make MaxNumBuffers larger than OutputQueueSize. Otherwise its not guaranteed to work
        cam.MaxNumBuffer.SetValue(16)  # how many buffers there are in total (empty and full)
        cam.OutputQueueSize.SetValue(
            8)  # maximal number of filled buffers (if another image is retrieved it replaces an old one and is called skipped)

        cam.AcquisitionMode = 'Continuous'
        # TODO add other options for color cameras !
        # nodemap.GetNode("PixelFormat").FromString("BGR8")
        # cam.DemosaicingMode.SetValue('BaslerPGI')
        cam.PixelFormat = 'Mono8'

        cam.LineSelector = "Line3"
        cam.LineMode = "Input"

        cam.TriggerSelector = "FrameStart"
        cam.TriggerSource = "Line3"
        cam.TriggerMode = "On"
        cam.TriggerActivation = 'RisingEdge'

    def is_color_cam(self, cam):
        # get available formats
        available_formats = cam.PixelFormat.Symbolics

        # figure out if a color format is available
        if 'BGR8Packed' in available_formats:
            return True
        return False

    def set_gain_exposure(self, cam_id: int, gain: float, exposure: float):
        """ Set values from GUI"""
        was_closed = False
        cam = self.cam_array[cam_id]
        if not cam.IsOpen():
            was_closed = True
            cam.Open()
        cam.Gain.SetValue(gain)
        cam.ExposureTime.SetValue(exposure)
        if was_closed:
            cam.Close()

    def run_white_balance(self, cam_id: int):
        """Set auto white balance for color cameras"""
        was_closed = False
        cam = self.cam_array[cam_id]
        if not cam.IsOpen():
            was_closed = True
            cam.Open()
        self.log.info(f"Setting white balance for {CameraIdentificationSN(cam.DeviceInfo.GetSerialNumber()).name} "
                      f"{cam.GetDeviceInfo().GetSerialNumber()}")

        if not self.is_color_cam(cam):
            self.log.info(f"{CameraIdentificationSN(cam.DeviceInfo.GetSerialNumber()).name} is not a color cam\n"
                          f"Skipping white balancing")
            return

        cam.AutoFunctionROISelector.SetValue('ROI1')
        cam.AutoFunctionROIUseWhiteBalance.SetValue(False)
        cam.AutoFunctionROISelector.SetValue('ROI2')
        cam.AutoFunctionROIUseWhiteBalance.SetValue(True)

        # define ROI to use
        cam.AutoFunctionROISelector.SetValue('ROI2')
        cam.AutoFunctionROIWidth.SetValue(cam.Width.GetValue())
        cam.AutoFunctionROIHeight.SetValue(cam.Height.GetValue())
        cam.AutoFunctionROIOffsetX.SetValue(0)
        cam.AutoFunctionROIOffsetY.SetValue(0)

        # get initial values
        if self._verbosity > 1:
            print('Initial balance ratio:', end='\t')
            cam.BalanceRatioSelector.SetValue('Red')
            print('Red= ', cam.BalanceRatio.GetValue(), end='\t')
            cam.BalanceRatioSelector.SetValue('Green')
            print('Green= ', cam.BalanceRatio.GetValue(), end='\t')
            cam.BalanceRatioSelector.SetValue('Blue')
            print('Blue= ', cam.BalanceRatio.GetValue())

        cam.BalanceWhiteAuto.SetValue('Once')

        i = 0
        while not cam.BalanceWhiteAuto.GetValue() == 'Off':
            cam.GrabOne(5000)
            i += 1

            if i > 100:
                self.log.error('Auto White balance was not successful')
                break

        # get final values
        if self._verbosity > 1:
            print('Final balance ratio:', end='\t')
            cam.BalanceRatioSelector.SetValue('Red')
            print('Red= ', cam.BalanceRatio.GetValue(), end='\t')
            cam.BalanceRatioSelector.SetValue('Green')
            print('Green= ', cam.BalanceRatio.GetValue(), end='\t')
            cam.BalanceRatioSelector.SetValue('Blue')
            print('Blue= ', cam.BalanceRatio.GetValue())

        if was_closed:
            cam.Close()


    def run_auto_exposure(self, cam_id: int) -> float:
        """ Adjust exposure time while keeping gain fixed. """
        was_closed = False
        cam = self.cam_array[cam_id]
        if not cam.IsOpen():
            was_closed = True
            cam.Open()

        self.log.info(f"Setting auto exposure for {CameraIdentificationSN(cam.GetDeviceInfo().GetSerialNumber()).name} "
                      f"{cam.GetDeviceInfo().GetSerialNumber()}")

        cam.AutoFunctionROISelector.SetValue('ROI1')
        cam.AutoFunctionROIUseBrightness.SetValue(True)
        cam.AutoFunctionROISelector.SetValue('ROI2')
        cam.AutoFunctionROIUseBrightness.SetValue(False)

        # define ROI to use
        cam.AutoFunctionROISelector.SetValue('ROI1')
        wOff = int(cam.Width.GetValue() / 4)
        hOff = int(cam.Height.GetValue() / 4)
        wSize = int(cam.Width.GetValue() / 2)
        hSize = int(cam.Height.GetValue() / 2)

        # Enforce size is a multiple of two (important because of bayer pattern)
        wSize = int(wSize / 2) * 2
        hSize = int(hSize / 2) * 2

        # set ROI
        cam.AutoFunctionROIWidth.SetValue(wSize)
        cam.AutoFunctionROIHeight.SetValue(hSize)
        cam.AutoFunctionROIOffsetX.SetValue(wOff)
        cam.AutoFunctionROIOffsetY.SetValue(hOff)

        # 0.3 means that the target brightness is 30 % of the maximum brightness
        # of the raw pixel value read out from the sensor.
        cam.AutoTargetBrightness.SetValue(0.2)

        # give auto some bounds
        cam.AutoExposureTimeLowerLimit.SetValue(cam.AutoExposureTimeLowerLimit.GetMin())
        cam.AutoExposureTimeUpperLimit.SetValue(cam.AutoExposureTimeUpperLimit.GetMax())

        # set gain to its reference value
        # TODO set some gain value ?
        cam.ExposureAuto.SetValue('Once')

        i = 0
        while not cam.ExposureAuto.GetValue() == 'Off':
            cam.GrabOne(5000)
            i += 1

            if i > 100:
                self.log.error('Auto Exposure was not successful')
                break

        self.log.debug(f'Final exposure after {i} images {cam.ExposureTimeAbs.GetValue():d} us in range '
                       f'{cam.AutoExposureTimeLowerLimit.GetMin()}-{cam.AutoExposureTimeUpperLimit.GetMax()}')

        # check if we should give warnings
        if rel_close(cam.ExposureTimeAbs.GetValue(), cam.AutoExposureTimeUpperLimit.GetMax()):
            self.log.warning('Final exposure value is very close to its maximum value:'
                             'Consider increasing gain, opening camera shutter wider or put more light.')

        if was_closed:
            cam.Close()
        return cam.ExposureTimeAbs.GetValue()

    def run_auto_gain(self, cam_id) -> float:
        # check if this can be run while visualization is running ?
        # do a check if grabbing is already grabbing ?
        # if so just wait until th flag gets reset ?
        """ Adjust gain while keeping exposure time fixed.
        returns resulting gain
        """
        was_closed = False
        cam = self.cam_array[cam_id]
        if not cam.IsOpen():
            was_closed = True
            cam.Open()
        self.log.info(f"Setting auto gain for {CameraIdentificationSN(cam.GetDeviceInfo().GetSerialNumber()).name} "
                      f"{cam.GetDeviceInfo().GetSerialNumber()}")


        #no clue whether those are needed / or work
        
        cam.AutoFunctionROISelector.SetValue('ROI1')
        cam.AutoFunctionROIUseBrightness.SetValue(True)
        cam.AutoFunctionROISelector.SetValue('ROI2')
        cam.AutoFunctionROIUseBrightness.SetValue(False)

        # define ROI to use
        cam.AutoFunctionROISelector.SetValue('ROI1')
        wOff = int(cam.Width.GetValue() / 4)
        hOff = int(cam.Height.GetValue() / 4)
        wSize = int(cam.Width.GetValue() / 2)
        hSize = int(cam.Height.GetValue() / 2)

        # Enforce size is a multiple of two (important because of bayer pattern)
        wSize = int(wSize/2)*2
        hSize = int(hSize/2)*2

        # set ROI
        cam.AutoFunctionROIWidth.SetValue(wSize)
        cam.AutoFunctionROIHeight.SetValue(hSize)
        cam.AutoFunctionROIOffsetX.SetValue(wOff)
        cam.AutoFunctionROIOffsetY.SetValue(hOff)

        # 0.3 means that the target brightness is 30 % of the maximum brightness
        # of the raw pixel value read out from the sensor.
        cam.AutoTargetBrightness.SetValue(0.2)

        # give auto some bounds
        cam.AutoGainLowerLimit.SetValue(cam.Gain.GetMin())
        cam.AutoGainUpperLimit.SetValue(cam.Gain.GetMax())

        # set exposure to its reference value
        # cam.ExposureTime.SetValue(0)
        # todo set some exposure value ?
        # print('Initial gain', cam.Gain.GetValue())
        cam.GainAuto.SetValue('Once')
        i = 0
        while not cam.GainAuto.GetValue() == 'Off':
            cam.GrabOne(5000)
            #instead of grabing just waiting if cama is already grabbing ?
            i += 1

            if i > 100:
                self.log.error('Auto Gain was not successful')
                break

        self.log.debug(f'Final gain after {i} images {cam.Gain.GetValue():0.1f} in range {cam.Gain.GetMin()}'
                       f'-{cam.Gain.GetMax()}')

        # check if we should give warnings
        if rel_close(cam.Gain.GetValue(), cam.Gain.GetMax()):
            self.log.warning('Final gain value is very close to its maximum value:'
                             ' Consider increasing exposure time, opening camera shutter wider or put more light.')

        if was_closed:
            cam.Close()
        return cam.Gain.GetValue()

    def flip_image_x(self, cam_id: int):
        """  Flips the image in the X plane"""
        was_closed = False
        cam = self.cam_array[cam_id]
        if not cam.IsOpen():
            was_closed = True
            cam.Open()
        cam.ReverseX = not cam.ReverseX.GetValue() #switch value
        if was_closed:
            cam.Close()

    def flip_image_y(self, cam_id: int):
        """  Flips the image in the Y plane"""
        was_closed = False
        cam = self.cam_array[cam_id]
        if not cam.IsOpen():
            was_closed = True
            cam.Open()
        cam.ReverseY = not cam.ReverseY.GetValue()  #switch value
        if was_closed:
            cam.Close()

    def run_single_cam_show(self, cam_id: int, stop_event: Event):
        was_closed = False
        cam = self.cam_array[cam_id]
        self.single_view_queue = Queue(100)
        if not cam.IsOpen():
            was_closed = True
            cam.Open()

        self.log.info(f'Showing device {CameraIdentificationSN(cam.GetDeviceInfo().GetSerialNumber()).name} '
                      f'with {self.fps} FPS')

        self._config_cams_continuous(cam)
        self.current_cam = cam
        self.stop_event = stop_event

        self.single_view_thread = Thread(target=self.single_cam_show)
        self.single_view_thread.start()

    def stop_single_cam_show(self):
        self.single_view_thread.join()  # wait for thread to finish
        self.current_cam = None
        self.stop_event = None
        self.single_view_thread = None
        #self.current_cam.StopGrabbing()  # just to be sure..

    def single_cam_show(self):
        cam = self.current_cam
        cam.StartGrabbing(pylon.GrabStrategy_LatestImageOnly)

        while not self.stop_event.isSet():
            try:
                grabResult = cam.RetrieveResult(self.grab_timeout, pylon.TimeoutHandling_ThrowException)
                img = grabResult.GetArray()
                self.single_view_queue.put_nowait(img)
                grabResult.Release()
                #if len(img.shape) == 2:
                #    img = np.stack([img]*3, -1)
            except genicam.TimeoutException as e:
                self.log.error(e)
                break
            except Full:
                self.log.error("Queue buffer overrun !")
                break
        cam.StopGrabbing()




if __name__ == "__main__":
    baslerRec = Recorder()
    print(baslerRec.get_cam_info())

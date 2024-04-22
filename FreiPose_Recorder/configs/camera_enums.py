from enum import Enum, unique
import json


# TODO some bigger changes happend in python 3.11 check if using this version !

@unique
class CameraIdentificationSN(Enum):
    def __new__(cls, sn):
        value = len(cls.__members__)
        obj = object.__new__(cls)
        obj.context = value
        obj._value_ = sn
        return obj

    cam_v0 = '0815-0000'
    cam_v1 = '0815-0001'
    cam_v3 = '0815-0002'
    cam_v4 = '0815-0003'
    cam_v5 = '0815-0004'
    cam_v6 = '0815-0005'
    cam_v7 = '0815-0006'
    cam_v8 = '0815-0007'

    cam42 = '22561089'
    cam43 = '40069823'

    cam00 = '22551262'
    cam01 = '22561086'
    cam02 = '22561087'
    cam03 = '22561096'
    # cam04 = '22561089'


class CameraRegistry:
    """Class to manage the camera serial numbers and their context values
    camera dict is stored in a json file, sn is the top key, name and context are the values
    context is hashed from the name, names are enforced to be unique
    thus collisions should be minimized
    _cameras = {
        '0815-0000': {'name': 'cam_v0', 'context': 0},
        '0815-0001': {'name': 'cam_v1', 'context': 1},
        '0815-0002': {'name': 'cam_v2', 'context': 2},
        '22561089': {'name': 'cam42', 'context': 3},
        '40069823': {'name': 'cam43', 'context': 4},
    }
    """
    def __init__(self):
        try:
            with open('../cameras.json', 'r') as f:
                self._cameras = json.load(f)
                if not self.validate_cameras():
                    self.write_newcam()
        except (FileNotFoundError, json.decoder.JSONDecodeError):
            self._cameras = {}

    def write_newcam(self):
        """write the camera dict to a json file"""
        with open('../cameras.json', 'w') as f:
            json.dump(self._cameras, f, indent=4)

    def get_camera(self, serial_number):
        """get the camera dict for a given serial number
        if the camera is not in the dict, add it"""
        if serial_number not in self._cameras:
            # Add a new camera if it does not exist
            index = len(self._cameras)
            #context = self.hash_camera_name(f'cam_{index:02d}')
            self._cameras[serial_number] = {'name': f'cam{index:02d}', 'context': index}
            self.validate_cameras()
            self.write_newcam()
        return self._cameras[serial_number]

    @classmethod
    def hash_camera_name(cls, name):
        """hash the camera name to a fixed size integer for the context value"""
        return hash(name) & 0xffffff  # Masking to get a fixed size integer

    def validate_cameras(self) -> bool:
        """
        check if the camera names are unique and add a context to the camera dict
        if dublicates are found, a _2 is added to the name, context is recalculated by hash
        :return: True if no dublicates are found
        """
        no_dubs = True
        for sn in self._cameras.keys():
            #find dubplicates name
            if list(val['name'] for val in self._cameras.values()).count(self._cameras[sn]['name']) > 1:
                self._cameras[sn]['name'] += '_2'
                no_dubs = False
            self._cameras[sn]['context'] = self.hash_camera_name(self._cameras[sn]['name'])
        return no_dubs

if __name__ == "__main__":
    CameraIdentificationSN('22561089')
    print(CameraIdentificationSN('22561089').context)

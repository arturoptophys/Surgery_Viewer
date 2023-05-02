from enum import IntEnum, Enum, unique
#TODO some bigger changes happend in python 3.11 check if using this version !

@unique
class CameraIdentificationSN(Enum):
    def __new__(cls, sn):
        value = len(cls.__members__)
        obj = object.__new__(cls)
        obj.context = value
        obj._value_ = sn
        return obj
    cam0 = '0815-0000'
    cam1 = '0815-0001'
    cam2 = '0815-0002'
    cam3 = '0815-0003'
    cam42 = '22561089'


@unique
class CameraIdentificationContext(IntEnum):
    cam0 = 0
    cam1 = 1
    cam2 = 2
    cam3 = 3
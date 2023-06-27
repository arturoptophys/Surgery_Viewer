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
    #cam04 = '22561089'



if __name__ == "__main__":
    CameraIdentificationSN('5')
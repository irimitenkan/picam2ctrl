'''
Created on 23.05.2023

@author: irimi
'''

import json
import logging

class Dict(dict):
    """dot.notation access to dictionary attributes"""
    __getattr__ = dict.__getitem__
    __setattr__ = dict.__setitem__
    __delattr__ = dict.__delitem__

# found at
# https://stackoverflow.com/questions/19078170/python-how-would-you-save-a-simple-settings-config-file
class Config(object):
    @staticmethod
    def __load__(data):
        if isinstance(data, dict):
            return Config.load_dict(data)
        elif isinstance(data, list):
            return Config.load_list(data)
        else:
            return data

    @staticmethod
    def load_dict(data: dict):
        result = Dict()
        for key, value in data.items():
            result[key] = Config.__load__(value)
        return result

    @staticmethod
    def load_list(data: list):
        result = [Config.__load__(item) for item in data]
        return result

    @staticmethod
    def load_json(path: str):
        with open(path, "r") as f:
            try:
                result = Config.__load__(json.loads(f.read()))
                return result
            except json.decoder.JSONDecodeError as e:
                logging.error(f"{path}: {e}")
            except TypeError as e:
                logging.error(f"{path}: {e}")
        return None



class CheckConfig (object):

    PAN_TILT_HARDWARE={
        "None":"None",
        "ULN2003":"STMicroelectronics",
        "WAVESHARE_HAT":"Waveshare"
        }

    @staticmethod
    def HasValidStartup(cfg:Config) -> bool:
        cnt=0
        enabled=""
        if cfg.startup.snap:
            cnt+=1
            enabled+="Snap,"
        if cfg.startup.video:
            cnt+=1
            enabled+=" Video,"
        if cfg.startup.videolapse:
            cnt+=1
            enabled+=" VideoLapse,"
        if cfg.startup.httpStream:
            cnt+=1
            enabled+=" HttpStream,"
        if cfg.startup.udpStream:
            cnt+=1
            enabled+=" UdpStream"

        if cnt>=2:
            logging.error("Check your startup settings ! Only ONE function can be enabled during startup.")
            logging.error(f"But {enabled} are enabled !")
            return False
        else:
            return True

    @staticmethod
    def HasPanTilt(cfg:Config) -> bool:
        if cfg.PanTilt.active in CheckConfig.PAN_TILT_HARDWARE:
            if "None" == cfg.PanTilt.active:
                return False
            else:
                return True
        else:
            logging.error(f"unknown PanTilt settings :'{cfg.PanTilt.active}'.")
            logging.info("Supported HW")
            for t in CheckConfig.PAN_TILT_HARDWARE:
                logging.info(f"{t}")
            exit(-1)
    
    @staticmethod
    def HasWaveShare(cfg:Config) -> bool:
        if CheckConfig.HasPanTilt(cfg):
            return cfg.PanTilt.active=="WAVESHARE_HAT"
        return False

    @staticmethod
    def HasULN2003(cfg:Config) -> bool:
        if CheckConfig.HasPanTilt(cfg):
            return cfg.PanTilt.active=="ULN2003"
        return False

    @staticmethod
    def HasTilt(cfg:Config) -> bool:
        if ("ULN2003" == cfg.PanTilt.active and \
            cfg.PanTilt.ULN2003.Tilt_enabled) or \
            "WAVESHARE_HAT" == cfg.PanTilt.active:
            return True
        return False
    
    @staticmethod    
    def HasLightSens(cfg:Config) -> bool:
        if "WAVESHARE_HAT" == cfg.PanTilt.active:
            return True
        return False

#cfg=Picam2Ctrl("./config.json")
#def getCfg()->Picam2Ctrl:
#    return cfg

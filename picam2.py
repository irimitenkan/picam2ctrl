'''
Created on 09.02.2023

@author: irimi
'''
import time
import json
import logging
import numpy as np
import subprocess as sp
import libcamera
from datetime import datetime as dt
from pathlib import Path
from picamera2.encoders import H264Encoder, Quality
from picamera2.outputs import FfmpegOutput
from picamera2.outputs import FileOutput
from picamera2 import Picamera2, MappedArray
from picamera2 import CameraConfiguration, StreamConfiguration, Controls
from libcamera import controls
from picamera2.encoders import MJPEGEncoder
from utils import ThreadEvent, StreamingOutput, StreamingHandler,StreamingServer
from config import Config

from cv2 import putText

INIT_TIMEOUT = 0.8

LAPS_FILEPATH ="timelapse"
VIDEO_FMT = "mp4"

FONTS = {
    "FONT_HERSHEY_SIMPLEX": 0,
    "FONT_HERSHEY_PLAIN": 1,
    "FONT_HERSHEY_DUPLEX": 2,
    "FONT_HERSHEY_COMPLEX": 3,
    "FONT_HERSHEY_TRIPLEX": 4,
    "FONT_HERSHEY_COMPLEX_SMALL": 5,
    "FONT_HERSHEY_SCRIPT_SIMPLEX": 6,
    "FONT_HERSHEY_SCRIPT_COMPLEX": 7
}

QUALITY = {
    "VERRY_LOW" : Quality.VERY_LOW,
    "LOW" : Quality.LOW,
    "MEDIUM" : Quality.MEDIUM,
    "HIGH" : Quality.HIGH,
    "VERY_HIGH" : Quality.VERY_HIGH,
    }

def popen (cmd):
    logging.debug(cmd)
    p = sp.Popen(
        cmd,
        shell=True,
        stdout=sp.PIPE,
        stderr=sp.PIPE)
    # waitpid(p.pid, 0)
    (stdout, stderr) = p.communicate()
    if p.returncode != 0:
        logging.error(f"{cmd} has failed: {str (stderr)}")
    else:
        logging.debug(f"{cmd} return result: {str (stdout)}")
        return str(stdout, encoding='utf-8').strip()

    return None

def getCameraInfo():
    p = popen ("libcamera-hello --version")
    if p:
        res= [Picamera2.global_camera_info(),p]
    else:
        res= [Picamera2.global_camera_info(),"tbd"]
    return res

"""
creates a mp4 slideshow video.
see details at https://trac.ffmpeg.org/wiki/Slideshow
"""
def mergeSlides (destPath):
    src= Path(destPath+ "/" + LAPS_FILEPATH).joinpath("snap-%03d.jpg")
    now = dt.now().strftime("%Y_%m_%d-%H_%M_%S")
    dest=Path(destPath).joinpath(f"TimeLaps-{now}.mp4")
    cmd = f"ffmpeg  -framerate 2 -i {src} -vf scale=1920:1080 -r 20  -c:v h264_v4l2m2m  -pix_fmt yuv420p {dest}"
    popen(cmd)
    return dest

def mergeVideo(destPath,stamps, src):
    dest=Path(destPath).joinpath(f"{src}.{VIDEO_FMT}")
    #1st create time sync mkv container
    cmd = f"mkvmerge -o {src}.mkv --timestamps 0:{stamps} {src}.h264"
    if popen(cmd):
        #2nd recode & move to mp4
        cmd = f"ffmpeg -i {src}.mkv -metadata comment=\"created by Picam2Ctrl\" -b: 6M -c:v h264_v4l2m2m {dest}"
        popen(cmd)
        return True

    return False

class CaptureThread(ThreadEvent):

    """
    Base class for capturing
    
    provides motion detection & time stamp generation
    
    """

    ctrlMapAwbMode={
        "Auto":libcamera.controls.AwbModeEnum.Auto,
        "Tungsten":libcamera.controls.AwbModeEnum.Tungsten,
        "Fluorescent":libcamera.controls.AwbModeEnum.Fluorescent,
        "Indoor":libcamera.controls.AwbModeEnum.Indoor,
        "Daylight":libcamera.controls.AwbModeEnum.Daylight,
        "Cloudy":libcamera.controls.AwbModeEnum.Cloudy
        }

    ctrlMapAwbEnable={
        "off":False,
        "on":True
        }

    #libcamera.controls.AwbEnable
    def __init__(self, parent: ThreadEvent, cfg: Config, ctrls:dict = None, bMotion:bool=False):
        super().__init__(parent)
        self.cfg = cfg
        self._bMotion=bMotion
        logging.debug(f"Capture Motion = {bMotion}")
        self.actCtrls=ctrls.copy()
        self.defaultCtrls=ctrls.copy()
        self.mapCtrls()

        self._size = (320, 200)
        self.picam2 = Picamera2(cfg.camera.index)
        logging.info("Configured camera:  "+str(self.picam2.camera_properties))
        if len(cfg.camera.tuning) > 0:
            self.picam2.load_tuning_file(cfg.camera.tuning)

        self.picam2.set_logging(logging.ERROR)
        if cfg.timestamp.enabled:
            self.picam2.pre_callback = self._apply_timestamp_
            logging.debug("Time Stamps enabled")

            self._col = tuple(json.loads(cfg.timestamp.color))
            self._org = tuple(json.loads(cfg.timestamp.origin))
            self._fscale = cfg.timestamp.fscale
            self._thick = cfg.timestamp.thickness
            self._fmt = cfg.timestamp.format
            self._font = FONTS.get(cfg.timestamp.font, 0)

        p = Path(self.cfg.storepath)
        try:
            p.mkdir(parents=False, exist_ok=True)  # to be created ?
        except Exception as e:
            logging.error(f"{str(e)}, configured store path not accessable")

    def mapCtrls(self):
        if len (self.actCtrls) > 0:
            self.actCtrls["AwbMode"]=self.ctrlMapAwbMode[self.actCtrls["AwbMode"]]
            if self.actCtrls['AwbEnable'] in self.ctrlMapAwbEnable:
                self.actCtrls["AwbEnable"]=self.ctrlMapAwbEnable[self.actCtrls["AwbEnable"]]
        else:
            self.actCtrls=self.defaultCtrls

    def _setCtrls_(self):
        if len(self.actCtrls)>0:
            logging.debug(f"picam2.set_controls={self.actCtrls}")
            self.picam2.set_controls(self.actCtrls)
            time.sleep(2) #must have
        else:
            logging.debug(f"picam2.set_controls not set")

    def updateCtrls(self,ctrls,update=True):
        self.actCtrls=ctrls.copy()
        self.mapCtrls()
        if update:
            self._setCtrls_()

    """
    delete "last file links" with specific file suffix in
    cfg.storepath/subdir directory
    resp create directory
    
    @param suffix: suffix of files to be deleted
    """
    def _clean_latest_(self, suffix,subdir="latest"):
        p = Path(self.cfg.storepath).joinpath(subdir)
        if p.exists():  # delete old latest files
            logging.debug("trying to delete old last files in" + str(p))
            for fn in p.glob('*.' + suffix):
                fn.unlink()
        else:
            try:
                p.mkdir(parents=False, exist_ok=True)  # to be created ?
            except Exception as e:
                logging.error(f"{str(e)}, configured store path not accessable")


    """
    simple scp execution, copies complete directory content client -> server 
    don't forget to pre share public ssh key, e.g.: ssh-copy-id -i .ssh/id_rsa.pub user@ssh-server 
    """
    def _scp_(self,file=None):
        if self.cfg.SSHClient.enabled:
            conn = f"{self.cfg.SSHClient.user}@{self.cfg.SSHClient.server}"
            dst = ":" + self.cfg.SSHClient.dest_path
            if file:
                cmd = f"scp {file} {conn}{dst}"
            else:
                cmd = f"scp -r {Path(self.cfg.storepath + '/latest')} {conn}{dst}"
            popen(cmd)

    """
    set timestamp to picam2 image/video/stream output 
    """
    def _apply_timestamp_(self, request):
        timestamp = time.strftime(self._fmt)
        with MappedArray(request, "main") as m:
            putText(m.array,
                    timestamp,
                    org=self._org,
                    fontFace=self._font,
                    fontScale=self._fscale,
                    color=self._col,
                    thickness=self._thick)

    """
    wait for motion detection for video or image capture
    """
    def _wait_for_motion_(self):
        msize = (320, 240)
        timeout = 5
        sensi = self.cfg.camera.sensitivity  # used delta mse and delta time
        mconfig = self.picam2.create_video_configuration(
            lores={"size": msize, "format": "YUV420"})
        self.picam2.configure(mconfig)
        self.picam2.start()
        time.sleep(timeout)

        w, h = msize
        prev = None
        mse = 0
        stime = time.time()
        while not self._stopEvent.is_set():
            dtime = int(time.time() - stime)
            logging.debug(f"Wait for mse>{sensi} , ResetTime={dtime}")
            cur = self.picam2.capture_buffer("lores")
            cur = cur[:w * h].reshape(h, w)
            if prev is not None and dtime < sensi:
                mse = np.square(np.subtract(cur, prev)).mean()
                logging.debug("mse =" + str(mse))
                if mse > sensi:
                    logging.debug("Motion detected")
                    self.picam2.stop()
                    self._parent.motion_detected()
                    self._record_motion_()
                    logging.debug("Waiting for next motion loop")
                    prev = None
                    self.picam2.configure(mconfig)
                    self.picam2.start()
                    time.sleep(timeout)

            else:
                logging.debug("mse delta reset " + str(stime))
                stime = time.time()
                prev = cur
                time.sleep(0.5) # reduce power consumption

    """ default method when motion has been detected"""
    def _record_motion_(self):
        self._single_capture_()

    def _worker_(self):
        if self._bMotion:
            self._wait_for_motion_()
        else:
            self.timeout = 1
            self._single_capture_()

    """
    shutdown and clean picam2 capture thread
    """
    def _shutdown_(self):
        self.picam2.close()
        super()._shutdown_()

    """
    to be defined by derived class: how to capture   
    """
    def _single_capture_(self):
        logging.error("_single_capture_ not implemented in derived class")


class ImageCapture (CaptureThread):
    """
    capture snapshot images to defined storepath
    """
    def __repr__(self):
        return "ImageCapture" 
    def __init__(self, parent: ThreadEvent, cfg: Config, ctrls, bMotion, iTime, iCount, bTimeLapse):
        super().__init__(parent, cfg, ctrls, bMotion)
        self._size = tuple(json.loads(cfg.image.size))
        self.ImgCount=int(iCount)
        self.ImgTime=int(iTime)
        self.bTLapse=bTimeLapse
        if bTimeLapse:
            self._clean_latest_(self.cfg.image.fmt,subdir=LAPS_FILEPATH)
        
    """
    single_capture method for images: number on snapshots define in configirution
    0 - endloss loop , capture images as long stop signal is not set
    1 ... n : capture 1 ... n images every    
    """
    def _single_capture_(self):

        logging.debug("ImageCapture: _single_capture_")
        iConfig = self.picam2.create_still_configuration(
            main={
                "size": self._size},
            transform=libcamera.Transform(
                hflip=self.cfg.camera.hflip,
                vflip=self.cfg.camera.vflip))

        self.picam2.configure(iConfig)
        self.picam2.start()
        time.sleep(INIT_TIMEOUT)
        self._setCtrls_()

        if 0==self.ImgCount: #endless loop until stop event
            i=1
            while not self._stopEvent.is_set():
                self._clean_latest_(self.cfg.image.fmt)
                self._snapshot_(i)
                self._scp_() # scp latest
                i+=1
        else:
            for i in range(0, self.ImgCount):
                self._clean_latest_(self.cfg.image.fmt)
                self._snapshot_(i+1)
                self._scp_() # scp latest
                if self._stopEvent.is_set():
                    break
            
        self.picam2.stop()
        if self.bTLapse:
            merged=mergeSlides(self.cfg.storepath)
            if merged:
                self._clean_latest_(self.cfg.image.fmt)
                file_l = Path(self.cfg.storepath + '/latest').joinpath("latest."+VIDEO_FMT)
                file_l.symlink_to(merged)
                self._scp_()
                self._clean_latest_(VIDEO_FMT)
            else:
                logging.debug("scp timelapsed failed")
    """
    make one single image snapshot
    @param i the image index number: 
    """
    def _snapshot_(self,i):
        if self.bTLapse:
            fn = f"{self.cfg.image.prefix}-{i:03d}.{self.cfg.image.fmt}"
            file = Path(self.cfg.storepath + "/" + LAPS_FILEPATH).joinpath(fn)
        else:
            now = dt.now().strftime("%Y_%m_%d-%H_%M_%S")
            fn = f"{self.cfg.image.prefix}-{now}.{self.cfg.image.fmt}"
            file = Path(self.cfg.storepath).joinpath(fn)
        fn_l = f"latest.{self.cfg.image.fmt}"
        file_l = Path(self.cfg.storepath + '/latest').joinpath(fn_l)

        logging.debug(f"image file={file}")
        logging.debug(f"image file_latest={file_l}")
        _metadata = self.picam2.capture_file(str(file))
        file_l.symlink_to(file)
        #logging.debug(f"metadata={str(metadata)}")
        if self.ImgCount != 1:
            time.sleep(self.ImgTime)

    def _shutdown_(self):
        self._clean_latest_(self.cfg.image.fmt)
        super()._shutdown_()

class VideoCapture (CaptureThread):
    """
    capture (mp4) videos  with / without audio to defined storepath
    """
    
    def __repr__(self):
        return "VideoCapture"

    def __init__(self, parent: ThreadEvent, cfg: Config, ctrls:dict, bMotion:bool, vTime:int):
        super().__init__(parent, cfg, ctrls, bMotion)
        logging.debug("creating VideoCapture")
        self._size = tuple(json.loads(cfg.video.size))
        self.vidTime=int(vTime)
    def _single_capture_(self):
        self._clean_latest_(VIDEO_FMT)
        quality=QUALITY.get(self.cfg.video.quality,Quality.HIGH)
        logging.debug("VideoCapture: _single_capture_")
        vconfig = self.picam2.create_video_configuration(
            main={
                "size": self._size},
            transform=libcamera.Transform(
                hflip=self.cfg.camera.hflip,
                vflip=self.cfg.camera.vflip))
        self.picam2.configure(vconfig)
        encoder = H264Encoder(self.cfg.video.bitrate)
        now = dt.now().strftime("%Y_%m_%d_%H_%M_%S")
        fn = f"{self.cfg.video.prefix}-{now}.{VIDEO_FMT}"
        fn_l = f"latest.{VIDEO_FMT}"
        file = Path(self.cfg.storepath).joinpath(fn)
        file_l = Path(self.cfg.storepath + '/latest').joinpath(fn_l)

        logging.debug(f"video file={file}")
        logging.debug(f"video file_latest={file_l}")

        # ffmpeg -re -i input.mkv -c:v libx264 -maxrate 1000k -bufsize 2000k
        # -an -bsf:v h264_mp4toannexb -g 50 http://localhost:8090/feed1.ffm
        output = FfmpegOutput(str(file), audio=self.cfg.video.audio)
        self._setCtrls_()
        self.picam2.start_recording(
            encoder, output, quality)  # VERY_HIGH,VERY_LOW,MEDIUM
        if 0==self.vidTime:
            while not self._stopEvent.is_set():
                time.sleep(1)
        else:
            time.sleep(self.vidTime)
        self.picam2.stop_recording()
        time.sleep(INIT_TIMEOUT)
        file_l.symlink_to(file)
        #self.picam2.stop()
        self._scp_()

    def _shutdown_(self):
        self._clean_latest_(VIDEO_FMT)
        super()._shutdown_()

class RtspCapture (CaptureThread):
    """
    RtspCapture capture (h264) videos  with / without audio
    """

    def __repr__(self):
        return "RtspCapture"

    def __init__(self, parent: ThreadEvent, cfg: Config, ctrls:dict, bMotion:bool, vTime:int):
        super().__init__(parent, cfg, ctrls, bMotion)
        logging.debug("creating RtspCapture")
        self._size = tuple(json.loads(cfg.video.size))
        self.vidTime=int(vTime)
    def _single_capture_(self):
        quality=QUALITY.get(self.cfg.video.quality,Quality.HIGH)
        logging.debug("RtspCapture: _single_capture_")
        vconfig = self.picam2.create_video_configuration(
            main={
                "size": self._size,
                "format": "RGB888"},
            transform=libcamera.Transform(
                hflip=self.cfg.camera.hflip,
                vflip=self.cfg.camera.vflip),
            controls={'FrameRate': 30})
        self.picam2.configure(vconfig)
        encoder = H264Encoder(repeat=True, iperiod=30, framerate=30, enable_sps_framerate=True)

        ref=self.cfg.video.streaming
        str_rtsp="-f rtsp -rtsp_transport tcp rtsp://"
        if len(self.cfg.video.streaming.rtsp_user):
            str_rtsp=str_rtsp+f"{ref.rtsp_user}:{ref.rtsp_passwd}@"
        str_rtsp=str_rtsp+f"{ref.rtsp_server}:{ref.rtsp_port}/{ref.rtsp_stream}"
        logging.debug(f"FfmpegOutput={str_rtsp},audio={self.cfg.video.audio}")
        output = FfmpegOutput(str_rtsp, audio=self.cfg.video.audio)
        self._setCtrls_()
        self.picam2.start_recording(
            encoder, output, quality)  # VERY_HIGH,VERY_LOW,MEDIUM
        logging.debug("-> in case of error 'default: No such process' check your audio settings")
        logging.debug("-> in case of error 'av_interleaved_write_frame() broken pipe")
        logging.debug("   with go2rtsp / frigate please read README.md in repro ADDONS folder")

        if 0==self.vidTime:
            while not self._stopEvent.is_set():
                time.sleep(INIT_TIMEOUT)
        else:
            time.sleep(self.vidTime)
        self.picam2.stop_recording()

class VideoCaptureElapse (CaptureThread):
    """
    capture (mp4) timeelapse videos
    """

    class TimelapseOutput(FileOutput):
        """
        inner helper class TimelapseOutput
        Define an output which divides all the timestamps by a factor
        based on picamera2/examples/capture_timelaspe_video.py
        """
        def __init__(self, file=None, pts=None, speed=10):
            self.speed = int(speed)
            logging.debug (f"TimelapseOutput file={file}, pts={pts}, speed={speed}")
            super().__init__(file, pts)

        def outputtimestamp(self, timestamp):
            if timestamp == 0:
                # Print timecode format for the first line
                print("# timestamp format v2", file=self.ptsoutput, flush=True)
            # Divide each timestamp by factor to speed up playback
            timestamp //= self.speed
            super().outputtimestamp(timestamp)

    def __repr__(self):
        return "VideoCapture"

    def __init__(self, parent: ThreadEvent, cfg: Config, ctrls:dict, bMotion:bool, vTime:int, vSpeed:int):
        super().__init__(parent, cfg, ctrls, bMotion)
        logging.debug("creating VideoCapture")
        self._size = tuple(json.loads(cfg.video.size))
        self.vidTime=int(vTime)

        self.vidSpeed=int(vSpeed)
        self._clean_latest_(VIDEO_FMT)

    def _single_capture_(self):
        quality=QUALITY.get(self.cfg.video.quality,Quality.HIGH)
        logging.debug("VideoCaptureElapse: _single_capture_")

        vconfig = self.picam2.create_video_configuration(
            main={
                "size": self._size},
            transform=libcamera.Transform(
                hflip=self.cfg.camera.hflip,
                vflip=self.cfg.camera.vflip))
        self.picam2.configure(vconfig)
        encoder = H264Encoder(self.cfg.video.bitrate)
        now = dt.now().strftime("%Y_%m_%d_%H_%M_%S")
        fn = f"{self.cfg.video.prefix}-{now}"
        fn_l = f"latest.{VIDEO_FMT}"
        # str required due to  print() AttributeError:
        #'PosixPath' object has no attribute 'write'
        file = str(Path(self.cfg.storepath).joinpath(fn))
        stamps = str(Path(self.cfg.storepath).joinpath("timestamps.txt"))

        file_l = Path(self.cfg.storepath + '/latest').joinpath(fn_l)

        logging.debug(f"video file={file}.{VIDEO_FMT}")
        logging.debug(f"video file_latest={file_l}")

        output = self.TimelapseOutput(file+".h264", stamps, self.vidSpeed)
        encoder.output = output
        self.picam2.start()
        time.sleep(INIT_TIMEOUT)
        self._setCtrls_()
        self.picam2.set_controls({"AeEnable": False, "AwbEnable": False, "FrameRate": 1.0})
        # And wait for those settings to take effect
        time.sleep(1)
        self.picam2.start_encoder(encoder, quality=quality)
        if 0==self.vidTime:
            while not self._stopEvent.is_set():
                time.sleep(1)
        else:
            time.sleep(self.vidTime)
        self.picam2.stop_encoder()
        self.picam2.stop()

        if mergeVideo(self.cfg.storepath,stamps, file):
            file_l.symlink_to(f"{file}.{VIDEO_FMT}")
            self._scp_()

    def _shutdown_(self):
        self._clean_latest_(VIDEO_FMT)
        super()._shutdown_()

class HTTPStreamCapture (CaptureThread):
    """
    simple HTTP Webserver page with video live stream 
    """
    def __repr__(self):
        return "HTTPStreamCapture" 

    def __init__(self, parent: ThreadEvent, cfg: Config, ctrls:dict, bMotion:bool):
        super().__init__(parent, cfg, ctrls, bMotion)
        logging.debug("creating HttpStreamCapture")
        self._size = tuple(json.loads(self.cfg.video.size))

    def _single_capture_(self):
        vconfig = self.picam2.create_video_configuration(
            main={
                "size": self._size},
            transform=libcamera.Transform(
                hflip=self.cfg.camera.hflip,
                vflip=self.cfg.camera.vflip))
        self.picam2.configure(vconfig)

        output = StreamingOutput()
        #encoder = H264Encoder(self.cfg.video.bitrate)
        encoder = MJPEGEncoder()
        #self.picam2.start_recording(JpegEncoder(70), FileOutput(output))
        self._setCtrls_()
        self.picam2.start_recording(encoder, FileOutput(output))
        address = ('', self.cfg.video.streaming.http_port)
        self.server = StreamingServer(address, StreamingHandler, output,self.cfg.video.streaming.http_index)
        #self.server.handle_request()
        self.server.serve_forever()
        self.server.server_close()
        self.picam2.stop_recording()
        self.picam2.stop()

    def trigger_stop(self):
        super().trigger_stop()
        self.server.shutdown()

    def _shutdown_(self):
        self.picam2.close()
        super()._shutdown_()

class UDPStreamCapture (CaptureThread):
    """
    UDP video live stream 
    """
    
    def __repr__(self):
        return "UDPStreamCapture" 
    
    def __init__(self, parent: ThreadEvent, cfg: Config, ctrls:dict, bMotion:bool):
        super().__init__(parent, cfg,ctrls, bMotion)
        logging.debug("creating UDPStreamCapture")
        self.__sock = None
        self._size = tuple(json.loads(cfg.video.size))

    def _single_capture_(self):
        vconfig = self.picam2.create_video_configuration(
            main={
                "size": self._size},
            transform=libcamera.Transform(
                hflip=self.cfg.camera.hflip,
                vflip=self.cfg.camera.vflip))
        self.picam2.configure(vconfig)
        encoder = H264Encoder(self.cfg.video.bitrate)
        output = FfmpegOutput(f"-f mpegts udp://{self.cfg.video.streaming.udp_addr}:{self.cfg.video.streaming.udp_port}",audio=self.cfg.video.audio)
        self._setCtrls_()
        self.picam2.start_recording(encoder, output)
        while not self._stopEvent.is_set():
            time.sleep(1)

        self.picam2.stop_recording()
        self.picam2.stop()
            
    def _shutdown_(self):
        self.picam2.close()
        super()._shutdown_()

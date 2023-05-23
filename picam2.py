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
from picamera2.encoders import MJPEGEncoder
from utils import ThreadEvent, StreamingOutput, StreamingHandler,StreamingServer
from config import Config

from cv2 import putText


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

def getCameraInfo():
    res = ("tbd","tbd")
    p = sp.Popen(
        "libcamera-hello --version",
        shell=True,
        stdout=sp.PIPE,
        stderr=sp.PIPE)
    (stdout, _stderr) = p.communicate()
    if p.returncode == 0:
        res= [Picamera2.global_camera_info(),
              str (stdout).strip('\\n').strip()]
    
    return res


class CaptureThread(ThreadEvent):

    """
    Base class for capturing
    
    provides motion detection & time stamp generation
    
    """
    def __init__(self, parent: ThreadEvent, cfg: Config, bMotion=False):
        super().__init__(parent)
        self.cfg = cfg
        self._bMotion=bMotion
        logging.debug(f"Capture Motion = {bMotion}")

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
        p.mkdir(parents=False, exist_ok=True)  # to be created ?

    """
    delete "last file links" with specific file suffix in
    cfg.storepath/latest directory
    
    @param suffix: suffix of files to be deleted
    """
    def _clean_latest_(self, suffix):
        p = Path(self.cfg.storepath).joinpath("latest")
        if p.exists():  # delete old latest files
            logging.debug("trying to delete old last files in" + str(p))
            for fn in p.glob('*.' + suffix):
                fn.unlink()
        else:
            p.mkdir(parents=False, exist_ok=True)  # to be created ?

    """
    simple scp execution, copies complete directory content client -> server 
    don't forget to pre share public ssh key, e.g.: ssh-copy-id -i .ssh/id_rsa.pub user@ssh-server 
    """
    def _scp_(self):
        if self.cfg.SSHClient.enabled:
            conn = f"{self.cfg.SSHClient.user}@{self.cfg.SSHClient.server}"
            dst = ":" + self.cfg.SSHClient.dest_path
            cmd = f"scp -r {Path(self.cfg.storepath + '/latest')} {conn}{dst}"
            #cmd = (["scp", "-r", f"{Path(self.cfg.storepath + '/latest')}", f"{conn}{dst}"])
            logging.debug(cmd)
            p = sp.Popen(
                cmd,
                shell=True,
                stdout=sp.PIPE,
                stderr=sp.PIPE)
            # waitpid(p.pid, 0)
            (stdout, stderr) = p.communicate()
            if p.returncode != 0:
                logging.error(f"scp has failed: {str (stderr)}")
            else:
                logging.debug(f"scp return result: {str (stdout)}")

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
    
    def __init__(self, parent: ThreadEvent, cfg: Config, bMotion):
        super().__init__(parent, cfg, bMotion)
        self._size = tuple(json.loads(cfg.image.size))
        
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
        time.sleep(1)
        
        if 0==self.cfg.image.snapshots: #endless loop until stop event
            while not self._stopEvent.is_set():
                self._clean_latest_(self.cfg.image.fmt)
                self._snapshot_(0)
        else:
            self._clean_latest_(self.cfg.image.fmt)
            for i in range(0, self.cfg.image.snapshots):
                self._snapshot_(i)
                if self._stopEvent.is_set():
                    break
            
        self.picam2.stop()
        self._scp_()
    
    """
    make one single image snapshot
    @param i the image index number: 
    """
    def _snapshot_(self,i):
        now = dt.now().strftime("%Y_%m_%d-%H_%M_%S")
        fn = f"{self.cfg.image.prefix}-{now}.{self.cfg.image.fmt}"
        fn_l = f"latest{i+1}.{self.cfg.image.fmt}"
        file = Path(self.cfg.storepath).joinpath(fn)
        file_l = Path(self.cfg.storepath + '/latest').joinpath(fn_l)

        logging.debug(f"image file={file}")
        logging.debug(f"image file_latest={file_l}")
        metadata = self.picam2.capture_file(str(file))

        file_l.symlink_to(file)
        logging.debug(f"metadata={str(metadata)}")
        time.sleep(self.cfg.image.snapshots_t)
        
        
    def _shutdown_(self):
        self._clean_latest_(self.cfg.image.fmt)
        super()._shutdown_()


class VideoCapture (CaptureThread):
    """
    capture (mp4) videos  with / without audio to defined storepath
    """
    
    def __repr__(self):
        return "VideoCapture" 

    def __init__(self, parent: ThreadEvent, cfg: Config, bMotion):
        super().__init__(parent, cfg, bMotion)
        logging.debug("creating VideoCapture")
        self._size = tuple(json.loads(cfg.video.size))

    def _single_capture_(self):
        quality=QUALITY.get(self.cfg.video.quality,Quality.HIGH)
        logging.debug("VideoCapture: _single_capture_")
        self._clean_latest_(self.cfg.video.fmt)
        vconfig = self.picam2.create_video_configuration(
            main={
                "size": self._size},
            transform=libcamera.Transform(
                hflip=self.cfg.camera.hflip,
                vflip=self.cfg.camera.vflip))
        self.picam2.configure(vconfig)
        #self.picam2.start()
        encoder = H264Encoder(self.cfg.video.bitrate)
        now = dt.now().strftime("%Y_%m_%d_%H_%M_%S")
        fn = f"{self.cfg.video.prefix}-{now}.{self.cfg.video.fmt}"
        fn_l = f"latest.{self.cfg.video.fmt}"
        file = Path(self.cfg.storepath).joinpath(fn)
        file_l = Path(self.cfg.storepath + '/latest').joinpath(fn_l)

        logging.debug(f"video file={file}")
        logging.debug(f"video file_latest={file_l}")

        # ffmpeg -re -i input.mkv -c:v libx264 -maxrate 1000k -bufsize 2000k
        # -an -bsf:v h264_mp4toannexb -g 50 http://localhost:8090/feed1.ffm
        output = FfmpegOutput(str(file), audio=self.cfg.video.audio)
        self.picam2.start_recording(
            encoder, output, quality)  # VERY_HIGH,VERY_LOW,MEDIUM
        time.sleep(self.cfg.video.duration)
        self.picam2.stop_recording()
        file_l.symlink_to(file)
        #self.picam2.stop()
        self._scp_()

    def _shutdown_(self):
        self._clean_latest_(self.cfg.video.fmt)
        super()._shutdown_()

class HTTPStreamCapture (CaptureThread):
    """
    simple HTTP Webserver page with video live stream 
    """
    def __repr__(self):
        return "HTTPStreamCapture" 
    
    def __init__(self, parent: ThreadEvent, cfg: Config, bMotion):
        super().__init__(parent, cfg, bMotion)
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
    
    def __init__(self, parent: ThreadEvent, cfg: Config, bMotion):
        super().__init__(parent, cfg,bMotion)
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
        self.picam2.start_recording(encoder, output)
        while not self._stopEvent.is_set():
            time.sleep(1)

        self.picam2.stop_recording()
        self.picam2.stop()
            
    def _shutdown_(self):
        self.picam2.close()
        super()._shutdown_()


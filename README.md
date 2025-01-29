# Picam2Ctrl

[Overview](#Overview) |
[Features](#Features) |
[Installation](#Installation) |
[Running the MQTT client](#Running) |
[RTSP](#RTSP) |
[Configuration](#Configuration) |
[Pan-Hardware](#PAN-Hardware) |
[Home Assistant Integration](#HASS-Integration)

# Overview

Picam2ctrl is a MQTT client based on new [Picamera2 API](https://github.com/raspberrypi/picamera2 ) with [Home Assistant](https://www.home-assistant.io/) discovery support.

## General Restriction

Since [Picamera2](https://github.com/raspberrypi/picamera2) is currently only available as a [beta release](https://github.com/raspberrypi/picamera2#readme) *picam2ctrl* can break with newer *Picamera2* releases.

More details about the new libcamera-based Python-API for Raspberry Pi camera you can find [here](https://www.raspberrypi.com/documentation/computers/camera_software.html ).

# Features

MQTT client to control your Raspberry Pi Camera with [Home Assistant](https://www.home-assistant.io/)

* actual 10 different MQTT client entities
* taking snapshot pictures
* capturing MP4 videos incl. audio
* RTSP video streaming of camera to RTSP server mediaMTX / go2rtsp / frigate
* simple HTTP MJPEG streaming server
* UDP video streaming
* motion/occupancy detection by camera
* picamera tuning controls support
* timestamp support
* time elapse video support
* PAN / TILT camera support with 5V Stepper Motor (28BYJ-48) and ULN2003 driver board (optinal)
* PAN-TILT Hat by Waveshare integrated incl. lighsensor
* support of secure copy latest picture- / video-files to SSH server

# Installation

Raspberry Pi OS bullseye version is required and camera legacy mode must be disabled in raspi-config.
On headless Raspberry Pi OS lite you have to update from *libcamera-apps-lite* to full version *libcamera-apps*.
No gui but OpenCV python bindings and paho-mqtt package are required:

  ```
  sudo apt-get install -y --no-install-recommends libcamera-apps python3-picamera2 python3-opencv python3-paho-mqtt python3-smbus ffmpeg git
  ```

finally clone the picam2ctrl repository:

  ```
  git clone https://github.com/irimitenkan/picam2ctrl.git
  ```

## Installation & Calibration of Waveshare's Pan-Tilt Hat (optional)

For 1st setup the calibration of the servos is required to avoid a damage when the servos are assembled, i.e. that must be done *BEFORE* the Pan-Tilt Hat is assembled completly. After that the servomotors are set to 0° degrees. Keep in mind you still have to consider the angles for assignment of the CAM direction when you assemble the hat.

According to Waweshare's [documentation](https://www.waveshare.com/w/upload/b/b9/Pan-Tilt_HAT_user_manual_en.pdf) there is a test program for servo adjustment but it requires WiringPi which has been removed from Bullseye's repro. WiringPi package is still available at [github](https://github.com/WiringPi/WiringPi/releases/download/2.61-1/wiringpi-2.61-1-armhf.deb) but we can use here a python script instead. It is available at this picam2ctrl repro.

Hence:

* enable I2C in raspi-config (Interface options -> I2C -> enable)
* python smbus is required:

  ```
  sudo apt install python3-smbus
  ```

* only connect Pan & Tilt servos to hat
* connect hat with Raspberry Pi
* execute servoTest

  ```
  python pantilt/waveshare/servoTest.py
  ```

* proceed with Pan-Tilt Hat assembling see Waveshare's [guideline](https://www.waveshare.com/img/devkit/accBoard/Pan-Tilt-HAT/Pan-Tilt-HAT-assemble.jpg)

* finally enable Pan-Tilt Hat in config.json if not already done

  ```
  "PanTilt":{
     "active":"WAVESHARE_HAT",

  ```

## Picamera2 options

For Picamera2 with GUI support , for non-headless Raspberry see [Picamera2 installation](https://github.com/raspberrypi/picamera2#installation )

# RTSP

A RTSP server is required, see [README](https://github.com/irimitenkan/picam2ctrl/blob/main/addons/README.md) for details in adddons folder

# Configuration

Example config.json

  ```
  {
    "LogLevel":"INFO",
    "storepath": "/home/pi/picam2",
    "HASS_Node_ID":"%HOSTNAME",
    "//HASS_Node_ID":"SELF_DEFINED_UNIQUE_ID",

    "startup": {
        "motion":false,
        "snap":false,
        "video":false,
        "videolapse":false,
        "httpStream":false,
        "udpStream":false,
        "rtspStream":false,
        "panAuto":false,
        "SnapTimer":10,
        "SnapCount":1,
        "VideoTimer":10,
        "VideoLapseSpeed":10,
        "PanAngle":0,
        "TiltAngle":0
 },

   "startup": {
    "motion":false,
    "snap":false,
    "video":false,
    "videolapse":false,
    "httpStream":false,
    "udpStream":false,
    "panAuto":false,
 
    "SnapTimer":10,
    "SnapCount":1,
    "VideoTimer":10,
    "VideoLapseSpeed":10,
    "PanAngle":0,
    "TiltAngle":0
   },

    "camera": {
    "index":0,
    "hflip":1,
    "vflip":1,
    "sensitivity": 10,
    "tuning":"/usr/share/libcamera/ipa/raspberrypi/imx708.json"
    "ControlOptionsDoc": "https://datasheets.raspberrypi.com/camera/picamera2-manual.pdf",
    "CtrlsEnabled": false,
    "Tune": {
    "AwbEnable":true,
    "//AwbMode Auto, Tungsten, Fluorescent, Indoor, Daylight,Cloudy": "",
    "AwbMode": "Auto",
    "Brightness": 0.0,
    "Contrast": 1.0,
    "Saturation": 1.0,
    "Sharpness": 1.0
        },
    },

    "timestamp": {
    "enabled":true,
    "format": "%A %d.%b %Y - %X",
    "color" : "[255, 255, 0]",
    "origin" : "[0, 45]",
    "font" : "FONT_HERSHEY_TRIPLEX",
    "fscale" : 2,
    "thickness" : 2
    },

    "image": {
      "prefix":"snap",
      "fmt": "jpg",
      "size": "[4056, 3040]"
    },

    "video": {
      "prefix": "videosnap",
      "bitrate": 1000000,
      "size" : "[ 1920, 1080]",
      "quality" : "HIGH",
      "audio":true,

      "streaming": {
        "udp_addr": "<DESTINATION-IP-ADDRESS>",
        "udp_port": 10001,
        "http_port": 8010,
        "http_index":"www/index.html"
        "rtsp_user":"",
        "rtsp_passwd":"",
        "rtsp_port":"8554",
        "rtsp_server":"localhost",
        "rtsp_stream":"picamera2"
      }
    },

      "MQTTBroker":{
      "host":"<ADDRESS OF BROKER>",
      "port": 8883,
      "username":"<USERNAME>",
      "password":"<SECRET>",
      "servercafile":"",
      "clientkeyfile":"",
      "clientcertfile":""
    },

    "SSHClient":{
      "enabled":true,
      "server": "<SSH SERVER ADDRESS>",
      "user" : "<SSH USERNAME>",
      "dest_path" : "/opt/homeassistant/config/tmp"
    },

  "PanTilt":{
  "active":"WAVESHARE_HAT",
  "speed":"SLOW",
   "Pan":{
       "angle_max":80,
       "angle_min":-80,
       "flip":true
   },
   "Tilt":{
       "angle_low":-26,
       "angle_high":60,
       "flip":true
   },


     "None":{
            "//":"PanTilt is disabled"
            },

     "ULN2003":{
            "Pan_enabled":true,
            "Tilt_enabled":true,
            "check":true,
            "Pan_GPIO_PinA": 27,
            "Pan_GPIO_PinB": 22,
            "Pan_GPIO_PinC": 23,
            "Pan_GPIO_PinD": 24,

            "Tilt_GPIO_PinA": 13,
            "Tilt_GPIO_PinB": 15,
            "Tilt_GPIO_PinC": 16,
            "Tilt_GPIO_PinD": 18
    },

    "WAVESHARE_HAT":{
        "sensorRefresh":60
            }

  }


}

  ```

## startup options

* "motion":false : enable/disable motion detection during startup

only ONE of these camera applications can be enabled (value=true) when the client is started:

* "snap":false,
* "video":false,
* "videolapse":false,
* "httpStream":false,
* "udpStream":false,
* "rtspStream":false,

* "panAuto":false,

configure initial startup values of client:

* "SnapTimer":10 : timeout for next snapshot
* "SnapCount":1: count of snapshot
* "VideoTimer": video record time length - value 0 := infinite time
* "VideoLapseSpeed":10 : video lapse speed factor
* "PanAngle":0 : default Pan Angle (depends on HW)
* "TiltAngle":0 :: default Tilt Angle (depends on HW)

## camera options

* "index":0 - the camera idx of connected camera
* "hflip", vflip: 0/1 - to rotate camera output
* "sensitivity": 10 - used for motion detection,for manual calibration, set LogLevel to "DEBUG" and check output during detection.
* "tuning": "path to file" - special tuning e.g. for noir camera

## tuning control options

See details for allowed tuning value option for each parameter in [PiCamera2 manual]("https://datasheets.raspberrypi.com/camera/picamera2-manual.pdf")

To enable picamera's control tuning options

* "CtrlsEnabled" must be set to *true*

Supported tuning parameters

* "AwbEnable"
* "AwbMode"
* "Brightness"
* "Contrast"
* "Saturation"
* "Sharpness"

## timestamp options

* "format" = "code string", see documention of [strftime options](https://docs.python.org/3/library/datetime.html#strftime-strptime-behavior)
* "font" : allowed 'HERSHEY' string values see module picam2.FONTS resp. [here](https://docs.opencv.org/4.x/d6/d6e/group__imgproc__draw.html)

## video options

* "quality" : "HIGH" - allowed values: VERY_LOW, LOW, MEDIUM, HIGH or VERY_HIGH
* "audio":true - enable/disable audio for mp4 file resp UDP streaming (http actually not supported).

## SSHClient options

resp. SCP support to be used to copy latest snapshot picture / mp4 video to a SSH server (e.g. your Home Assistant host)
but setup up public key authentication is required:

1. generate SSH Key with ssh-keygen e.g. ```ssh-keygen -t rsa -b 4096```
2. copy the public key to your desired server with
3. ```ssh-copy-id -i ~/.ssh/id_rsa.pub user@host```
4. verify passwordless login: ```ssh user@host```

5. finally check user@host has write access to configured destination path e.g.:
   "dest_path" : "/opt/homeassistant/config/tmp"

## PanTilt options

* "check" : when 'true' the LEDs on ULN2003 driver board will flash during startup (A->B->C->D, if GPIO PINS are connected correctly), disabled with 'false'
* 'speed' : PAN speed, allowed values: VERY_SLOW, SLOW, MEDIUM, FAST, VERY_FAST
* 'angle_max : maxium absolute angle to pan camera to left resp. right side
* 'GPIO_PinA (B, C, D)' : GPIO Pin A (B, C, D) of ULN2003 driver board wiring assigment, see check option for verification. More details see [PAN-HW chapter](##PAN-Hardware)

## WAVESHARE options

* 'sensorRefresh': refresh rate in [t] to update the most recent illuminance state of light sensor

# Running

* to start from terminal

  ```
  cd picam2ctrl
  python3 picam2ctrl.py
  ```

 with option: -c FILE, --cfg=FILE  set config file default: ./config.json

* to stop it & started from terminal

  ```
  enter CTRL-C
  ```

* to enable at startup and start service:

  ```
  loginctl enable-linger
  systemctl --user enable --now ~/picam2ctrl/picam2ctrl.service
  ```

* to disable running service at startup and stop it:

  ```
  systemctl --user disable --now picam2ctrl
  ```

* to stop the service again

  ```
  systemctl --user stop picam2ctrl
  ```

* to start the service

  ```
  systemctl --user start picam2ctrl
  ```

* check the status of the service

  ```
  systemctl --user status picam2ctrl
  ```

* check the picam2ctrl specific service logs

  ```
  journalctl --user-unit picam2ctrl
  ```

# PAN-Tilt-Hardware

## ULN2003 with 5V step motor(s) 28BYJ-48

The PAN camera can be realized with a step-motor which can be controlled with 4 GPIO ports of your Raspberry Pi.

You need to buy a [5V step motor 28BYJ-48 with ULN2003 driver board](https://www.amazon.com/s?k=ULN2003+driver+board+28BYJ-48).

Howto setup the hardware wiring you can find e.g.[here](https://diyprojectslab.com/28byj-48-stepper-motor-with-raspberry-pi-pico/) or [here](https://github.com/gavinlyonsrepo/RpiMotorLib/blob/master/Documentation/28BYJ.md).

Finally we need a construction to pan the connected Raspberry Pi Camera with above mentioned step-motor. As solution a Raspberry Pi housing with camera integration support is recommended: we pan the complete Raspberry Pi case.

My 1st prototype is using the [Raspberry Pi 3 case](https://www.raspberrypi.com/products/raspberry-pi-3-case/) with a wide angle camera.
Here is an [image of the PAN camera prototype](https://github.com/irimitenkan/picam2ctrl/blob/main/images/Mounted_Prototype_1.jpg) and some construction details [Mounting_Prototype_1.jpg](https://github.com/irimitenkan/picam2ctrl/blob/main/images/Mounting_Prototype_1.jpg) & [Mounting_Prototype_2.jpg](https://github.com/irimitenkan/picam2ctrl/blob/main/images/Mounting_Prototype_2.jpg)

## Waveshare's Pan-Tilt Hat

Full support of [Waveshare's Pan-Tilt Hat](https://www.waveshare.com/pan-tilt-hat.htm), see some more details at [Installation](## Installation)

# HASS-Integration

All picam2ctrl entities will be detected by Home Assistant automatically
by HASS discovery function via configured MQTT broker.

## available Home Assistant entities

* picam2ctrl.\< HOSTNAME \>.Record:

  represents a state
  * state runing when Image Snapshot / (Timelapse) Video or streaming is active
  * state not running when no picam2 record function is active

* picam2ctrl.\< HOSTNAME \>.Snapshot:

  this is a *switch* to enable/disable the picture snapshot function.

  * when [image.snapshots](## Configuration) is set to 0, picam2ctrl takes picture every [image.snapshots_t](## Configuration) seconds in an endless loop, since there is no switch off request
  * when count is set to x>0,  picam2ctrl takes x pictures every .. s  and stops.
  * when [Motion](##Motion) is disabled picture(s) will be taken immediately
  * when [Motion](##Motion) is enabled, picture(s) will be taken only after motion detection
  * when [timestamp](##Configuration) is enabled each picture has a time stamp as configured in json configuration
  * when [[SSHClient]](##Configuration) is enabled the latest taken picture(s) will be copied via secure shell to configured path @SSH server

* picam2ctrl.\< HOSTNAME \>.SnapshotCounter

  this is a number box field:

  * setup how many images will taken when Snapshot function was triggered

* picam2ctrl.\< HOSTNAME \>.SnapshotTimer

  this is a number box field:

  * setup the time between two image snapshots when SnapshotCounter > 1

* picam2ctrl.\< HOSTNAME \>.TimeLapse:

  This is a *switch* to activate / deactive TimeLapse function for Video resp. Snapshotfunction

  * when active and 'Video' is triggered: a mp4 video with "VidLapsSpeed" factor is created
  * when active and 'Snapshot' is triggered and SnapshotCounter > 1 a mp4 video is created by concatenating the snapshot images
  Attention: ffmmeg and mkvmerge must be installed

* picam2ctrl.\< HOSTNAME \>.VidLapseSpeed

  This is a *slider* to to setup the timeeplased video speed:
  * the time speed factor to create an mp4 video when 'TimeLapse' is active

* picam2ctrl.\< HOSTNAME \>.Video:

  This is a *switch* to enable/disable the video snapshot function.

  * when count is set to x>0,  picam2ctrl takes x pictures every .. s  and stops.
  * when [Motion](##Motion) is disabled picture(s) will be taken immediately
  * when [Motion](##Motion) is enabled, picture(s) will be taken only after motion detection
  * when [timestamp](##Configuration) is enabled each picture has a time stamp as configured in json configuration
  * when [audio](##Configuration) is enabled & available mp4 video file incl. audio stream is created
  * when [SSHClient](##Configuration) is enabled the latest taken video will be copied via secure shell to configured path @SSH server

* picam2ctrl.\< HOSTNAME \>.VideoTimer

  this is a number box field:

  * setup the time Video record time in [s]. 0s := infinite, since to video/udp/rtsp switch in on


* picam2ctrl.\< HOSTNAME \>.RtspStream:

  This is a *switch* to enable/disable a RTSP video stream.

  * when [Motion](##Motion) is disabled the rtsp stream starts immediately
  * when [Motion](##Motion)  is enabled, the rtsp stream starts after motion detection
  * when [timestamp](##Configuration) is enabled the rtsp stream has a time stamp as configured in json configuration
  * duration depends on VideoTimer value in [s]. 0s := infinite, since to rtsp switch in on

* picam2ctrl.\< HOSTNAME \>.HttpStream:

  This is a *switch* to enable/disable a simple HTTP Server with MJPEG stream.

  * when [Motion](##Motion) is disabled the MJPEG stream starts immediately
  * when [Motion](##Motion)  is enabled, the MJEP stream starts after motion detection
  * when [timestamp](##Configuration) is enabled the MJPEG stream has a time stamp as configured in json configuration

* picam2ctrl.\< HOSTNAME \>.UdpStream:

  This is a *switch* to enable/disable an UDP video stream.

  * when [Motion](##Motion) is disabled the UDP stream starts immediately
  * when [Motion](##Motion) is enabled, the UDP stream starts after motion detection
  * when [timestamp](##Configuration) is enabled the video stream has a time stamp as configured in json configuration
  * when [audio](##Configuration) is enabled & available the video+audio stream is created

## tuning controls

* picam2ctrl.\< HOSTNAME \>.TuneCtrls:

  This is a *switch* to enable/disable tuning controls of picamera2.
  * when disabled picamera2 default control settings are used. see details in [PiCamera2 manual]("https://datasheets.raspberrypi.com/camera/picamera2-manual.pdf")

* picam2ctrl.\< HOSTNAME \>.AwbEnable

  This is a *switch*

* picam2ctrl.\< HOSTNAME \>.AwbMode

  This is an *option list*

* picam2ctrl.\< HOSTNAME \>.Brightness

  This is a *float number* represented by a *slider*

* picam2ctrl.\< HOSTNAME \>.Contrast

  This is a *float number* represented by a *slider*

* picam2ctrl.\< HOSTNAME \>.Saturation

  This is a *float number* represented by a *slider*

* picam2ctrl.\< HOSTNAME \>.Sharpness

  This is a *float number* represented by a *slider*

## PAN-TILT

* picam2ctrl.\< HOSTNAME \>.Pan-Automation:

  This is a *switch* to enable/disable to pan the camera in range from -angle_max to +angle_max automatically.

* picam2ctrl.\< HOSTNAME \>.Pan:

  This is a *slider* to pan the camera in range -angle_max to +angle_max manually.

* picam2ctrl.\< HOSTNAME \>.Tilt:

  This is a *slider* to tilt the camera in range -angle_max to +angle_max manually.
  It is only available  with WAVESHARE_HAT or ULN2003 & tilt enabled.

## Motion

* picam2ctrl.\< HOSTNAME \>.MotionEnabled:

  This is a *switch* to enable/disable the motion detection.
  * a switch off request deactivates a running function, too
  * when disabled the Motion binary switch is not available in HASS

* picam2ctrl.\< HOSTNAME \>.Motion:

  This is a *binary switch* . It becomes active for ~0.5s if
  * MotionEnabled switch is active
  * and one of the above mentioned functions (streaming, picture/video snapshot) is enabled
  * and a motion has been detected by camera

  *Restrictions*
  Only one switch resp. camera application (HTTPStream, UDPStream, video capturing to file or image snapshots ) can be enabled.
  Since one application is active, switching on requests for other applications are ignored.

## Lightsensor

* picam2ctrl.\< HOSTNAME \>.Lightsensor:

  This is a illumance *sensor* , which is only avaliable with Waveshare Pan-Tilt Hat

# Home Assistant Configuration

configuration.yaml examples for showing camera output in [Home Assistant](https://www.home-assistant.io/):

## UDP Stream

  ```
  camera:
    - platform: ffmpeg
      name: picamera2
      input: 'udp://@:10001'
  ```

## HTTPServer / MJPEG Stream

* In Home Assistant go to
  * add integration
  * from the list, search and select “MJPEG IP Camera”
  * in MJPEG-URL field enter

  ```
  http://< YOUR_RASPI_ADDRESS >:< CONFIGURED_HTTP_PORT>/stream.mjpg
  ```

## picture snapshots

* In Home Assistant go to
  * add integration
  * from the list, search and select *Local File*
  * enter file path e.g. /config/tmp/latest/latest1.jpg

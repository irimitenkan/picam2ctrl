# Picam2ctrl
[Overview](#Overview) |
[Features](#Features) |
[Installation](#Installation) |
[Running the MQTT client](#Running) |
[Configuration](#Configuration) |
[Pan-Hardware](#PAN-Hardware) |
[Home Assistant Integration](#HASS-Integration)

# Overview

Picam2ctrl is a MQTT client based on new [Picamera2 API](https://github.com/raspberrypi/picamera2 ) with [Home Assistant](https://www.home-assistant.io/) discovery support.

*General Restriction*

Since [Picamera2](https://github.com/raspberrypi/picamera2) is currently only available as a [beta release](https://github.com/raspberrypi/picamera2#readme) *picam2ctrl* can break with newer *Picamera2* releases.

More details about the new libcamera-based Python-API for Raspberry Pi camera you can find [here](https://www.raspberrypi.com/documentation/computers/camera_software.html ).

# Features

MQTT client to control your Raspberry Pi Camera with [Home Assistant](https://www.home-assistant.io/)

* taking snapshot pictures
* capturing MP4 videos incl. audio 
* simple HTTP MJPEG streaming server
* UDP video streaming
* motion/occupancy detection by camera
* timestamp support
* PAN camera support with 5V Stepper Motor (28BYJ-48) and ULN2003 driver board
* support of secure copy latest picture- / video-files to SSH server 

# Installation

Raspberry Pi OS bullseye version is required and camera legacy mode must be disabled in raspi-config.
On headless Raspberry Pi OS lite you have to update from *libcamera-apps-lite* to full version *libcamera-apps*. 
No gui but OpenCV python bindings and paho-mqtt package are required:

  ```
  sudo apt-get install -y --no-install-recommends libcamera-apps python3-picamera2 python3-opencv python3-paho-mqtt ffmpeg git
  ```

finally clone the picam2ctrl repository:


  ```
  git clone https://github.com/irimitenkan/picam2ctrl.git
  ```


For Picamera2 with GUI support see [Picamera2 installation](https://github.com/raspberrypi/picamera2#installation )

# Configuration

Example config.json


  ```
  {
    "LogLevel":"INFO",
    "storepath": "/home/pi/picam2",

    "camera": {
    "index":0,
    "hflip":1,
    "vflip":1,
    "sensitivity": 10,
    "tuning":"/usr/share/libcamera/ipa/raspberrypi/imx708.json"
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
      "size": "[4056, 3040]",
      "snapshots":1,
      "snapshots_t":10
    },

    "video": {
      "prefix": "videosnap",
      "fmt": "mp4",
      "bitrate": 1000000,
      "size" : "[ 1920, 1080]",
      "quality" : "HIGH",
      "duration" : 30,
      "audio":true,

      "streaming": {
        "udp_addr": "<DESTINATION-IP-ADDRESS>",
        "udp_port": 10001,
        "http_port": 8010,
        "http_index":"www/index.html"
      }
    },

      "MQTTBroker":{
      "host":"<ADDRESS OF BROKER>",
      "port": 8883,
      "username":"<USERNAME>",
      "password":"<SECRET>",
      "insecure":true,
      "connection_retries":3,
      "clientkeyfile":"",
      "clientcertfile":""
    },

    "SSHClient":{
      "enabled":true,
      "server": "<SSH SERVER ADDRESS>",
      "user" : "<SSH USERNAME>",
      "dest_path" : "/opt/homeassistant/config/tmp"
    },
    
    "PAN":{
     "enabled":true,
     "check":true,
     "speed":"MEDIUM",
     "angle_max" : 90,
	 "GPIO_PinA": 27,
	 "GPIO_PinB": 22,
	 "GPIO_PinC": 23,
	 "GPIO_PinD": 24
    }
    
  }

  ```

## camera options 
* "index":0 - the camera idx of connected camera
* "hflip", vflip: 0/1 - to rotate camera output
* "sensitivity": 10 - used for motion detection,for manual calibration, set LogLevel to "DEBUG" and check output during detection.
* "tuning": "path to file" - special tuning e.g. for noir camera
	
## timestamp options
* "format" = "code string", see documention of [strftime options](https://docs.python.org/3/library/datetime.html#strftime-strptime-behavior)
* "font" : allowed 'HERSHEY' string values see module picam2.FONTS resp. [here](https://docs.opencv.org/4.x/d6/d6e/group__imgproc__draw.html)

## video options
* "quality" : "HIGH" - allowed values: VERY_LOW, LOW, MEDIUM, HIGH or VERY_HIGH
* "duration" : 30 - mp4 record time length in [s].
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

## PAN options
* "check" : when 'true' the LEDs on ULN2003 driver board will flash during startup (A->B->C->D, if GPIO PINS are connected correctly), disabled with 'false'
* 'speed' : PAN speed, allowed values: VERY_SLOW, SLOW, MEDIUM, FAST, VERY_FAST
* 'angle_max : maxium absolute angle to pan camera to left resp. right side  
* 'GPIO_PinA (B, C, D)' : GPIO Pin A (B, C, D) of ULN2003 driver board wiring assigment, see check option for verification. More details see [PAN-HW chapter](#PAN-Hardware)

# Running
- to start from terminal

  ```
  cd picam2ctrl
  python3 picam2ctrl.py
  ```
 with option: -c FILE, --cfg=FILE  set config file default: ./config.json

- to stop it & started from terminal

  ```
  enter CTRL-C
  ```

- to enable at startup and start service:

  ```
  loginctl enable-linger
  systemctl --user enable --now ~/picam2ctrl/picam2ctrl.service
  ```

- to disable running service at startup and stop it:

  ```
  systemctl --user disable --now picam2ctrl
  ```

- to stop the service again

  ```
  systemctl --user stop picam2ctrl
  ```

- to start the service

  ```
  systemctl --user start picam2ctrl
  ```

- check the status of the service

  ```
  systemctl --user status picam2ctrl
  ```

- check the picam2ctrl specific service logs

  ```
  journalctl --user-unit picam2ctrl
  ```

# PAN-Hardware

The PAN camera can be realized with a step-motor which can be controlled with 4 GPIO ports of your Raspberry Pi.
You need to buy a [5V step motor 28BYJ-48 with ULN2003 driver board](https://www.amazon.com/s?k=ULN2003+driver+board+28BYJ-48).
 
Howto setup the hardware wiring you can find e.g.[here](https://diyprojectslab.com/28byj-48-stepper-motor-with-raspberry-pi-pico/) or [here](https://github.com/gavinlyonsrepo/RpiMotorLib/blob/master/Documentation/28BYJ.md).

Finally we need a construction to pan the connected Raspberry Pi Camera with above mentioned step-motor. As solution a Raspberry Pi housing with camera integration support is recommended: we pan the complete Raspberry Pi case.

My 1st prototype is using the [Raspberry Pi 3 case](https://www.raspberrypi.com/products/raspberry-pi-3-case/) with a wide angle camera.
Here is an [image of the PAN camera prototype](https://github.com/irimitenkan/picam2ctrl/blob/main/images/Mounted_Prototype_1.jpg) and some construction details [Mounting_Prototype_1.jpg](https://github.com/irimitenkan/picam2ctrl/blob/main/images/Mounting_Prototype_1.jpg) & [Mounting_Prototype_2.jpg](https://github.com/irimitenkan/picam2ctrl/blob/main/images/Mounting_Prototype_2.jpg)

# HASS-Integration

All picam2ctrl entities will be detected by Home Assistant automatically
by HASS discovery function via configured MQTT broker.

*Known problem*
* When picam2ctrl is started the very first time, all entities do not enter "available state"
 (for some unknown reason, it seems HASS discovery keeps in pending state ?)
* workaround: just stop  and restart picam2ctrl again and restart Home-Assistant, too. Problem disappears after 2nd start. This is reproducible when I delete all picam2ctrl MQTT messages with [MQTT-Explorer](http://mqtt-explorer.com/).
  

## available Home Assistant entities

- picam2ctrl.\< HOSTNAME \>.Snapshot:

  This is a *switch* to enable/disable the picture snapshot function.
  * when [image.snapshots](# Configuration) is set to 0, picam2ctrl takes picture every [image.snapshots_t](# Configuration) seconds in an endless loop, since there is no switch off request
  * when count is set to x>0,  picam2ctrl takes x pictures every .. s  and stops.
  * when [Motion](#Motion) is disabled picture(s) will be taken immediately
  * when [Motion](#Motion) is enabled, picture(s) will be taken only after motion detection
  * when [timestamp](#Configuration) is enabled each picture has a time stamp as configured in json configuration
  * when [[SSHClient]](#Configuration) is enabled the latest taken picture(s) will be copied via secure shell to configured path @SSH server

- picam2ctrl.\< HOSTNAME \>.Video:

  This is a *switch* to enable/disable the video snapshot function.
  * when count is set to x>0,  picam2ctrl takes x pictures every .. s  and stops.
  * when [Motion](#Motion) is disabled picture(s) will be taken immediately
  * when [Motion](#Motion) is enabled, picture(s) will be taken only after motion detection
  * when [timestamp](#Configuration) is enabled each picture has a time stamp as configured in json configuration
  * when [audio](#Configuration) is enabled & available mp4 video file incl. audio stream is created
  * when [SSHClient](#Configuration) is enabled the latest taken video will be copied via secure shell to configured path @SSH server


- picam2ctrl.\< HOSTNAME \>.HttpStream:

  This is a *switch* to enable/disable a simple HTTP Server with MJPEG stream.
  * when [Motion](#Motion) is disabled the MJPEG stream starts immediately
  * when [Motion](#Motion)  is enabled, the MJEP stream starts after motion detection
  * when [timestamp](#Configuration) is enabled the MJPEG stream has a time stamp as configured in json configuration


- picam2ctrl.\< HOSTNAME \>.UdpStream:

  This is a *switch* to enable/disable an UDP video stream.
  * when [Motion](#Motion) is disabled the UDP stream starts immediately
  * when [Motion](#Motion) is enabled, the UDP stream starts after motion detection
  * when [timestamp](#Configuration) is enabled the video stream has a time stamp as configured in json configuration
  * when [audio](#Configuration) is enabled & available the video+audio stream is created

## PAN

- picam2ctrl.\< HOSTNAME \>.Pan-Automation:
  
  This is a *switch* to enable/disable to pan the camera in range from -angle_max to +angle_max automatically.

- picam2ctrl.\< HOSTNAME \>.Pan:
  
  This is a *slider* to pan the camera in range -angle_max to +angle_max manually.

  
## Motion
- picam2ctrl.\< HOSTNAME \>.MotionEnabled:

  This is a *switch* to enable/disable the motion detection.
  * a switch off request deactivates a running function, too
  * when disabled the Motion binary switch is not available in HASS

- picam2ctrl.\< HOSTNAME \>.Motion:

  This is a *binary switch* . It becomes active for ~0.5s if
  * MotionEnabled switch is active
  * and one of the above mentioned functions (streaming, picture/video snapshot) is enabled
  * and a motion has been detected by camera

  *Restrictions*
  Only one switch resp. camera application (HTTPStream, UDPStream, video capturing to file or image snapshots ) can be enabled.
  Since one application is active, switching on requests for other applications are ignored.


# Home Assistant Configuration

configuration.yaml examples for showing camera output in [Home Assistant](https://www.home-assistant.io/):

## UDP Stream

  ```
  camera:
    - platform: ffmpeg
      name: picamera2
      input: 'udp://@:10001'
  ```

## picture snapshots

  ```
  camera:
    - platform: local_file
      name: picamera2
      file_path: /config/tmp/latest/latest1.jpg
  ```

## HTTPServer / MJPEG Stream

- In Home Assistant go to
  * add integration
  * from the list, search and select “MJPEG IP Camera”
  * in MJPEG-URL field enter

  ```
  http://< YOUR_RASPI_ADDRESS >:< CONFIGURED_HTTP_PORT>/stream.mjpg
  ```

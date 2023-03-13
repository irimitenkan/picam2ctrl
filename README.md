# Picam2ctrl
[Overview](#Overview) |
[Features](#features) |
[Installation](#running) |
[Running the MQTT client](#running) |
[Configuration](#Installation) |
[Home Assistant Integration](#Integration) |
[Changelog](https://github.com/)

# Overview

Picam2ctrl is a MQTT client for [Picamera2](https://github.com/raspberrypi/picamera2 ) with [Home Assistant](https://www.home-assistant.io/) discovery support.
More details about the new libcamera-based Python-API for Raspberry Pi camera you can find [here](https://www.raspberrypi.com/documentation/computers/camera_software.html ) .

*General Restriction*

Since [Picamera2](https://github.com/raspberrypi/picamera2) is currently only available as a [beta release](https://github.com/raspberrypi/picamera2#readme) *picam2ctrl* can break with newer *Picamera2* releases.

# Features

 MQTT client to control your Raspberry Pi Camera with [Home Assistant](https://www.home-assistant.io/)

  * taking snapshot pictures
  * capturing MP4 video audio file
  * simple HTTP MJPEG Streaming Server
  * video with audio via UDP streaming
  * motion/occupancy detection by camera

  * timestamp support
  * secure copy latest picture- / video-files to SSH server support

# Installation

First steps see [Picamera2 installation](https://github.com/raspberrypi/picamera2#installation )


OpenCV python-bindings are required:
	
  ```
  apt-get install --no-install-recommends python3-opencv
  ```
		
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
    "motion":false,
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
    }
  }

  ```
	


# running
- to start from terminal
	
  ```
  cd picam2ctrl
  python3 picam2ctrl.py
  ```
	
- to stop it &  started from terminal
	
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
	

# Integration

All picam2ctrl entities will be detected by Home Assistant automatically
by HASS discovery function via configured MQTT broker.

*Known problem*
* When picam2ctrl is started the very first time, all entities do not enter "available state"
 (Due to unknown reason it seems HASS discovery keeps in pending state)
* workaround: just stop  and restart picam2ctrl again.


## available HASS entities



- picam2ctrl.\< HOSTNAME \>.Snapshot:


  This is a switch to enable/disable a picture snapshot function.
  * when [image.snapshots](# Configuration) is set to 0, picam2ctrl takes picture every [image.snapshots_t](# Configuration) seconds in an endless loop, since there is no switch off request
  * when count is set to x>0,  picam2ctrl takes x pictures every .. s  and stops.
  * when [Motion](#Motion) is disabled picture(s) will be taken immediately
  * when [Motion](#Motion) is enabled, picture(s) will be taken only after motion detection
  * when [timestamp](#Configuration) is enabled each picture has a time stamp as configured in json configuration
  * when [timestamp](#Configuration) is enabled the latest taken picture(s) will be copied via secure shell to configured path @SSH server

- picam2ctrl.\< HOSTNAME \>.Video:


  This is a switch to enable/disable a video snapshot function.
  * when count is set to x>0,  picam2ctrl takes x pictures every .. s  and stops.
  * when [Motion](#Motion) is disabled picture(s) will be taken immediately
  * when [Motion](#Motion) is enabled, picture(s) will be taken only after motion detection
  * when [timestamp](#Configuration) is enabled each picture has a time stamp as configured in json configuration
  * when [SSHClient](#Configuration) is enabled the latest taken picture(s) will be copied via secure shell to configured path @SSH server


- picam2ctrl.\< HOSTNAME \>.HttpStream:


  This is a switch to enable/disable a simple HTTP Server with MJPEG stream.
  * when [Motion](#Motion) is disabled the MJPEG stream starts immediately
  * when [Motion](#Motion)  is enabled, the MJEP stream starts after motion detection
  * when [timestamp](#Configuration) is enabled the MJPEG stream has a time stamp as configured in json configuration


- picam2ctrl.\< HOSTNAME \>.UdpStream:


  This is a switch to enable/disable MP4 stream.
  * when [Motion](#Motion) is disabled the UDP stream starts immediately
  * when [Motion](#Motion) is enabled, the UDP stream starts after motion detection
  * when timestamp is enabled the video stream has a time stamp as configured in json configuration
  * when audio is enabled & available the video+audio stream is created

## Motion
- picam2ctrl.\< HOSTNAME \>.MotionEnabled:


  This is a switch to enable/disable the motion detection.
  * a switch off request deactivates a running function, too
  * when disabled the Motion binary switch is not available in HASS

- picam2ctrl.\< HOSTNAME \>.Motion:


  This is a binary switch . It becomes active for ~0.5s if
  * MotionEnabled switch is active
  * and one of the above mentioned functions (streaming, picture/video snapshot) is enabled and
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
  * in MPEG-URL field enter
	
  ```
  http://< YOUR_RASPI_ADDRESS >:< CONFIGURED_HTTP_PORT>/stream.mjpg
  ```
	


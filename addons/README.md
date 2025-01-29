# ADDONS: RTSP server setup

to be used for picam2ctrl's RTSP feature

## [docker](https://www.docker.com/)

* docker installation:
`curl -sLS https://get.docker.com | sh`

## mediaMTX
[project's page](https://github.com/bluenviron/mediamtx#)

**mediaMTX is highly recommended even if you want to stream with picam2ctrl to frigate server resp. go2rtsp **
Actually you'll get an error "*av_interleaved_write_frame() broken pipe*" if you try to stream directly to go2rtsp resp. frigate (which also uses go2rtsp).

**WORKAROUND if you want to use frigate resp go2rtsp and picam2ctrl's RTSP **:

* stream via mediamtx: picam2ctrl (localhost) -> mediamtx (localhost) -> frigate (HOSTX)
* if frigate is running on same host you have to change the mediamtx default listen port 8554 to other port e.g. 8550 or 554.

* docker installation: enter mediamtx folder:
 * optional change 'cert.conf'
 * create server certificate:
`./mkserver_crt.sh`
* and start container:
`sudo docker compose up -d`

## go2rtsp
[project's page](https://github.com/AlexxIT/go2rtc#)


(Docker) installation, please aware of the restriction that actually you can't stream from picam2ctrl to go2rtsp directly,
 see [mediamtx](##mediamtx) for details:
* docker installation: enter mediamtx folder:
 * adapt for your needs `./config/go2rts.yaml`

 ```
streams:
    test:
      - rtsp://[RPI'S ADDRESS with mediamtx runnung]:8554/picamera2

 ```


* and start container:
`sudo docker compose up -d`

## frigate
[project's page](https://github.com/blakeblackshear/frigate#)

* docker installation: enter mediamtx folder:
 * adapt for your needs `./config/config.yaml`

 ```
cameras:
  RaspiZero2W:
    enabled: true
    ffmpeg:
      inputs:
        - path: rtsp://[RPI'S ADDRESS with mediamtx runnung]:8554/picamera2
          roles:
          #  - detect
            - record
 ```


* and start container with
`sudo docker compose up`

to get admin / password in console output.

* after ctrl-c you can restart it again with
`sudo docker compose up -d`

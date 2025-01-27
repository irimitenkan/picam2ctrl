# ADDONS / mediamtx RTSP-Server setup

Required for picam2ctrl's RTSP feature

## Installation 
Installation via docker highly recommended:
* install docker:
`curl -sLS https://get.docker.com | sh`
* in mediamtx folder:optional change cert.conf and create server certificate:
`./mkserver_crt.sh`

* and start container:
`sudo docker compose up -d`

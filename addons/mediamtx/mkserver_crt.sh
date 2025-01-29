#!/bin/bash
openssl genrsa -out ./config/server.key 2048
openssl req -new -x509 -sha256 -key ./config/server.key -out ./config/server.crt -config cert.conf -days 3650
openssl x509 -in ./config/server.crt -noout -text
ls -la  ./config/server.crt

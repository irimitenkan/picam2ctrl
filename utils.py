'''
Created on 09.02.2023

@author: irimi
'''
import json
import threading
import io
import socketserver
import logging
from http import server


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
            result = Config.__load__(json.loads(f.read()))
        return result


class ThreadEvent(threading.Thread):
    """
    helper class to control threads with stop events
    """
    def __init__(self, parent=None):
        threading.Thread.__init__(self)
        self.timeout = None
        self._parent = parent
        self._stopEvent = threading.Event()

    def run(self):
        self._worker_()
        self._stopEvent.wait(self.timeout)
        self._shutdown_()

    def _worker_(self):
        pass

    def _shutdown_(self):
        if self._parent:
            self._parent.child_down(self)

    def child_down(self,child):
        pass

    def trigger_stop(self):
        self._stopEvent.set()

class ThreadEvents(ThreadEvent):
    """
    Simple Multi Thread Events Handler
    """
    def __init__(self):
        self.threads=list()

    def addThread (self, newThread: ThreadEvent):
        newThread.start()
        #self.threads.update({tId, newThread})
        self.threads.append(newThread)
        
    def rmThread (self,rmThread: ThreadEvent ):
        if rmThread in self.threads:
            self.threads.remove(rmThread)
            
    def stopAllThreads(self):
        for t in self.threads:
            t.trigger_stop()

# Mostly copied from
# https://github.com/raspberrypi/picamera2/blob/next/examples/mjpeg_server_2.py
class StreamingOutput(io.BufferedIOBase):
    def __init__(self):
        self.frame = None
        self.condition = threading.Condition()

    def write(self, buf):
        with self.condition:
            self.frame = buf
            self.condition.notify_all()


# Mostly copied from
# https://github.com/raspberrypi/picamera2/blob/next/examples/mjpeg_server_2.py
class StreamingHandler(server.BaseHTTPRequestHandler):
    output = None
    pagefn = None

    def do_GET(self):
        if self.path == '/':
            self.send_response(301)
            self.send_header('Location', '/index.html')
            self.end_headers()
        elif self.path == '/index.html':
            # content = PAGE.encode('utf-8')
            content = self.getPage()
            self.send_response(200)
            self.send_header('Content-Type', 'text/html')
            self.send_header('Content-Length', len(content))
            self.end_headers()
            self.wfile.write(content)
        elif self.path == "/favicon.ico":
            icon = io.open("www/pi_logo.ico", "rb").read()
            self.send_response(200)
            self.send_header('Content-type', 'mage/x-icon')
            self.send_header('Content-length', len(icon))
            self.end_headers()
            self.wfile.write(icon)
        elif self.path == '/stream.mjpg':
            self.send_response(200)
            self.send_header('Age', 0)
            self.send_header('Cache-Control', 'no-cache, private')
            self.send_header('Pragma', 'no-cache')
            self.send_header('Content-Type',
                             'multipart/x-mixed-replace; boundary=FRAME')
            self.end_headers()
            try:
                while True:
                    with StreamingHandler.output.condition:
                        StreamingHandler.output.condition.wait()
                        frame = StreamingHandler.output.frame
                    self.wfile.write(b'--FRAME\r\n')
                    self.send_header('Content-Type', 'image/jpeg')
                    self.send_header('Content-Length', len(frame))
                    self.end_headers()
                    self.wfile.write(frame)
                    self.wfile.write(b'\r\n')
            except Exception as e:
                logging.warning(
                    'Removed streaming client %s: %s',
                    self.client_address, str(e))
        else:
            self.send_error(404)
            self.end_headers()

    def getPage(self):
        try:
            with open(StreamingHandler.pagefn) as f:
                page = f.read()
                f.close()
                PAGE = page.encode('utf-8')

        except OSError as e:
            print(f"ERROR {type(e)}: {e}")
            PAGE = f"<html>ERROR: {e}</html>"

        return PAGE

# Mostly copied from
# https://github.com/raspberrypi/picamera2/blob/next/examples/mjpeg_server_2.py
class StreamingServer(socketserver.ThreadingMixIn, server.HTTPServer):
    allow_reuse_address = True
    daemon_threads = True

    def __init__(self, address, handler, output, pagefn):
        handler.output = output
        handler.pagefn = pagefn
        super().__init__(address, handler)

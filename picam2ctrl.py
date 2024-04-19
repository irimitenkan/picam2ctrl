#!/usr/bin/python3
# encoding: utf-8
'''
picam2ctrl -- Picam2Ctrl MQTT Client

@author:     irimi@gmx.de

@copyright:  irimi@gmx.de - All rights reserved.

@license:    BSD 2-Clause License

@contact:    irimi@gmx.de

'''

import sys
import os

from optparse import OptionParser
from picamclient import startClient

__all__ = []
__version__ = "0.3.0"
__updated__ = '2024-04-19'

def main(argv=None):
    '''Command line options.'''

    program_name = os.path.basename(sys.argv[0])
    program_version = f"v{__version__}"
    program_version_string = f"{program_name} {program_version} {__updated__}"
    program_license = "Copyright 2023 irimi@gmx.de, published under BSD 2-Clause License"

    if argv is None:
        argv = sys.argv[1:]
    # setup option parser
    parser = OptionParser(
        version=program_version_string,
        epilog="your Picamera2 MQTT client for Home Assistant",
        description=program_license)

    parser.add_option(
        "-c",
        "--cfg",
        dest="cfgfile",
        help="set config file [default: %default]",
        metavar="FILE")

    parser.set_defaults(cfgfile="./config.json")
    (opts, _args) = parser.parse_args(argv)

    if opts.cfgfile:
        print("cfgfile = %s" % opts.cfgfile)

    startClient(opts.cfgfile)


if __name__ == "__main__":
    sys.exit(main())

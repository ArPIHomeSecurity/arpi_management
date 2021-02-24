#!/usr/bin/env python
# encoding: utf-8

import fileinput
import sys

from utils import get_repository_version

__version__ = "V0.6.00"


def replace(filename, placeholder, value):
    with fileinput.FileInput(filename, inplace=True) as file:
        for line in file:
            print(line.replace(placeholder, value), end="")


def main():
    server_version = __version__ + ":" + get_repository_version("server")
    webapplication_version = (
        __version__ + ":" + get_repository_version("webapplication")
    )

    print("Server: %s" % server_version)
    print("Webapp: %s" % webapplication_version)

    with open("server/src/server/version.py", "w") as f:
        f.write('__version__="{}"'.format(server_version))

    with open("webapplication/src/app/version.ts", "w") as f:
        f.write('export const VERSION = "{}"'.format(webapplication_version))


if __name__ == "__main__":
    sys.exit(main())

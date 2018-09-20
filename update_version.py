
import fileinput
import subprocess
import sys

from utils import get_repository_version

__version__ = "V0.1"


def replace(filename, placeholder, value):
    with fileinput.FileInput(filename, inplace=True) as file:
        for line in file:
            print(line.replace(placeholder, value), end='')


def main():
    server_version = __version__ + ":" + get_repository_version("server")
    webapplication_version = __version__ + ':' + get_repository_version("webapplication")

    print("Server: %s" % server_version)
    print("Webapp: %s" % webapplication_version)
    return

    replace("server/etc/server.demo.env", '{{SERVER_VERSION}}', server_version)
    replace("server/etc/server.dev.env", '{{SERVER_VERSION}}', server_version)
    replace("server/etc/server.prod.env", '{{SERVER_VERSION}}', server_version)

    replace("webapplication/src/environments/environment.ts", '{{WEBAPPLICATION_VERSION}}', webapplication_version)
    replace("webapplication/src/environments/environment.prod.ts", '{{WEBAPPLICATION_VERSION}}', webapplication_version)


if __name__ == "__main__":
    sys.exit(main())

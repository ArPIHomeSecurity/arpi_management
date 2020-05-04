#!/usr/bin/env python
# encoding: utf-8
"""

Script for installing the components of the ArPI home security system to a running Raspberry PI Zero Wifi host.
It uses the configuration file install.yaml!

---

@author:     Gábor Kovács

@copyright:  2017 argus-security.info. All rights reserved.

@contact:    gkovacs81@gmail.com
"""
import logging
import subprocess
import sys
from argparse import ArgumentParser, RawDescriptionHelpFormatter
from os import path
from os.path import exists, join
from pprint import pformat
from socket import gaierror

import paramiko
import yaml
from paramiko.ssh_exception import (AuthenticationException,
                                    NoValidConnectionsError)
from scp import SCPClient

from utils import (deep_copy, generate_SSH_key, list_copy, print_lines,
                   print_ssh_output, progress, uploaded_files)

CONFIG = {}

logging.basicConfig(format="%(message)s")
logger = logging.getLogger()
logging.getLogger("paramiko").setLevel(logging.CRITICAL)

__all__ = []
__version__ = 0.1
__date__ = "2017-08-21"
__updated__ = "2019-08-21"


def get_connection():
    try:
        logger.info("Connecting with private key in '%s' %s@%s", CONFIG['arpi_key_name'], CONFIG["arpi_username"], CONFIG["arpi_hostname"])

        private_key = None
        if path.exists(CONFIG['arpi_key_name']):
            private_key = paramiko.RSAKey.from_private_key_file(CONFIG['arpi_key_name'], CONFIG['arpi_password'])

        ssh = paramiko.SSHClient()
        ssh.load_system_host_keys()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(CONFIG["arpi_hostname"], username=CONFIG["arpi_username"], password=CONFIG["arpi_password"], pkey=private_key)
        logger.info("Connected")
    except (AuthenticationException, NoValidConnectionsError, gaierror) as error:
        try:
            logger.info("Connecting %s@%s", CONFIG["default_username"], CONFIG["default_hostname"])
            ssh.connect(CONFIG["default_hostname"], username=CONFIG["default_username"], password=CONFIG["default_password"])
            logger.info("Connected")
        except (NoValidConnectionsError, gaierror):
            raise Exception("Can't connect to the host!")

    return ssh


def install_environment():
    """
    Install prerequisites to an empty Raspberry PI.
    """
    if not path.exists(CONFIG['arpi_key_name']) and not path.exists(CONFIG['arpi_key_name'] + ".pub"):
        generate_SSH_key(CONFIG['arpi_key_name'], CONFIG['arpi_password'])

    ssh = get_connection()

    # create the env variables string because paramiko update_evironment ignores them
    arguments = {
        "ARGUS_DB_SCHEMA": CONFIG["argus_db_schema"],
        "ARGUS_DB_USERNAME": CONFIG["argus_db_username"],
        "ARGUS_DB_PASSWORD": CONFIG["argus_db_password"],
    }
    arguments = [f"export {key}={value}" for key, value in arguments.items()]
    arguments = "; ".join(arguments)

    scp = SCPClient(ssh.get_transport(), progress=progress)
    scp.put("scripts/install_environment.sh", remote_path=".")
    deep_copy(ssh, join(CONFIG["server_path"], "etc"), "/tmp/etc", "**/*")

    channel = ssh.get_transport().open_session()
    channel.get_pty()
    channel.set_combine_stderr(True)
    output = channel.makefile("r", -1)

    logger.info("Starting install script...")
    channel.exec_command(f"{arguments}; ./install_environment.sh")
    print_lines(output)
    ssh.close()

    # waiting for user
    # 1. deploy key can timeout
    # 2. ssh accept password only from terminal
    input(f"Waiting before deploying public key. Use the password: '{CONFIG['arpi_password']}'!")
    command = f"ssh-copy-id -i {CONFIG['arpi_key_name']} {CONFIG['arpi_username']}@{CONFIG['arpi_hostname']}"
    logger.info("Deploy public key: %s", command)
    subprocess.call(command, shell=True)

    ssh = get_connection()
    logger.info("Enabling key based ssh authentication")
    _, stdout, stderr = ssh.exec_command("sudo sed -i -E -e 's/.*PasswordAuthentication (yes|no)/PasswordAuthentication no/g' /etc/ssh/sshd_config")
    print_ssh_output(stdout, stderr)

    logger.info("Restarting the host")
    _, stdout, stderr = ssh.exec_command("sudo reboot")
    print_ssh_output(stdout, stderr)


def install_server():
    """
    Install the server component to a Raspberry PI.
    """
    ssh = get_connection()
    logger.info("Creating server directories...")
    _, stdout, stderr = ssh.exec_command("mkdir -p  server/scripts; mkdir -p server/etc; mkdir -p server/webapplication")
    print_ssh_output(stdout, stderr)

    list_copy(ssh, (
        (join(CONFIG["server_path"], "requirements.txt"), "server"),
        (join(CONFIG["server_path"], "scripts/update_database_data.sh"), "server/scripts"),
        (join(CONFIG["server_path"], "scripts/update_database_struct.sh"), "server/scripts"),
        (join(CONFIG["server_path"], "scripts/start_monitor.sh"), "server/scripts"),
        (join(CONFIG["server_path"], "scripts/stop_monitor.sh"), "server/scripts"),
        (join(CONFIG["server_path"], "scripts/start_server.sh"), "server/scripts"),
        (join(CONFIG["server_path"], "scripts/install.sh"), "server/scripts"),
        (join(CONFIG["server_path"], "etc/common.prod.env"), "server/etc"),
        (join(CONFIG["server_path"], "etc/server.prod.env"), "server/etc"),
        (join(CONFIG["server_path"], "etc/monitor.prod.env"), "server/etc"),
        (join(CONFIG["server_path"], "etc/secrets.env"), "server/etc")
    ))
    logger.debug("%-80s\n%s", "Files copied:", pformat(uploaded_files))
    uploaded_files.clear()

    deep_copy(ssh, join(CONFIG["server_path"], "src"), join("server", "src"), "**/*.py")

    logger.debug("Files:\n%s" % pformat(uploaded_files))
    uploaded_files.clear()

    logger.info("Starting install script...")
    _, stdout, stderr = ssh.exec_command("cd server; source ./etc/common.prod.env; ./scripts/install.sh")
    print_ssh_output(stdout, stderr)

    ssh.close()


def install_database():
    """
    Install the database component to a Raspberry PI.
    """
    ssh = get_connection()

    logger.info("Updating database structure...")
    _, stdout, stderr = ssh.exec_command(f"cd server; ./scripts/update_database_struct.sh {CONFIG['argus_db_environment']}")
    print_ssh_output(stdout, stderr)

    logger.info("Updating database content...")
    _, stdout, stderr = ssh.exec_command(f"cd server; ./scripts/update_database_data.sh {CONFIG['argus_db_environment']} {CONFIG['argus_db_content']}")
    print_ssh_output(stdout, stderr)

    ssh.close()


def install_webapplication():
    """
    Install the web application component to a Raspberry PI.
    """
    ssh = get_connection()

    logger.info("Delete old webapplication on remote site...")
    _, stdout, stderr = ssh.exec_command("rm -R server/webapplication || true")
    print_ssh_output(stdout, stderr)

    scp = SCPClient(ssh.get_transport(), progress=progress)
    scp.put(join(CONFIG["webapplication_path"]), remote_path=join("server", "webapplication"), recursive=True)
    logger.info("Files: %s" % pformat(uploaded_files))
    uploaded_files.clear()

    scp = SCPClient(ssh.get_transport(), progress=progress)
    scp.put(join(CONFIG["webapplication_path"], "hu"), remote_path=join("server", "webapplication", "hu"), recursive=True)
    logger.info("Files: %s" % pformat(uploaded_files))
    uploaded_files.clear()


def main(argv=None):  # IGNORE:C0111
    """Command line options."""

    if argv is None:
        argv = sys.argv
    else:
        sys.argv.extend(argv)

    program_shortdesc = __import__("__main__").__doc__.split("---")[0]
    program_license = """%s

  Created by gkovacs81@gmail.com on %s.
  Copyright 2019 arpi-security.info. All rights reserved.

USAGE
""" % (
        program_shortdesc,
        str(__date__),
    )

    try:
        # Setup argument parser
        parser = ArgumentParser(description=program_license, formatter_class=RawDescriptionHelpFormatter)
        # parser.add_argument("-r", "--recursive", dest="recurse", action="store_true", help="recurse into subfolders [default: %(default)s]")
        parser.add_argument("-v", "--verbose", dest="verbose", action="count", help="set verbosity level [default: %(default)s]")
        # parser.add_argument('-V', '--version', action='version', version=program_version_message)
        # parser.add_argument(dest="action", help="install", metavar="action")
        parser.add_argument("component", choices=["environment", "server", "webapplication", "database"])
        parser.add_argument("-e", "--env", dest="environment", default="", help="Select a different config (install.{environment}.yaml)")

        # Process arguments
        args = parser.parse_args()
        if args.verbose:
            logger.setLevel(logging.DEBUG)
            logger.info("Verbose mode on")
        else:
            logger.setLevel(logging.INFO)

        config_filename = __file__.replace(".py", ".yaml")
        if args.environment:
            config_filename = config_filename.replace(".yaml", "." + args.environment + ".yaml")

        logger.info("Working from %s", config_filename)

        with open(config_filename, "r") as stream:
            global CONFIG
            CONFIG = yaml.load(stream, Loader=yaml.FullLoader)
            logger.info("Working with configuration: \n%s", pformat(CONFIG))

        if args.component == "environment":
            install_environment()
        elif args.component == "server":
            install_server()
        elif args.component == "webapplication":
            install_webapplication()
        elif args.component == "database":
            install_database()
        return 0
    except KeyboardInterrupt:
        # handle keyboard interrupt ###
        return 0
    except Exception:
        logger.exception("Failed to execute!")
        return 2

    logger.info("Finished successfully!")


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python
# encoding: utf-8
"""

Script for installing the components of the ArPI home security system to a running Raspberry PI Zero Wifi host.

It uses the configuration file install/[_<environment>].yaml!

---

@author:     Gábor Kovács

@copyright:  2017 arpi-security.info. All rights reserved.

@contact:    gkovacs81@gmail.com
"""

import json
import logging
import subprocess
import sys
from argparse import ArgumentParser, RawDescriptionHelpFormatter
from os import system
from os.path import basename, exists, join
from socket import gaierror
from time import sleep

import paramiko
import yaml
from paramiko.ssh_exception import (
    AuthenticationException,
    NoValidConnectionsError
)
from scp import SCPClient

from utils import (
    deep_copy,
    execute_remote,
    generate_SSH_key,
    list_copy,
    print_lines,
    show_progress
)

CONFIG = {}


class ConnectionError(Exception):
    """
    Thrown when we can't connect to the remote host.
    """
    pass


logging.basicConfig(format="%(message)s")
logger = logging.getLogger()
logging.getLogger("paramiko").setLevel(logging.CRITICAL)

__all__ = []
__version__ = 0.1
__date__ = "2017-08-21"
__updated__ = "2019-08-21"
program_shortdesc = __import__("__main__").__doc__.split("---")[0]
program_license = f"""{program_shortdesc}

  Created by gkovacs81@gmail.com on {__date__}.
  Copyright 2019 arpi-security.info. All rights reserved.

USAGE
"""


def get_connection():
    try:
        logger.info(
            "Connecting with private key in '%s' %s@%s",
            CONFIG["arpi_key_name"],
            CONFIG["arpi_username"],
            CONFIG["arpi_hostname"],
        )

        private_key = None
        if exists(CONFIG["arpi_key_name"]):
            private_key = paramiko.RSAKey.from_private_key_file(
                CONFIG["arpi_key_name"], CONFIG["arpi_password"]
            )

        ssh = paramiko.SSHClient()
        ssh.load_system_host_keys()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(
            CONFIG["arpi_hostname"],
            username=CONFIG["arpi_username"],
            password=CONFIG["arpi_password"],
            pkey=private_key,
        )
        logger.info("Connected")
    except (AuthenticationException, NoValidConnectionsError, gaierror):
        try:
            logger.info("Connecting %s@%s", CONFIG["default_username"], CONFIG["default_hostname"])
            ssh.connect(
                CONFIG["default_hostname"],
                username=CONFIG["default_username"],
                password=CONFIG["default_password"],
            )
            logger.info("Connected")
        except (AuthenticationException, NoValidConnectionsError, gaierror) as error:
            raise ConnectionError("Can't connect to the host: %s" % error) from error

    return ssh


def install_environment():
    """
    Install prerequisites to an empty Raspberry PI.
    """

    # generate SSH key if the name is defined but it doesn't exist
    if CONFIG["arpi_key_name"]:
        if not exists(CONFIG["arpi_key_name"]) and not exists(CONFIG["arpi_key_name"] + ".pub"):
            generate_SSH_key(CONFIG["arpi_key_name"], CONFIG["arpi_password"])

    dhparam_file = "arpi_dhparam.pem"
    if not exists(dhparam_file):
        logger.info("dhparam (%s) generating", dhparam_file)
        system(f"openssl dhparam -out {dhparam_file} {CONFIG['dhparam_size']}")
    else:
        logger.info("dhparam (%s) already exists", dhparam_file)
        system(f"openssl dhparam -in {dhparam_file} -text | head -3")

    # create the env variables string because paramiko update_environment ignores them
    arguments = {
        "ARPI_PASSWORD": CONFIG["arpi_password"],
        "ARGUS_DB_SCHEMA": CONFIG["argus_db_schema"],
        "ARGUS_DB_USERNAME": CONFIG["argus_db_username"],
        "ARGUS_DB_PASSWORD": CONFIG["argus_db_password"],
        "ARPI_HOSTNAME": CONFIG["arpi_hostname"],
        "DHPARAM_FILE": join("/tmp", dhparam_file),
        # progress
        "QUIET": "" if CONFIG["progress"] else "-q",
        "PROGRESS": "on" if CONFIG["progress"] else "off"
    }

    # adding package versions
    arguments.update({p.upper(): f"{v}" for p, v in CONFIG["packages"].items() if v})

    arguments = [f"export {key}={value}" for key, value in arguments.items()]
    arguments = "; ".join(arguments)

    ssh = get_connection()
    scp = SCPClient(ssh.get_transport(), progress=show_progress if CONFIG["progress"] else None)
    scp.put("scripts/install_environment.sh", remote_path=".")
    deep_copy(ssh, join(CONFIG["server_path"], "etc"), "/tmp/etc", "**/*", CONFIG["progress"])
    list_copy(
        ssh,
        (
            (dhparam_file, "/tmp"),
            ("manage_versions.py", "~")
        ),
        CONFIG["progress"]
    )

    channel = ssh.get_transport().open_session()
    channel.get_pty()
    channel.set_combine_stderr(True)
    output = channel.makefile("r", -1)

    logger.info("Starting install script...")
    channel.exec_command(f"{arguments}; ./install_environment.sh")
    print_lines(output)

    if CONFIG["arpi_key_name"] and CONFIG['deploy_ssh_key']:
        # waiting for user
        # 1. deploy key can timeout
        # 2. ssh accept password only from terminal
        input("Waiting before deploying public key!")
        command = f"ssh-copy-id -i {CONFIG['arpi_key_name']} {CONFIG['arpi_username']}@{CONFIG['default_hostname']}"
        logger.info("Deploy public key: %s", command)
        while subprocess.call(command, shell=True) != 0:
            # retry after 2 seconds
            sleep(2)

    if CONFIG["arpi_key_name"] and CONFIG['disable_ssh_password_authentication']:
        execute_remote(
            message="Switching to key based ssh authentication",
            ssh=ssh,
            command="sudo sed -i -E -e 's/.*PasswordAuthentication (yes|no)/PasswordAuthentication no/g' /etc/ssh/sshd_config",
        )

    # restart the host to activate the user
    execute_remote(message="Restarting the host", ssh=ssh, password="argus1", command="sudo reboot")

    retry = 0
    ssh.close()
    ssh = None
    while not ssh:
        sleep(5)
        try:
            ssh = get_connection()
        except ConnectionError:
            if retry > 10:
                logger.warn("Failed to connect to SSH server")
                retry += 1
                break

    if ssh:
        execute_remote(
            message="Delete default user...",
            ssh=ssh,
            password=CONFIG["arpi_password"],
            command=f"sudo deluser {CONFIG['default_username']}"
        )
        execute_remote(
            message="Delete default user home folder...",
            ssh=ssh,
            password=CONFIG["arpi_password"],
            command=f"sudo rm -rf /home/{CONFIG['default_username']}"
        )

    logger.info("Finished installing environment")

def install_component(component, update=False, restart=False):
    """
    Install the monitor component to a Raspberry PI.
    """
    ssh = get_connection()

    execute_remote(
        message="Creating server directories...",
        ssh=ssh,
        command="mkdir -p  server/etc server/scripts server/src webapplication",
    )

    logger.info("Copy common files...")
    list_copy(
        ssh,
        (
            (join(CONFIG["server_path"], "Pipfile"), "server"),
            (join(CONFIG["server_path"], "Pipfile.lock"), "server"),
            (join(CONFIG["server_path"], f"{CONFIG['environment']}.env"), "server/.env"),
            (join(CONFIG["server_path"], "src", "data.py"), join("server", "src", "data.py")),
            (join(CONFIG["server_path"], "src", "constants.py"), join("server", "src", "constants.py")),
            (join(CONFIG["server_path"], "src", "hash.py"), join("server", "src", "hash.py")),
            (join(CONFIG["server_path"], "src", "models.py"), join("server", "src", "models.py")),
            (join(CONFIG["server_path"], "src", "new_registration_code.py"), join("server", "src", "new_registration_code.py")),
            (join(CONFIG["server_path"], "src", "tester.py"), join("server", "src", "tester.py")),
        ), CONFIG["progress"]
    )
    deep_copy(
        ssh, join(CONFIG["server_path"], "src", "tools"), join("server", "src", "tools"), "**/*.py", CONFIG["progress"]
    )

    logger.info("Copy component '%s'...", component)
    deep_copy(
        ssh,
        join(CONFIG["server_path"], "src", component),
        join("server", "src", component),
        "**/*.py",
        CONFIG["progress"]
    )

    if CONFIG["deploy_simulator"]:
        list_copy(
            ssh,
            (
                (join(CONFIG["server_path"], "src", "simulator.py"), join("server", "src", "simulator.py")),
                (join(CONFIG["server_path"], "channels.json"), join("server", "channels.json")),
                (join(CONFIG["server_path"], "power.json"), join("server", "power.json")),
            ), CONFIG["progress"]
        )

    if update:
        execute_remote(
            message="Install python packages to system...",
            ssh=ssh,
            password=CONFIG["arpi_password"],
            command=f"cd server; sudo PIPENV_TIMEOUT=9999 CI=1 pipenv install {'--dev' if CONFIG['deploy_simulator'] else ''} --system",
        )

    if restart:
        execute_remote(
            message="Restarting the service...",
            ssh=ssh,
            password=CONFIG["arpi_password"],
            command="sudo systemctl restart argus_monitor.service argus_server.service",
        )

    ssh.close()


def install_server(update=False, restart=False):
    """
    Install the server component to a Raspberry PI.
    """
    install_component("server", update=update, restart=restart)


def install_monitoring(update=False, restart=False):
    """
    Install the monitor component to a Raspberry PI.
    """
    install_component("monitoring", update=update, restart=restart)


def install_database():
    """
    Install the database component to a Raspberry PI.
    """
    ssh = get_connection()

    execute_remote(
        message="Initialize database...",
        ssh=ssh,
        command="cd server; export $(grep -v '^#' .env | xargs -d '\\n'); flask db init",
    )
    execute_remote(
        message="Migrate database...",
        ssh=ssh,
        command="cd server; export $(grep -v '^#' .env | xargs -d '\\n'); flask db migrate",
    )
    execute_remote(
        message="Upgrade database...",
        ssh=ssh,
        command="cd server; export $(grep -v '^#' .env | xargs -d '\\n'); flask db upgrade",
    )

    execute_remote(
        message="Updating database content...",
        ssh=ssh,
        command=f"cd server; src/data.py -d -c {CONFIG['argus_db_content']}",
    )

    ssh.close()


def install_webapplication(restart=False):
    """
    Install the web application component to a Raspberry PI.
    """
    ssh = get_connection()

    execute_remote(
        message="Delete old webapplication on remote site...",
        ssh=ssh,
        command="rm -R webapplication || true",
    )

    target = "webapplication"
    logger.info("Copy web application: %s => %s", CONFIG["webapplication_path"], target)
    deep_copy(ssh, CONFIG["webapplication_path"], target, "**/*", CONFIG["progress"])

    if restart:
        execute_remote(
            message="Restarting the service...",
            ssh=ssh,
            command="sudo systemctl restart nginx.service",
        )


def main(argv=None):  # IGNORE:C0111
    """Command line options."""

    if argv is None:
        argv = sys.argv
    else:
        sys.argv.extend(argv)

    try:
        # Setup argument parser
        parser = ArgumentParser(
            description=program_license, formatter_class=RawDescriptionHelpFormatter
        )
        parser.add_argument(
            "-v",
            "--verbose",
            dest="verbose",
            action="store_const",
            const=logging.DEBUG,
            default=logging.INFO,
            help="Verbose output",
        )
        parser.add_argument(
            "component",
            choices=["environment", "server", "monitoring", "webapplication", "database"],
        )
        parser.add_argument(
            "-e",
            "--env",
            dest="environment",
            default="",
            required=True,
            help="Select a different config (install/{environment}.yaml)",
        )
        parser.add_argument(
            "-r",
            "--restart",
            action="store_true",
            help="Restart depending service(s) after deployment",
        )
        parser.add_argument(
            "-u",
            "--update",
            action="store_true",
            help="Update the python environment for the depending service(s) after deployment",
        )
        parser.add_argument(
            "-p",
            "--progress",
            action="store_true",
            help="Show progress bars",
        )

        # Process arguments
        args = parser.parse_args()
        logger.setLevel(args.verbose)

        config_filename = join(basename(__file__).replace(".py", ""), f"{args.environment}.yaml")

        logger.info("Working with %s", args)
        logger.info("Working from %s", config_filename)

        with open(config_filename, "r") as stream:
            global CONFIG
            CONFIG = yaml.load(stream, Loader=yaml.FullLoader)
            CONFIG["progress"] = args.progress
            logger.info("Working with configuration: \n%s", json.dumps(CONFIG, indent=4, sort_keys=True))
            input("Waiting before starting the installation to verify the configuration!")

        if args.component == "environment":
            install_environment()
        elif args.component == "server":
            install_server(args.update, args.restart)
        elif args.component == "monitoring":
            install_monitoring(args.update, args.restart)
        elif args.component == "webapplication":
            install_webapplication(args.restart)
        elif args.component == "database":
            install_database()
        else:
            logger.error("Unknown component: %s", args.component)

        logger.info("Finished successfully!")
        return 0
    except ConnectionError as error:
        logger.warning("Unable to connect to device! %s", error)
    except KeyboardInterrupt:
        # handle keyboard interrupt ###
        logger.info("\n\nCancelled!\n")
        return 0
    except Exception:
        logger.exception("Failed to execute!")
        return 2


if __name__ == "__main__":
    sys.exit(main())

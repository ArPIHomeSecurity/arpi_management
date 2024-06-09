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
from paramiko.ssh_exception import SSHException
from scp import SCPClient

from install_utils import (
    deep_copy,
    execute_remote,
    generate_SSH_key,
    list_copy,
    print_lines,
    show_progress
)


class SSHConnectionError(Exception):
    """
    Thrown when we can't connect to the remote host.
    """


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


def get_default_connection(access):
    """
    Returns the connection to the remote host
    """
    try:
        ssh = paramiko.SSHClient()
        logger.info("Connecting %s@%s with %s", access["username"], access["hostname"], access["password"])
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(
            hostname=access["hostname"],
            port=access.get("port", 22),
            username=access["username"],
            password=access["password"]
        )
        logger.info("Connected")
    except (SSHException, gaierror) as error:
        raise SSHConnectionError(f"Can't connect to the host: {error}") from error

    return ssh


def get_arpi_connection(access):
    """
    Returns the connection to the remote host
    """
    try:
        if access.get("key_name", "") and exists(access.get("key_name", "")):
            logger.info(
                "Connecting with private key '%s' %s@%s:%s",
                access.get("key_name", "-"),
                access["username"],
                access["hostname"],
                access.get("port", 22)
            )
        elif access.get("key_name", "") == "":
            logger.info(
                "Connecting with password %s@%s:%s",
                access["username"],
                access["hostname"],
                access.get("port", 22)
            )

        private_key = None
        if exists(access.get("key_name", "")):
            try:
                private_key = paramiko.RSAKey.from_private_key_file(
                    access.get("key_name", ""), access["password"]
                )
                logger.info("RSA key loaded")
            except SSHException:
                private_key = paramiko.Ed25519Key.from_private_key_file(
                    access.get("key_name", ""), access["password"]
                )
                logger.info("Ed25519 key loaded")

        ssh = paramiko.SSHClient()
        ssh.load_system_host_keys()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(
            hostname=access["hostname"],
            port=access.get("port", 22),
            username=access["username"],
            password=access["password"],
            pkey=private_key,
        )
        logger.info("Connected")
    except (SSHException, gaierror) as error:
        raise SSHConnectionError(f"Can't connect to the host: {error}") from error

    return ssh


def install_environment(default_access, arpi_access, database, deployment, progress=False):
    """
    Install prerequisites to an empty Raspberry PI.
    """

    # generate SSH key if the name is defined but it doesn't exist
    if (
        arpi_access.get("key_name", "")
        and not exists(arpi_access.get("key_name", ""))
        and not exists(arpi_access.get("key_name", "") + ".pub")
    ):
        generate_SSH_key(arpi_access.get("key_name", ""), arpi_access["password"])

    dhparam_file = "arpi_dhparam.pem"
    if not exists(dhparam_file):
        logger.info("dhparam (%s) generating", dhparam_file)
        system(f"openssl dhparam -out {dhparam_file} {deployment['dhparam_size']}")
    else:
        logger.info("dhparam (%s) already exists", dhparam_file)
        system(f"openssl dhparam -in {dhparam_file} -text | head -3")

    # create the env variables string because paramiko update_environment ignores them
    arguments = {
        "ARPI_PASSWORD": arpi_access["password"],
        "ARGUS_DB_SCHEMA": database["schema"],
        "ARGUS_DB_USERNAME": database["username"],
        "ARGUS_DB_PASSWORD": database.get("password", ""),
        "ARPI_HOSTNAME": arpi_access["hostname"],
        "DHPARAM_FILE": join("/tmp", dhparam_file),
        "SALT": deployment["salt"],
        "SECRET": deployment["secret"],
        # progress
        "QUIET": "" if progress else "-q",
        "PROGRESS": "on" if progress else "off"
    }

    # adding package versions
    arguments.update({p.upper(): f"{v}" for p, v in deployment["packages"].items() if v})

    arguments = [f"export {key}={value}" for key, value in arguments.items()]
    arguments = "; ".join(arguments)

    ssh = get_default_connection(default_access)
    scp = SCPClient(ssh.get_transport(), progress=show_progress if progress else None)
    scp.put("scripts/install_environment.sh", remote_path=".")
    deep_copy(ssh, join("server", "etc"), "/tmp/etc", "**/*", progress)
    list_copy(
        ssh,
        (
            (dhparam_file, "/tmp"),
            ("manage_versions.py", "~")
        ),
        progress
    )

    channel = ssh.get_transport().open_session()
    channel.get_pty()
    channel.set_combine_stderr(True)
    output = channel.makefile("r", -1)

    logger.info("Starting install script...")
    channel.exec_command(f"{arguments}; ./install_environment.sh")
    print_lines(output)

    if arpi_access.get("key_name", "") and arpi_access['deploy_ssh_key']:
        # waiting for user
        # 1. deploy key can timeout
        # 2. ssh accept password only from terminal
        input("Waiting before deploying public key!")
        command = f"ssh-copy-id -i {arpi_access.get('key_name', '')} {arpi_access['username']}@{default_access['hostname']}"
        logger.info("Deploy public key: %s", command)
        while subprocess.call(command, shell=True) != 0:
            # retry after 2 seconds
            sleep(2)

    if arpi_access.get("key_name", "") and arpi_access['disable_ssh_password_authentication']:
        execute_remote(
            message="Switching to key based ssh authentication",
            ssh=ssh,
            command="sudo sed -i -E -e 's/.*PasswordAuthentication (yes|no)/PasswordAuthentication no/g' /etc/ssh/sshd_config",
        )

    # restart the host to activate the user
    execute_remote(message="Restarting the host", ssh=ssh, password=arpi_access["password"], command="sudo reboot")

    retry = 0
    ssh.close()
    ssh = None
    while not ssh:
        sleep(5)
        try:
            ssh = get_arpi_connection(arpi_access)
        except SSHConnectionError:
            if retry > 20:
                logger.warning("Failed to connect to SSH server")
                retry += 1
                break

    if ssh:
        execute_remote(
            message="Delete default user...",
            ssh=ssh,
            password=arpi_access["password"],
            command=f"sudo deluser {default_access['username']}"
        )
        execute_remote(
            message="Delete default user home folder...",
            ssh=ssh,
            password=arpi_access["password"],
            command=f"sudo rm -rf /home/{default_access['username']}"
        )

    logger.info("Finished installing environment")


def install_component(arpi_access, deployment, component, update=False, restart=False, progress=False):
    """
    Install the monitor component to a Raspberry PI.
    """
    ssh = get_arpi_connection(arpi_access)

    execute_remote(
        message="Creating server directories...",
        ssh=ssh,
        command="mkdir -p  server/etc server/scripts server/src webapplication",
    )

    logger.info("Copy common files...")
    list_copy(
        ssh,
        (
            (join("server", "Pipfile"), "server"),
            (join("server", "Pipfile.lock"), "server"),
            (join("server", f"{deployment['server_environment']}.env"), "server/.env"),
            (join("server", "src", "data.py"), join("server", "src", "data.py")),
            (join("server", "src", "constants.py"), join("server", "src", "constants.py")),
            (join("server", "src", "hash.py"), join("server", "src", "hash.py")),
            (join("server", "src", "models.py"), join("server", "src", "models.py")),
            (join("server", "src", "new_registration_code.py"), join("server", "src", "new_registration_code.py")),
            (join("server", "src", "tester.py"), join("server", "src", "tester.py")),
        ), progress
    )
    deep_copy(
        ssh, join("server", "src", "tools"), join("server", "src", "tools"), "**/*.py", progress
    )

    logger.info("Copy component '%s'...", component)
    deep_copy(
        ssh,
        join("server", "src", component),
        join("server", "src", component),
        "**/*.py",
        progress
    )

    if deployment["deploy_simulator"]:
        list_copy(
            ssh,
            (
                (join("server", "src", "simulator.py"), join("server", "src", "simulator.py")),
            ), progress
        )

    if update:
        execute_remote(
            message="Install python packages to system...",
            ssh=ssh,
            password=arpi_access["password"],
            command=f"cd server; sudo PIPENV_TIMEOUT=9999 CI=1 pipenv install {'--dev' if deployment['deploy_simulator'] else ''} --system",
        )

    if restart:
        execute_remote(
            message=f"Restarting the '{component}' service...",
            ssh=ssh,
            password=arpi_access["password"],
            command=f"sudo systemctl restart argus_{component}.service",
        )

    ssh.close()


def install_server(arpi_access, deployment, update=False, restart=False, progress=False):
    """
    Install the server component to a Raspberry PI.
    """
    install_component(arpi_access, deployment, "server", update=update, restart=restart, progress=progress)


def install_monitor(arpi_access, deployment, update=False, restart=False, progress=False):
    """
    Install the monitor component to a Raspberry PI.
    """
    install_component(arpi_access, deployment, "monitor", update=update, restart=restart, progress=progress)


def install_database(arpi_access, database, update=False, progress=False):
    """
    Install the database component to a Raspberry PI.
    """
    ssh = get_arpi_connection(arpi_access)

    logger.info("Copy migrations...")
    deep_copy(
        ssh,
        join("server", "migrations"),
        join("server", "migrations"),
        "**/*",
        progress
    )

    execute_remote(
        message="Upgrade database...",
        ssh=ssh,
        command="""cd server; \
            export $(grep -hv '^#' .env secrets.env | sed 's/\"//g' | xargs -d '\\n'); \
            printenv; \
            flask --app server:app db upgrade
        """
    )

    if update:
        execute_remote(
            message="Updating database content...",
            ssh=ssh,
            command=f"cd server; src/data.py -d -c {database['content']}",
        )

    ssh.close()


def install_webapplication(arpi_access, deployment, restart=False, progress=False):
    """
    Install the web application component to a Raspberry PI.
    """
    ssh = get_arpi_connection(arpi_access)

    execute_remote(
        message="Delete old webapplication on remote site...",
        ssh=ssh,
        command="rm -R webapplication || true",
    )

    target = "webapplication"
    logger.info("Copy web application: %s => %s", deployment["webapplication_path"], target)
    deep_copy(ssh, deployment["webapplication_path"], target, "**/*", progress)

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
            choices=["environment", "server", "monitor", "database", "webapplication"],
        )
        parser.add_argument(
            "-e",
            "--env",
            dest="environment",
            default="install",
            required=True,
            help="Select a different config (install/{environment}.yaml) default:environment=install",
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

        # name of the folder is the same as the name of the script
        # the name of the file is the environment argument
        config_filename = join(basename(__file__).replace(".py", ""), f"{args.environment}.yaml")

        logger.info("Working with %s", args)
        logger.info("Working from %s", config_filename)

        config = {}
        with open(config_filename, "r", encoding="utf-8") as stream:
            config = yaml.load(stream, Loader=yaml.FullLoader)
            logger.info("Working with configuration: \n%s", json.dumps(config, indent=4, sort_keys=True))
            input("Waiting before starting the installation to verify the configuration!")

        if args.component == "environment":
            install_environment(config["default_access"], config["arpi_access"], config["database"], config["deployment"], args.progress)
        elif args.component == "server":
            install_server(config["arpi_access"], config["deployment"], args.update, args.restart, args.progress)
        elif args.component == "monitor":
            install_monitor(config["arpi_access"], config["deployment"], args.update, args.restart, args.progress)
        elif args.component == "webapplication":
            install_webapplication(config["arpi_access"], config["deployment"], args.restart)
        elif args.component == "database":
            install_database(config["arpi_access"], config["database"], args.update, args.progress)
        else:
            logger.error("Unknown component: %s", args.component)

        logger.info("Finished successfully!")
        return 0
    except SSHConnectionError as error:
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

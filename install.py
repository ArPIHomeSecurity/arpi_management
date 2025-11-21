#!/usr/bin/env python3
# encoding: utf-8
"""

This script installs components of the ArPI home security system onto a running Raspberry Pi Zero Wifi host.

It uses SSH for communicating with the target device, leveraging the user's SSH configuration for accessing hosts.
The script reads deployment settings from a YAML configuration file located at install/[<environment>].yaml.

Main features:
- Prepares the target device by installing required Python packages.
- Deploys and installs the server component, including code synchronization and environment setup.
- Installs the web application component.
- Optionally restarts relevant services after deployment.
- Provides verbose logging and configuration verification before installation.

---

@author:     Gábor Kovács

@copyright:  2017 arpi-security.info. All rights reserved.

@contact:    gkovacs81@gmail.com
"""

import json
import logging
import os
import sys
from argparse import ArgumentParser, RawDescriptionHelpFormatter
from os import system
from os.path import basename, join

import yaml

from helpers.install_utils import SSHConnectionError, execute_remote, get_ssh_connection
from helpers.syncer import SshFileSyncer


# write logs to stdout for tee to a file
logging.basicConfig(format="%(message)s", stream=sys.stdout)
logger = logging.getLogger()
logging.getLogger("paramiko").setLevel(logging.CRITICAL)

__all__ = []
__version__ = 0.1
__date__ = "2017-08-21"
__updated__ = "2025-10-04"
program_shortdesc = __import__("__main__").__doc__.split("---")[0]
program_license = f"""{program_shortdesc}

  Created by gkovacs81@gmail.com on {__date__}.
  Copyright 2019 arpi-security.info. All rights reserved.

USAGE
"""


def install_server(arpi_access, database, deployment, prepare=False, deploy=False, install_environment=False, restart=False):
    """
    Install the monitor component to a Raspberry PI.
    """
    password = arpi_access.get("password")
    ssh = get_ssh_connection(arpi_access["hostname"], password)
    syncer = SshFileSyncer(ssh, progress=True)

    if prepare:
        execute_remote(
            message="Install pipenv and click...",
            ssh=ssh,
            command="sudo apt-get update && sudo apt-get install -y pipenv python3-click",
        )

    if deploy:
        # compress the server folder
        logger.info("Compressing server folder...")

        # Remove existing compressed file if it exists
        package_path = "server/server.tar.gz"
        if os.path.exists(package_path):
            os.remove(package_path)

        system(f"server/create_package.sh {deployment['server_environment']} server")

        logger.info("Copying server %s to folder...", package_path)
        syncer.list_copy(
            [
                (package_path, "/tmp/server.tar.gz"),
            ]
        )

        logger.info("List of additional files:")
        for file_path in syncer.list_additional_files:
            logger.info("  %s", file_path)
        logger.info("Synced files statistics: %s", syncer.get_statistics())


        execute_remote(
            message="Decompressing server files...",
            ssh=ssh,
            command=(
                "sudo rm -rf /tmp/server || true; "
                "mkdir -p /tmp/server && "
                "tar -xzf /tmp/server.tar.gz -C /tmp/server"
            ),
        )

        install_config = {
            "PYTHONPATH": "src",
            "INSTALL_SOURCE": "/tmp/server",
            "DATA_SET_NAME": database.get("content", ""),
            "DEPLOY_SIMULATOR": deployment.get("deploy_simulator", "false"),
        }

        if "board_version" in deployment:
            install_config["BOARD_VERSION"] = str(deployment["board_version"])

        # deploy source code
        execute_remote(
            message="Running full install script...",
            ssh=ssh,
            command="cd /tmp/server; "
            f"sudo {' '.join(f'{key}={value}' for key, value in install_config.items())} "
            f"bin/install.py deploy-code --backup",
        )

    if install_environment:
        install_config["INSTALL_SOURCE"] = "/home/argus/server"

        # execute full install
        execute_remote(
            message="Running full install script...",
            ssh=ssh,
            command="cd /home/argus/server; "
            f"sudo -E {' '.join(f'{key}={value}' for key, value in install_config.items())} "
            f"bin/install.py install",
        )

    if restart:
        execute_remote(
            message="Restarting the argus_server and argus_monitor services...",
            ssh=ssh,
            command="sudo systemctl restart argus_server.service argus_monitor.service nginx.service",
        )

    ssh.close()


def install_webapplication(arpi_access, deployment):
    """
    Install the web application component to a Raspberry PI.
    """
    password = arpi_access.get("password")
    ssh = get_ssh_connection(arpi_access["hostname"], password)
    syncer = SshFileSyncer(ssh, progress=True)

    execute_remote(
        message="Delete old webapplication on remote site...",
        ssh=ssh,
        command="rm -R webapplication || true",
    )

    target = "webapplication"
    logger.info("Copy web application: %s => %s", deployment["webapplication_path"], target)
    syncer.deep_copy(deployment["webapplication_path"], target, "**/*")

    logger.info("List of additional files:")
    for file_path in syncer.list_additional_files:
        logger.info("  %s", file_path)
    logger.info("Synced files statistics: %s", syncer.get_statistics())


def main() -> int:
    """
    Main program function.
    """

    parser = ArgumentParser(
        description=program_license, formatter_class=RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "-v",
        "--verbose",
        dest="verbose",
        action="store_true",
        help="Verbose output",
    )
    parser.add_argument(
        "-e",
        "--env",
        dest="environment",
        default="install",
        required=True,
        help="Select a different config (install/{environment}.yaml) default:environment=install",
    )

    subparsers = parser.add_subparsers(dest="component", required=True, help="Component to install")

    comp_parser = subparsers.add_parser("server", help="Install the server component")
    comp_parser.add_argument(
        "-p",
        "--prepare",
        default=False,
        action="store_true",
        help="Prepare python click",
    )
    comp_parser.add_argument(
        "-i",
        "--install-environment",
        action="store_true",
        help="Install the environment for the server",
    )
    comp_parser.add_argument(
        "-d",
        "--deploy",
        action="store_true",
        help="Deploy the server code to the target device",
    )
    comp_parser.add_argument(
        "-r",
        "--restart",
        action="store_true",
        help="Restart depending service(s) after deployment",
    )

    comp_parser = subparsers.add_parser("webapplication", help="Install the web application")

    args = parser.parse_args()
    if args.verbose:
        print("Verbose output enabled")
        logger.setLevel(logging.DEBUG)
    else:
        print("Verbose output disabled")
        logger.setLevel(logging.INFO)

    # name of the folder is the same as the name of the script
    # the name of the file is the environment argument
    config_filename = join(basename(__file__).replace(".py", ""), f"{args.environment}.yaml")

    logger.info("Working with %s", args)
    logger.info("Working from %s", config_filename)

    config = {}
    with open(config_filename, "r", encoding="utf-8") as stream:
        config = yaml.load(stream, Loader=yaml.FullLoader)
        logger.info(
            "Working with configuration: \n%s",
            json.dumps(config, indent=4, sort_keys=True),
        )
        input("Waiting before starting the installation to verify the configuration!")

    if args.component == "server":
        install_server(
            config["arpi_access"],
            config["database"],
            config["deployment"],
            args.prepare,
            args.deploy,
            args.install_environment,
            args.restart,
        )
    elif args.component == "webapplication":
        install_webapplication(config["arpi_access"], config["deployment"])
    else:
        logger.error("Unknown component: %s", args.component)

    logger.info("Installation finished!")

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SSHConnectionError as error:
        logger.warning("Unable to connect to device! %s", error)
    except KeyboardInterrupt:
        logger.info("\n\nCancelled!\n")
    except Exception:
        logger.exception("Failed to execute!")
        sys.exit(2)

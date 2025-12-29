#!/usr/bin/env python3
# encoding: utf-8
"""

This script installs components of the ArPI home security system onto a running Raspberry Pi Zero Wifi host.
The purpose of the script is to support the development of the system with granular control over the installation process.

It uses SSH for communicating with the target device, leveraging the user's SSH configuration for accessing hosts.
The script reads deployment settings from a YAML configuration file located at install/[<environment>].yaml.

Main features:
- deploys server and web application components
- supports bootstrapping the environment
- handles database migrations post-deployment
- provides verbose logging and configuration verification before installation

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


def install_server(
    arpi_access,
    database,
    deployment,
    prepare=False,
    bootstrap=False,
    deploy=False,
    clean_install=False,
    restart=False,
):
    """
    Install the monitor component to a Raspberry PI.
    """
    password = arpi_access.get("password")
    ssh = get_ssh_connection(arpi_access["hostname"], password)
    syncer = SshFileSyncer(ssh, progress=True)

    # clean previous builds
    system("rm -rf server/dist/* server/*.egg-info")

    if prepare:
        # Install basic dependencies and build tools needed for pip packages
        execute_remote(
            message="Installing basic Python tools...",
            ssh=ssh,
            command="sudo apt-get update && sudo apt-get install -y python3-pip python3-click",
        )

    if bootstrap or deploy:
        # we need the bootstrap package for both bootstrap of the environment
        # and the post-install step after deployment
        result = system("cd server && scripts/create_bootstrap_package.sh")
        if result != 0:
            logger.error("Failed to create bootstrap package")
            return
        
        # find the built package
        package_dir = "server/dist"
        package_files = [f for f in os.listdir(package_dir) if f.endswith('.tar.gz')]
        if not package_files:
            logger.error("No package file found in %s", package_dir)
            return
        
        bootstrap_file = [p for p in package_files if 'bootstrap' in p][0]
        logger.info("Built bootstrap package: %s", bootstrap_file)

        logger.info("Copying package to remote system...")
        syncer.list_copy(
            [
                (os.path.join(package_dir, bootstrap_file), f"/tmp/{bootstrap_file}"),
            ]
        )

    if bootstrap:
        execute_remote(
            message="Extracting bootstrap package...",
            ssh=ssh,
            command=(f"tar -xzf /tmp/{bootstrap_file} -C /tmp/"),
        )
        execute_remote(
            message="Bootstrapping environment...",
            ssh=ssh,
            command=(
                f"sudo BOARD_VERSION={deployment['board_version']} PYTHONPATH=/tmp/src python3 /tmp/src/installer/cli.py bootstrap"
            ),
        )

    if deploy:
        logger.info("Building Python package...")
        
        # build source distribution
        system(f"ENVIRONMENT={deployment['server_environment']} server/scripts/create_package.sh")

        # find the built package
        package_dir = "server/dist"
        package_files = [f for f in os.listdir(package_dir) if f.endswith('.whl')]
        if not package_files:
            logger.error("No package file found in %s", package_dir)
            return

        package_file = [p for p in package_files if 'arpi_server' in p][0]
        logger.info("Built package: %s", package_file)
        
        # copy package to remote
        logger.info("Copying package to remote system...")
        syncer.list_copy(
            [
                (os.path.join(package_dir, package_file), f"/tmp/{package_file}"),
            ]
        )

        # force installing the package to overwrite any existing files
        execute_remote(
            message="Installing the backend package...",
            ssh=ssh,
            command=(
                "pip3 install --user "
                "--break-system-packages "
                f"--upgrade --force-reinstall --no-deps /tmp/{package_file}"
            ),
        )

        extra_deps = ""
        if "extra_packages" in deployment:
            extra_deps = "[" + ",".join(deployment["extra_packages"]) + "]"

        # install dependencies separately
        execute_remote(
            message="Installing package dependencies...",
            ssh=ssh,
            command=(
                f"pip3 install --user --break-system-packages --upgrade '/tmp/{package_file}{extra_deps}'"
            ),
        )

        db_content = ""
        if clean_install:
            db_content = f"DATA_SET_NAME={database['content']}"

        execute_remote(
            message="Extracting deployment package...",
            ssh=ssh,
            command=(f"tar -xzf /tmp/{bootstrap_file} -C /tmp/")
        )
        execute_remote(
            message="Finalizing installation...",
            ssh=ssh,
            password=password,
            command=(
                f"sudo PYTHONPATH=/tmp/src {db_content} python3 /tmp/src/installer/cli.py post-install"
            ),
        )

    if restart:
        execute_remote(
            message="Restarting the argus_server and argus_monitor services...",
            ssh=ssh,
            password=password,
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
        "-b",
        "--bootstrap",
        action="store_true",
        help="Bootstrap the environment for the server",
    )
    comp_parser.add_argument(
        "-d",
        "--deploy",
        action="store_true",
        help="Deploy the server code to the target device",
    )
    comp_parser.add_argument(
        "-c",
        "--clean-install",
        action="store_true",
        help="Perform a clean installation by removing and updating existing database content",
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
            args.bootstrap,
            args.deploy,
            args.clean_install,
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

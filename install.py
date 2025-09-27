#!/usr/bin/env python
# encoding: utf-8
"""

Script for installing the components of the ArPI home security system to a running
Raspberry PI Zero Wifi host.

It uses the configuration file install/[_<environment>].yaml!

---

@author:     Gábor Kovács

@copyright:  2017 arpi-security.info. All rights reserved.

@contact:    gkovacs81@gmail.com
"""

import json
import logging
import os
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

from helpers.install_utils import execute_remote, generate_ssh_key
from helpers.syncer import SshFileSyncer


class SSHConnectionError(Exception):
    """
    Thrown when we can't connect to the remote host.
    """

# write logs to stdout for tee to a file
logging.basicConfig(format="%(message)s", stream=sys.stdout)
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
        logger.info(
            "Connecting %s@%s with %s",
            access["username"],
            access["hostname"],
            access["password"],
        )
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(
            hostname=access["hostname"],
            port=access.get("port", 22),
            username=access["username"],
            password=access["password"],
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
                access.get("port", 22),
            )
        elif access.get("key_name", "") == "":
            logger.info(
                "Connecting with password %s@%s:%s",
                access["username"],
                access["hostname"],
                access.get("port", 22),
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


def install_environment(arpi_access, database, deployment, progress=False):
    """
    Install prerequisites to an empty Raspberry PI.
    """

    # generate SSH key if the name is defined but it doesn't exist
    if (
        arpi_access.get("key_name", "")
        and not exists(arpi_access.get("key_name", ""))
        and not exists(arpi_access.get("key_name", "") + ".pub")
    ):
        generate_ssh_key(arpi_access.get("key_name", ""), arpi_access["password"])

    dhparam_file = "arpi_dhparam.pem"
    if not exists(dhparam_file):
        logger.info("dhparam (%s) generating", dhparam_file)
        system(f"openssl dhparam -out {dhparam_file} {deployment['dhparam_size']}")
    else:
        logger.info("dhparam (%s) already exists", dhparam_file)
        system(f"openssl dhparam -in {dhparam_file} -text | head -3")

    # create the env variables string because paramiko update_environment ignores them
    arguments = {
        "ARPI_HOSTNAME": arpi_access["hostname"],
        "ARPI_PASSWORD": arpi_access["password"],
        "ARGUS_DB_NAME": database["name"],
        "ARGUS_DB_USERNAME": database["username"],
        "ARGUS_DB_PASSWORD": database.get("password", ""),
        "DHPARAM_FILE": join("/tmp", dhparam_file),
        "SALT": deployment["salt"],
        "SECRET": deployment["secret"],
        # progress
        "QUIET": "" if progress else "-q",
        "PROGRESS": "on" if progress else "off",
    }

    # compress server folder
    logger.info("Compressing server folder...")
    # Remove existing compressed file if it exists
    if exists("source.zip"):
        logger.info("Removing existing source.zip")
        os.unlink("source.zip")

    system("cd server && zip -rq ../source.zip . -x '**/__pycache__/*' '**/*.pyc' '**/*.sock'")

    # adding package versions
    arguments.update({p.upper(): f"{v}" for p, v in deployment["packages"].items() if v})

    arguments = [f"export {key}={value}" for key, value in arguments.items()]
    arguments = "; ".join(arguments)

    # remove the known_hosts entry to avoid conflict with the previous installation
    subprocess.call(
        ["ssh-keygen", "-R", arpi_access["hostname"]],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )
    logger.info("Removed %s from known_hosts", arpi_access["hostname"])

    ssh = get_arpi_connection(arpi_access)
    syncer = SshFileSyncer(ssh, progress=progress)

    syncer.list_copy(
        [
            ("source.zip", "/tmp/source.zip"),
            (dhparam_file, f"/tmp/{dhparam_file}"),
            ("install_environment.py", "~/install_environment.py"),
            ("manage_versions.py", "~/manage_versions.py"),
        ]
    )

    logger.info("Final sync statistics: %s", syncer.get_statistics())
    for file_path in syncer.list_additional_files:
        logger.info("  %s", file_path)
    logger.info("Synced files statistics: %s", syncer.get_statistics())

    # remove compressed file locally
    os.unlink("source.zip")

    # decompress server folder
    execute_remote(
        message="Decompressing server folder...",
        ssh=ssh,
        command="unzip -o /tmp/source.zip -d /tmp/server",
    )

    execute_remote(
        message="Installing click...",
        ssh=ssh,
        command="sudo apt-get install -y python3-click",
    )

    execute_remote(
        message="Running install script",
        ssh=ssh,
        command=f"{arguments}; sudo -E ./install_environment.py full-install",
    )

    if arpi_access.get("key_name", "") and arpi_access["deploy_ssh_key"]:
        # add host to known_hosts
        subprocess.call(
            ["ssh-keyscan", "-H", arpi_access["hostname"]],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        logger.info("Added %s to known_hosts", arpi_access["hostname"])
        # deploy key
        command = [
            "sshpass",
            "-p",
            arpi_access["password"],
            "ssh-copy-id",
            "-i",
            arpi_access.get("key_name", ""),
            f"{arpi_access['username']}@{arpi_access['hostname']}",
        ]
        logger.info("Deploy public key: %s", " ".join(command))
        while subprocess.call(command) != 6:
            # 6 =        6      Host public key is unknown. sshpass exits without confirming the new key.
            # retry after 2 seconds
            logger.info("Retrying in 2 seconds...")
            sleep(2)

    if arpi_access.get("key_name", "") and arpi_access["disable_ssh_password_authentication"]:
        # ssh accept password only from terminal
        execute_remote(
            message="Switching to key based ssh authentication",
            ssh=ssh,
            command="sudo sed -i -E -e 's/.*PasswordAuthentication (yes|no)/PasswordAuthentication no/g' /etc/ssh/sshd_config",
        )

    logger.info("Finished installing environment")

    ssh.close()


def install_component(
    arpi_access, deployment, component, update=False, restart=False, progress=False, dry_run=False
):
    """
    Install the monitor component to a Raspberry PI.
    """
    ssh = get_arpi_connection(arpi_access)
    syncer = SshFileSyncer(ssh, progress=progress, dry_run=dry_run)

    execute_remote(
        message="Creating server directories...",
        ssh=ssh,
        command="mkdir -p  server/etc server/scripts server/src webapplication",
        dry_run=dry_run,
    )

    logger.info("Copy common files...")
    syncer.list_copy(
        [
            (join("server", "Pipfile"), "~/server/Pipfile"),
            (join("server", "Pipfile.lock"), "~/server/Pipfile.lock"),
            (join("server", f"{deployment['server_environment']}.env"), "~/server/.env"),
            (join("server", "src", "data.py"), "~/server/src/data.py"),
            (join("server", "src", "constants.py"), "~/server/src/constants.py"),
            (join("server", "src", "hash.py"), "~/server/src/hash.py"),
            (join("server", "src", "models.py"), "~/server/src/models.py"),
            (join("server", "src", "update_user.py"), "~/server/src/update_user.py"),
            (join("server", "src", "tester.py"), "~/server/src/tester.py"),
        ]
    )

    syncer.deep_copy(join("server", "src", "tools"), "~/server/src/tools", "**/*.py")
    syncer.deep_copy(join("server", "src", "utils"), "~/server/src/utils", "**/*.py")

    logger.info("Copy component '%s'...", component)
    syncer.deep_copy(join("server", "src", component), f"~/server/src/{component}", "**/*.py")

    if deployment["deploy_simulator"]:
        syncer.list_copy([
            (join("server", "src", "simulator.py"), "~/server/src/simulator.py"),
        ])

    logger.info("List of additional files:")
    for file_path in syncer.list_additional_files:
        logger.info("  %s", file_path)
    logger.info("Synced files statistics: %s", syncer.get_statistics())

    if update:
        #categories = ["packages", "device"]
        categories = ["packages"]
        if deployment["deploy_simulator"]:
            categories.append("simulator")

        execute_remote(
            message="Install python packages to system...",
            ssh=ssh,
            password=arpi_access["password"],
            command=f'cd server; \
                    PIPENV_TIMEOUT=9999 CI=1 WORKON_HOME=/home/argus/.venvs PIPENV_CUSTOM_VENV_NAME=server \
                    pipenv install --site-packages --categories "{" ".join(categories)}"',
            dry_run=dry_run,
        )

    if restart:
        execute_remote(
            message=f"Restarting the '{component}' service...",
            ssh=ssh,
            password=arpi_access["password"],
            command=f"sudo systemctl restart argus_{component}.service",
            dry_run=dry_run,
        )

    ssh.close()


def install_server(
    arpi_access, deployment, update=False, restart=False, progress=False, dry_run=False
):
    """
    Install the server component to a Raspberry PI.
    """
    install_component(
        arpi_access,
        deployment,
        "server",
        update=update,
        restart=restart,
        progress=progress,
        dry_run=dry_run,
    )


def install_monitor(
    arpi_access, deployment, update=False, restart=False, progress=False, dry_run=False
):
    """
    Install the monitor component to a Raspberry PI.
    """
    install_component(
        arpi_access,
        deployment,
        "monitor",
        update=update,
        restart=restart,
        progress=progress,
        dry_run=dry_run,
    )


def install_database(arpi_access, database, update=False, progress=False, dry_run=False):
    """
    Install the database component to a Raspberry PI.
    """
    ssh = get_arpi_connection(arpi_access)
    syncer = SshFileSyncer(ssh, progress=progress, dry_run=dry_run)

    logger.info("Copy migrations...")
    syncer.deep_copy(
        source=join("server", "migrations"),
        target=join("server", "migrations"),
        filter_expression="**/*",
    )

    logger.info("List of additional files:")
    for file_path in syncer.list_additional_files:
        logger.info("  %s", file_path)
    logger.info("Synced files statistics: %s", syncer.get_statistics())

    execute_remote(
        message="Upgrade database...",
        ssh=ssh,
        command="""cd server; \
            source /home/argus/.venvs/server/bin/activate; \
            export $(grep -hv '^#' .env secrets.env | sed 's/\"//g' | xargs -d '\\n'); \
            printenv; \
            flask --app server:app db upgrade
        """,
        dry_run=dry_run,
    )

    if update:
        execute_remote(
            message="Updating database content...",
            ssh=ssh,
            command=f"cd server;\
                    source /home/argus/.venvs/server/bin/activate; \
                    export $(grep -hv '^#' .env secrets.env | sed 's/\"//g' | xargs -d '\\n'); \
                    src/data.py -d -c {database['content']}",
            dry_run=dry_run,
        )

    ssh.close()


def install_webapplication(arpi_access, deployment, restart=False, progress=False, dry_run=False):
    """
    Install the web application component to a Raspberry PI.
    """
    ssh = get_arpi_connection(arpi_access)
    syncer = SshFileSyncer(ssh, progress=progress, dry_run=dry_run)

    execute_remote(
        message="Delete old webapplication on remote site...",
        ssh=ssh,
        command="rm -R webapplication || true",
        dry_run=dry_run,
    )

    target = "webapplication"
    logger.info("Copy web application: %s => %s", deployment["webapplication_path"], target)
    syncer.deep_copy(deployment["webapplication_path"], target, "**/*")

    logger.info("List of additional files:")
    for file_path in syncer.list_additional_files:
        logger.info("  %s", file_path)
    logger.info("Synced files statistics: %s", syncer.get_statistics())

    if restart:
        execute_remote(
            message="Restarting the service...",
            ssh=ssh,
            command="sudo systemctl restart nginx.service",
            dry_run=dry_run,
        )


def main(argv=None) -> int:
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
        "-p",
        "--progress",
        dest="progress",
        action="store_true",
        help="Show progress",
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

    env_parser = subparsers.add_parser(
        "environment",
        help="Install the environment",
        description="Install the environment for the security system (shell, nginx, python libraries, etc.)",
    )

    for comp in ["server", "monitor", "database", "webapplication"]:
        comp_parser = subparsers.add_parser(comp, help=f"Install the {comp} component")
        comp_parser.add_argument(
            "-r",
            "--restart",
            action="store_true",
            help="Restart depending service(s) after deployment",
        )
        comp_parser.add_argument(
            "-u",
            "--update",
            action="store_true",
            help="Update the python environment for the depending service(s) after deployment",
        )
        comp_parser.add_argument(
            "-d",
            "--dry-run",
            action="store_true",
            help="Don't execute the commands, just print them",
        )

    args = parser.parse_args()
    if args.verbose:
        print("Verbose output enabled")
        logger.setLevel(logging.DEBUG)
    else:
        print("Verbose output disabled")
        logger.setLevel(logging.INFO)

    if args.environment in ["server", "monitor", "database", "webapplication"] and args.dry_run:
        logger.info("Dry run enabled")

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

    if args.component == "environment":
        install_environment(
            config["arpi_access"],
            config["database"],
            config["deployment"],
            args.progress,
        )
    elif args.component == "server":
        install_server(
            config["arpi_access"],
            config["deployment"],
            args.update,
            args.restart,
            args.progress,
            args.dry_run,
        )
    elif args.component == "monitor":
        install_monitor(
            config["arpi_access"],
            config["deployment"],
            args.update,
            args.restart,
            args.progress,
            args.dry_run,
        )
    elif args.component == "webapplication":
        install_webapplication(
            config["arpi_access"], config["deployment"], args.restart, args.progress, args.dry_run
        )
    elif args.component == "database":
        install_database(
            config["arpi_access"], config["database"], args.update, args.progress, args.dry_run
        )
    else:
        logger.error("Unknown component: %s", args.component)

    if args.component in ["server", "monitor", "webapplication"] and args.dry_run:
        logger.info("Dry run finished")
    else:
        logger.info("Finished successfully!")

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

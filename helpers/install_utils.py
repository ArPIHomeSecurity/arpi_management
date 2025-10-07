"""
Module to handle SSH connections and command execution on remote servers.

@author: gkovacs
"""

import contextlib
import logging
import os
from socket import gaierror
from typing import Optional

import paramiko
from paramiko.ssh_exception import SSHException

# get main logger
logger = logging.getLogger(__name__)


class SSHConnectionError(Exception):
    """
    Thrown when we can't connect to the remote host.
    """

def print_ssh_output(output, errors, command=""):
    if command:
        logger.debug("Executed: '%s'", command)

    print_lines(output)
    print_lines(errors)


def print_lines(lines, indent="\t"):
    for line in iter(lambda: lines.readline(2048), ""):
        with contextlib.suppress(UnicodeDecodeError):
            if line.strip() != "":
                logger.info("%s%s", indent, line.rstrip())


def read_lines(lines):
    """
    Read lines from the output stream and log them.

    :param lines: output stream
    :return: concatenated string of lines
    """
    result = ""
    for line in iter(lambda: lines.readline(2048), ""):
        with contextlib.suppress(UnicodeDecodeError):
            if line.strip() != "None":
                result += line
    return result


def generate_ssh_key(key_name, passphrase):
    """
    Generate an SSH key pair

    :param key_name: name of the key file
    :param passphrase: passphrase for the key
    """
    key = paramiko.RSAKey.generate(4096)
    key.write_private_key_file(key_name, password=passphrase)

    with open(f"{key_name}.pub", "w", encoding="utf-8") as public_key:
        public_key.write(f"{key.get_name()} {key.get_base64()}")

    public_key.close()


def get_ssh_connection(hostname, password=None):
    """
    Returns SSH connection using SSH config and hostname
    """
    try:
        ssh = paramiko.SSHClient()
        ssh.load_system_host_keys()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        # load SSH config
        ssh_config = paramiko.SSHConfig()
        config_path = os.path.expanduser("~/.ssh/config")
        if os.path.exists(config_path):
            with open(config_path) as config_file:
                ssh_config.parse(config_file)

        # resolve connection parameters from SSH config
        host_config = ssh_config.lookup(hostname)

        # extract connection parameters
        connect_hostname = host_config.get("hostname", hostname)
        connect_port = host_config.get("port", 22)
        connect_username = host_config.get("user")

        if not connect_username:
            raise SSHConnectionError(f"No username configured for {hostname} in SSH config")

        logger.info("Connecting to %s@%s:%s", connect_username, connect_hostname, connect_port)

        # build connection parameters
        connect_params = {
            "hostname": connect_hostname,
            "port": int(connect_port),
            "username": connect_username,
        }

        # find first available key file and let paramiko handle key type detection
        key_found = False
        if "identityfile" in host_config:
            for key_file in host_config["identityfile"]:
                key_path = os.path.expanduser(key_file)
                if os.path.exists(key_path):
                    connect_params["key_filename"] = key_path
                    if password:
                        connect_params["passphrase"] = password
                        logger.info("Using key %s with passphrase", key_path)
                    else:
                        logger.info("Using key %s", key_path)
                    key_found = True
                    break

        # try connection with key first, then password fallback
        try:
            if key_found:
                ssh.connect(**connect_params)
                logger.info("Connected with key authentication")
            else:
                raise SSHException("No usable key found")

        except SSHException:
            if password:
                logger.info("Key authentication failed, trying password")
                # remove key parameters and use password
                connect_params.pop("key_filename", None)
                connect_params.pop("passphrase", None)
                connect_params["password"] = password
                ssh.connect(**connect_params)
                logger.info("Connected with password authentication")
            else:
                raise

    except (SSHException, gaierror) as error:
        error_msg = f"Can't connect to {hostname}. Error: {error}"
        if "Authentication failed" in str(error):
            if password:
                error_msg += "\nBoth key (with passphrase) and password authentication failed."
            else:
                error_msg += "\nKey authentication failed. Consider adding password to config."

        raise SSHConnectionError(error_msg) from error
    
    return ssh


def execute_remote(
    ssh, command, password=None, message=None, get_output=False, dry_run=False
) -> Optional[str]:
    """
    Execute a command on the remote server

    :param ssh: SSH client
    :param command: command to execute
    :param password: password to use for sudo
    :param message: message to log
    :param get_output: if True, return the output of the command
    :return: output of the command if get_output is True, else None
    """
    if message:
        logger.info(message)
        logger.debug("Executing command: %s", command)

    if dry_run:
        return

    stdin, stdout, stderr = ssh.exec_command(command, get_pty=True)

    if password:
        stdin.write(f"{password}\n")
        stdin.flush()

    if not get_output:
        print_ssh_output(stdout, stderr, command)
        return None

    return read_lines(stdout)

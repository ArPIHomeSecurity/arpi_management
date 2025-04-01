"""
Module to handle SSH connections and command execution on remote servers.

@author: gkovacs
"""

import contextlib

import logging
from typing import Optional


import paramiko


# get main logger
logger = logging.getLogger(__name__)


def print_ssh_output(output, errors, command=""):
    if command:
        logger.debug("Executed: '%s'", command)

    print_lines(output)
    print_lines(errors)


def print_lines(lines, indent="\t"):
    for line in iter(lambda: lines.readline(2048), ""):
        with contextlib.suppress(UnicodeDecodeError):
            if line.strip() != "None":
                logger.info("%s%s", indent, line.strip())


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

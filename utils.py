"""
Created on 2017. aug. 27.

@author: gkovacs
"""

import glob
import logging
import os.path
import subprocess
from os import listdir
from os.path import isfile, join
from textwrap import indent

import paramiko
from scp import SCPClient


# get main logger
logger = logging.getLogger(__name__)


def collect_files(local_path, file_filter=[]):
    results = []
    for item in listdir(local_path):
        if isfile(join(local_path, item)) and not item.startswith(".") and item not in file_filter:
            logger.info("Copy file: %s", item)
            results.append(item)
    return results


def print_ssh_output(output, errors, command=""):
    if command:
        logger.debug("Executed: '%s'", command)

    print_lines(output)
    print_lines(errors)


def print_lines(lines, indent="\t"):
    for line in iter(lambda: lines.readline(2048), ""):
        try:
            logger.info("%s%s", indent, line.strip())
        except UnicodeDecodeError:
            pass


uploaded_files = set()


def show_progress(filename, size, sent):
    uploaded_files.add(filename.decode("utf-8"))
    print("%s: %s/%s => %2d%%" % (filename.decode("utf-8"), sent, size, 100 * sent / size), end="\r")


def list_copy(ssh, files, progress):
    scp = SCPClient(ssh.get_transport(), progress=show_progress if progress else None)

    for source, target in files:
        logger.info("  Copying %s to %s", source, join(target, source.split("/")[-1]))
        scp.put(source, remote_path=target)

    # delete last progress line
    print("\033[K", end="\r")
    if uploaded_files:
        logger.debug("Files copied:\n%s\n", indent('\n'.join(sorted(uploaded_files)), "  "))
    uploaded_files.clear()


def deep_copy(ssh, source, target, filter, progress):
    _, stdout, stderr = ssh.exec_command(f"mkdir -p {target}")
    print_ssh_output(stdout, stderr)

    scp = SCPClient(ssh.get_transport(), progress=show_progress if progress else None)

    for fullfilename in glob.iglob(join(source, filter), recursive=True):
        if os.path.isfile(fullfilename):
            filename = fullfilename.split("/")[-1]
            directories = fullfilename.split(source + "/")[1].rsplit(filename)[0]
            logger.info("  Copying %s to %s", fullfilename, join(target, directories, filename))
            # print("Directories: ", directories)
            # print("Source: ", source)
            # print("Target: ", target)
            if directories:
                _, stdout, stderr = ssh.exec_command(f"mkdir -p {join(target, directories)}")
                print_ssh_output(stdout, stderr)
            scp.put(fullfilename, remote_path=join(target, directories, filename))

    # delete last progress line
    print("\033[K", end="\r")
    if uploaded_files:
        logger.debug("Files copied:\n%s\n", indent('\n'.join(sorted(uploaded_files)), "  "))
    uploaded_files.clear()


def get_repository_version(path):
    branch = (
        subprocess.check_output(["git", "-C", path, "rev-parse", "--abbrev-ref", "HEAD"])
        .strip()
        .decode("utf-8")
    )
    commit = (
        subprocess.check_output(["git", "-C", path, "rev-parse", "HEAD"])
        .strip()
        .decode("utf-8")[0:7]
    )
    return "{}-{}".format(branch, commit)


def generate_SSH_key(key_name, passphrase):
    key = paramiko.RSAKey.generate(4096)
    key.write_private_key_file(key_name, password=passphrase)

    with open(key_name + ".pub", "w") as public_key:
        public_key.write(f"{key.get_name()} {key.get_base64()}")

    public_key.close()


def execute_remote(ssh, command, message=None):
    if message:
        logger.info(message)
    _, stdout, stderr = ssh.exec_command(command)
    print_ssh_output(stdout, stderr, command)

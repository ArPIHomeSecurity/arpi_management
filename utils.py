"""
Created on 2017. aug. 27.

@author: gkovacs
"""

import glob
import os.path
import subprocess

from os import listdir
from os.path import isfile, join

from scp import SCPClient


def collect_files(local_path, file_filter=[]):
    results = []
    for item in listdir(local_path):
        if isfile(join(local_path, item)) and not item.startswith(".") and item not in file_filter:
            print("Copy file: %s" % item)
            results.append(item)
    return results


def print_ssh_output(output, errors, command=""):
    if command:
        print("Output of '%s':", command)
    print_lines(output)

    if command:
        print("Errors of '%s':", command)
    print_lines(errors)


def print_lines(lines, indent="\t"):
    for line in iter(lambda: lines.readline(2048), ""):
        print(indent + line.strip())


uploaded_files = set()


def progress(filename, size, sent):
    uploaded_files.add(filename.decode("utf-8"))
    print(("%s: %s/%s => %2d%%" % (filename.decode("utf-8"), size, sent, 100*sent/size)).ljust(100), end="\r")


def list_copy(ssh, files):
    scp = SCPClient(ssh.get_transport(), progress=progress)

    for source, target in files:
        print("Copying %s to %s" % (source, join(target, source.split("/")[-1])))
        scp.put(source, remote_path=target)


def deep_copy(ssh, source, target, filter):
    stdin, stdout, stderr = ssh.exec_command("mkdir -p  %s" % target)
    print_ssh_output(stdout, stderr)

    scp = SCPClient(ssh.get_transport(), progress=progress)

    for fullfilename in glob.iglob(join(source, filter), recursive=True):
        if os.path.isfile(fullfilename):
            filename = fullfilename.split("/")[-1]
            directories = fullfilename.split(source + "/")[1].rsplit(filename)[0]
            print("Copying %s to %s" % (fullfilename, join(target, directories, filename)))
            # print("Directories: %s" % directories)
            # print("Source: %s" % source)
            # print("Target: %s" % target)
            if directories:
                stdin, stdout, stderr = ssh.exec_command("mkdir -p  %s" % join(target, directories))
                print_ssh_output(stdout, stderr)
            scp.put(fullfilename, remote_path=join(target, directories, filename))


def get_repository_version(path):
    branch = subprocess.check_output(["git", "-C", path, "rev-parse", "--abbrev-ref", "HEAD"]).strip().decode("utf-8")
    commit = subprocess.check_output(["git", "-C", path, "rev-parse", "HEAD"]).strip().decode("utf-8")[0:7]
    return "{}-{}".format(branch, commit)

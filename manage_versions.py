#!/usr/bin/env python

import os
import contextlib
import logging
import shutil
import tarfile
import urllib.request

from argparse import ArgumentParser, RawTextHelpFormatter
from datetime import datetime as dt
from difflib import ndiff, unified_diff
from filecmp import dircmp
from logging import basicConfig
from packaging.version import Version, parse
from pathlib import Path
from time import sleep

from git import Repo


description = """
Replace the system code from the github repository based on the tags.

You can list the available tags and use them for upgrade
"""

COMPONENTS = {
    "server": "server",
    "webapplication": "webapplication"
}
SEPARATOR = "\n################################################################################"
INDENT_SIZE = 2


SERVER_GITURL = "https://github.com/ArPIHomeSecurity/arpi_server"
WEBAPP_GITURL = "https://github.com/ArPIHomeSecurity/arpi_webapplication"
TEMP_DIR = "/tmp"
ARGUS_HOME = os.getenv("ARGUS_ROOT", "/home/argus")
FIRST_RELEASE_VERSION = Version("v0.9.0-RC1")
RESTORE_FILES = [
    ".env",
    "migrations"
]


def list_files(start_path="."):
    # logging.debug("Files in %s", start_path)
    result = ""
    walk_result = sorted(list(os.walk(start_path)), key=lambda x: x[0])
    for root, dirs, files in walk_result:
        level = root.replace(start_path, '').count(os.sep)
        indent = ' ' * INDENT_SIZE * (level)
        # logging.debug("%s%s/", indent, os.path.basename(root))
        result += f"{indent}{os.path.basename(root)}/\n"
        sub_indent = ' ' * INDENT_SIZE * (level + 1)
        for f in sorted(files):
            file = os.path.join(root, f)
            info = Path(file)
            file_info = f"{sub_indent}{f:32} = {os.path.getsize(file):10} {info.group():>10}:{info.owner():<10}"
            # logging.debug(file_info)
            result += file_info + "\n"

    return result


def list_versions():
    logging.info("Component 'server'")
    list_versions_of(SERVER_GITURL, os.path.join(TEMP_DIR, "arpi_server"))
    logging.info("Component 'webapplication'")
    list_versions_of(WEBAPP_GITURL, os.path.join(TEMP_DIR, "arpi_webapp"))


def list_versions_of(repo_url, local_path):
    logging.info("Versions in %s", repo_url)
    if os.path.exists(local_path):
        shutil.rmtree(local_path)
    repo = Repo.clone_from(repo_url, local_path)
    get_version(repo)
    shutil.rmtree(local_path)
    logging.info("")


def get_version(repository):
    tags = repository.git.ls_remote("--tags", "origin")
    logging.debug("Tags: %s", tags)
    for line in tags.splitlines():
        logging.debug("Line: %s", line)
        if not line.endswith("^{}"):
            version = line.split("/")[-1]
            if parse(version) >= FIRST_RELEASE_VERSION:
                logging.info("  - %s", version)


def update(component, version):
    logging.info("Changing '%s' to version '%s'", component, version)

    if component == COMPONENTS["server"]:
        update_server(version)
    elif component == COMPONENTS["webapplication"]:
        update_webapplication(version)
    else:
        logging.error("Unknown component!")


def update_server(version):
    working_directory = os.path.join(ARGUS_HOME, "server")
    logging.info("Working directory: %s", working_directory)

    download(SERVER_GITURL, version, "arpi-server.tar.gz")
    extract_files("arpi-server")

    before = list_files(working_directory)
    backup_path = backup_folder(working_directory)

    # remove old files
    # cleanup_folder(working_directory)
    shutil.rmtree(working_directory)

    # copy the new version
    shutil.copytree(os.path.join(TEMP_DIR, "arpi-server"), working_directory)

    # restore configuration
    restore_files(backup_path, working_directory, RESTORE_FILES)

    # list files after replace
    after = list_files(working_directory)
    show_changes(before, after)

    # directory comparison of new and backup
    comparison = dircmp(working_directory, backup_path)
    logging.info(SEPARATOR)
    logging.info("\n\nDiff report:")
    comparison.report_full_closure()

    logging.info(SEPARATOR)
    logging.info("File differences:")
    print_diff_files(comparison)


def update_webapplication(version):
    working_directory = os.path.join(ARGUS_HOME, "webapplication")
    logging.info("Working directory: %s", working_directory)

    download(WEBAPP_GITURL, version, "arpi-webapplication.tar.gz")
    extract_files("arpi-webapplication")

    before = list_files(working_directory)

    backup_path = backup_folder(working_directory)

    # remove old files
    # cleanup_folder(ARGUS_ROOT)
    shutil.rmtree(working_directory)

    # copy the new version
    shutil.copytree(os.path.join(TEMP_DIR, "arpi-webapplication"), working_directory)

    # restore configuration
    restore_files(backup_path, working_directory, RESTORE_FILES)

    # list files after replace
    after = list_files(working_directory)
    show_changes(before, after)

    # directory comparison of new and backup
    # comparison = dircmp(working_directory, backup_path)
    # logging.info(SEPARATOR)
    # logging.info("\n\nDiff report:")
    # comparison.report_full_closure()

    # logging.info(SEPARATOR)
    # logging.info("File differences:")
    # print_diff_files(comparison)


def extract_files(filename):
    archive = tarfile.open(os.path.join(TEMP_DIR, f"{filename}.tar.gz"))
    archive.extractall(os.path.join(TEMP_DIR, filename))


def show_changes(before, after):
    # compare lists - show diff
    logging.info(SEPARATOR)
    logging.debug("Before: \n%s", before)
    logging.debug("After: \n%s", after)
    if before != after:
        diff = ndiff(before.splitlines(), after.splitlines())
        logging.info("Changes found: \n%s", "\n".join(list(diff)))
    else:
        logging.info("No changes found!")


def print_diff_files(comparison):
    """
    Difference of the files
    """
    for name in comparison.diff_files:
        if name in ["Pipfile.lock", "index.html"]:
            continue

        logging.info("\n\nFile difference %s found in %s and %s", name, comparison.left, comparison.right)
        path_left = os.path.join(comparison.left, name)
        path_right = os.path.join(comparison.right, name)
        with open(path_left, "r+") as file_left, open(path_right, "r+") as file_right:
            logging.info("".join(
                unified_diff(
                    file_left.readlines(),
                    file_right.readlines(),
                    fromfile=path_left,
                    tofile=path_right
                )
            ))

    for sub_comparison in comparison.subdirs.values():
        print_diff_files(sub_comparison)


def cleanup_folder(path):
    logging.info("Cleanup folder %s", path)
    for item in os.listdir(path):
        item_path = os.path.join(path, item)
        if os.path.isfile(item_path):
            os.remove(item_path)
        elif os.path.isdir(item_path):
            os.rmdir(item_path)


def backup_folder(path):
    backup_path = f"{path}_backup_{dt.now().strftime('%Y%m%d_%H%M%S')}"
    logging.info("Creating backup to: %s", backup_path)
    # shutil.move(path, backup_path)
    shutil.copytree(path, backup_path)
    return backup_path


def restore_files(backup_folder, restore_folder, backup_paths):
    for backup_path in backup_paths:
        full_backup_path = os.path.join(backup_folder, backup_path)
        relative_path = os.path.relpath(full_backup_path, start=backup_folder)
        restore_path = os.path.join(restore_folder, relative_path)
        logging.info("Restoring: %s", full_backup_path)
        if os.path.isfile(full_backup_path):
            shutil.copy(full_backup_path, restore_path)
        elif os.path.isdir(full_backup_path):
            shutil.copytree(full_backup_path, restore_path)


def download(repo_url, version, filename):
    full_url = f"{repo_url}/releases/download/{version}/{filename}"
    logging.debug("Download from %s", full_url)
    urllib.request.urlretrieve(full_url, os.path.join(TEMP_DIR, filename))


def main():
    parser = ArgumentParser(description=description, formatter_class=RawTextHelpFormatter)
    parser.add_argument("-v", "--verbose", action='store_true')
    subparsers = parser.add_subparsers(dest='action', description="You can use these commands to manage the version of the system")

    help = 'List the available versions'
    parser_list = subparsers.add_parser('list', description=help, help=help)
    # parser_a.add_argument("-o", action='store_true')
    # parser_a.add_argument("--opt2", action='store_true')

    # create the parser for the "b" command
    help = 'Change the local system to the given version'
    parser_change = subparsers.add_parser('change', description=help, help=help)
    parser_change.add_argument("-V", "--version", type=str, required=True)
    parser_change.add_argument("-c", "--component", choices=COMPONENTS.keys(), required=True)
    # parser_b.add_argument("--opt4", action='store_true')

    args = parser.parse_args()

    if args.verbose:
        basicConfig(level=logging.DEBUG, format="%(message)s")
    else:
        basicConfig(level=logging.INFO, format="%(message)s")

    if args.action == "list":
        list_versions()
    elif args.action == "change":
        update(args.component, args.version)
    else:
        parser.print_help()


if __name__ == '__main__':
    main()

"""
Utility functions for the python invoke tasks.
"""

# pylint: disable=not-context-manager
# pylint: disable=too-many-function-args

import contextlib
import fileinput

from sh import git, pushd, ErrorReturnCode


def print_output(line):
    """
    Prints the line to the console.
    """
    print(line)


def get_repository_version(path):
    """
    Returns the current version of the repository.
    """
    with pushd(path):
        # branch = git("rev-parse", "--abbrev-ref", "HEAD").strip()
        commit = git("rev-parse", "HEAD").strip()[:7]
        return commit


def replace(filename, placeholder, value):
    """
    Replaces the placeholder in the given file with the given value.
    """
    with fileinput.FileInput(filename, inplace=True) as file:
        for line in file:
            print(line.replace(placeholder, value), end="")


def update_version_files(version):
    """
    Updates the version files of the server and webapplication.
    """
    server_version = f"{version}:{get_repository_version('server')}"
    print(f"Update server version: {server_version}")
    with open("server/src/server/version.py", "w", encoding="utf-8") as f:
        f.write(f'__version__="{server_version}"')

    webapplication_version = f"{version}:" + get_repository_version("webapplication")
    print(f"Update webapplication version: {webapplication_version}")
    with open("webapplication/src/app/version.ts", "w", encoding="utf-8") as f:
        f.write(f'export const VERSION = "{webapplication_version}"')


def tag_repository(version, path):
    """
    Tags the repository with the given version and pushes it to the origin.
    """
    print(f"Tagging repository with version {version}")
    with pushd(path):
        if path == "server":
            with contextlib.suppress(ErrorReturnCode):
                git(
                    "commit", "src/server/version.py", "--message", f"Release {version}"
                )
        if path == "webapplication":
            with contextlib.suppress(ErrorReturnCode):
                git("commit", "src/app/version.ts", "--message", f"Release {version}")

        git("tag", version, "--message", f"Release {version}")


def get_uncommitted_changes(path):
    """
    Returns the uncommitted changes of the repository excluding the version files.
    """
    with pushd(path):
        lines = git("status", "--short").splitlines()
        # lines exclude version files
        lines = [line for line in lines if "version." not in line]
        return lines


def check_uncommitted_changes(path):
    """
    Returns True if the repository has uncommitted changes.
    """
    print(f"Checking for uncommitted changes in '{path}'...")
    changes = get_uncommitted_changes(path)
    if len(changes) > 0:
        print("\n".join(changes))
    else:
        print("No uncommitted changes found.")
    return len(changes) > 0

# pylint: disable=no-member
# pylint: disable=too-many-function-args
# pylint: disable=no-name-in-module
# pylint: disable=unexpected-keyword-arg
"""
Tasks form managing the ArPI Home Security system software components.
"""

from enum import Enum

from sh import ng
from invoke import task

from task_utils import check_uncommitted_changes, tag_repository, update_version_files


class Component(Enum):
    """
    Enum for the components of the ArPI Home Security system.
    """

    SERVER = "server"
    WEBAPPLICATION = "webapplication"


@task
def update_version(c, version):
    """
    Update the version of the server and webapplication.
    """
    update_version_files(version=version)


@task
def build_webapplication(c):
    """
    Builds the webapplication with the given version for production.
    """
    print("Building production webapplication...")
    print(
        ng(
            "build", "--configuration=production", "--localize", _cwd="webapplication"
        )
    )


@task(
    help={
        "version": "Version of the ArPI Home Security system to release.",
        "component": f"(optional) Component of the ArPI Home Security system to release {[c.value for c in Component]}.",
    }
)
def release(c, version, component: Component = None, dry_run=False):
    """
    Release the ArPI Home Security system software components.
    """

    update_version_files(version)

    if component == Component.SERVER.value:
        if check_uncommitted_changes("server"):
            print("Please commit your changes first!")
            exit(1)
        if not dry_run:
            tag_repository(version=version, path="server")
    elif component == Component.WEBAPPLICATION.value:
        if check_uncommitted_changes("webapplication"):
            print("Please commit your changes first!")
            exit(1)
        build_webapplication(c)
        if not dry_run:
            tag_repository(version=version, path="webapplication")
    else:
        if check_uncommitted_changes("server"):
            print("Please commit your changes first!")
            exit(1)
        if check_uncommitted_changes("webapplication"):
            print("Please commit your changes first!")
            exit(1)

        build_webapplication(c)
        if not dry_run:
            tag_repository(version=version, path="server")
            tag_repository(version=version, path="webapplication")

# pylint: disable=no-member
"""
Tasks form managing the ArPI Home Security system software components.
"""

from enum import Enum
import sh
from invoke import task

from task_utils import tag_repository, update_version_files


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
        sh.ng(
            "build", "--configuration=production", "--localize", _cwd="webapplication"
        )
    )


@task(help={
    "version": "Version of the ArPI Home Security system to release.",
    "component": f"(optional) Component of the ArPI Home Security system to release {[c.value for c in Component]}."
})
def release(c, version, component: Component = None):
    """
    Release the ArPI Home Security system software components.
    """
    update_version_files(version)

    if component == Component.SERVER.value:
        tag_repository(version=version, path="server")
    elif component == Component.WEBAPPLICATION.value:
        build_webapplication(c)
        tag_repository(version=version, path="webapplication")
    else:
        build_webapplication(c)
        tag_repository(version=version, path="server")
        tag_repository(version=version, path="webapplication")

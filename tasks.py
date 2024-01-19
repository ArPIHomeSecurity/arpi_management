# pylint: disable=no-member
"""
Tasks form managing the ArPI Home Security system software components.
"""

import sh
from invoke import task

from task_utils import print_output, tag_repository, update_version_files


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
            "build",
            "--configuration=production",
            "--localize",
            _cwd="webapplication"
        )
    )


@task
def release(c, version):
    """
    Release the ArPI Home Security system software components.

    """
    update_version_files(version)

    build_webapplication(c)

    tag_repository(version=version, path="server")
    tag_repository(version=version, path="webapplication")

"""
Module to handle file synchronization operations.
"""

import glob
import hashlib
import logging
import os
from dataclasses import dataclass
from enum import Enum
from os.path import join

from scp import SCPClient

from helpers.install_utils import execute_remote

logger = logging.getLogger(__name__)


class FileSyncType(Enum):
    """
    Enum to define the type of file sync
    """

    NEW = 1
    UPDATE = 2
    UNCHANGED = 3
    # counter for files on the remote server that are not in the local list
    ADDITIONAL = 4


SYNC_ICONS = {
    FileSyncType.NEW: "➕",
    FileSyncType.UPDATE: "🔄",
    FileSyncType.UNCHANGED: "✅",
    FileSyncType.ADDITIONAL: "🗑️",
}


@dataclass
class SyncStatistics:
    """
    Class to hold the statistics of the sync process
    """

    new: int = 0
    updated: int = 0
    unchanged: int = 0
    additional: int = 0

    def update(self, sync_type: FileSyncType):
        """
        Update the statistics based on the sync type
        :param sync_type: FileSyncType enum value
        """
        if sync_type == FileSyncType.NEW:
            self.new += 1
        elif sync_type == FileSyncType.UPDATE:
            self.updated += 1
        elif sync_type == FileSyncType.UNCHANGED:
            self.unchanged += 1
        elif sync_type == FileSyncType.ADDITIONAL:
            self.additional += 1

    def add(self, other: "SyncStatistics"):
        """
        Add another SyncStatistics object to this one
        :param other: SyncStatistics object
        """
        self.new += other.new
        self.updated += other.updated
        self.unchanged += other.unchanged
        self.additional += other.additional

    def __str__(self):
        """
        Return a string representation of the statistics
        :return: string
        """
        return (
            f"New files: {self.new}, "
            f"Updated files: {self.updated}, "
            f"Unchanged files: {self.unchanged}, "
            f"Additional files: {self.additional}"
        )


class SshFileSyncer:
    """
    A class to handle file synchronization operations.
    """

    def __init__(self, ssh, progress=False, dry_run=False):
        """
        Initialize the Syncer class.

        :param ssh: SSH client
        :param progress: show progress during file operations
        :param dry_run: if True, do not copy files
        """
        self._ssh = ssh
        self._progress = progress
        self._uploaded_files = set()
        self.final_statistics = SyncStatistics()
        self._remote_files = set()
        self._dry_run = dry_run

    def list_copy(self, files) -> SyncStatistics:
        """
        Copy files from local to remote server.

        :param files: list of files to copy (source file, target directory)

        :return: SyncStatistics object
        """
        sync_statistics = SyncStatistics()
        scp = SCPClient(
            self._ssh.get_transport(), progress=self._show_progress if self._progress else None
        )

        max_source_length = max(len(source_file) for source_file, _ in files)

        for source_file, target_path in files:
            # get file name from source
            sync_type = self.check_sha256(source_file, target_path)
            sync_statistics.update(sync_type)
            copy_message = f"  Copying (%s) %-{max_source_length}s to %s"
            logger.info(
                copy_message,
                SYNC_ICONS[sync_type],
                source_file,
                target_path,
            )
            if not self._dry_run:
                scp.put(source_file, remote_path=target_path)

            self._uploaded_files.add(target_path)

        # list files in target directory
        for _, target_path in files:
            is_absolute_path = target_path.startswith("/")
            target_directory = target_path.split("/")[:-1]
            if is_absolute_path:
                self._remote_files.update(self.list_remote_files(join("/", *target_directory)))
            else:
                self._remote_files.update(self.list_remote_files(join(*target_directory)))

        self.final_statistics.add(sync_statistics)
        return sync_statistics

    def deep_copy(self, source, target, filter_expression) -> SyncStatistics:
        """
        Copy files from source to target recursively.

        :param source: source directory
        :param target: target directory
        :param filter_expression: filter expression to match files

        :return: SyncStatistics object
        """
        execute_remote(self._ssh, f"mkdir -p {target}", dry_run=self._dry_run)

        created_directories = set()
        files_to_copy = []
        for full_filename in glob.iglob(join(source, filter_expression), recursive=True):
            if os.path.isfile(full_filename):
                filename = full_filename.split("/")[-1]
                directories = full_filename.split(f"{source}/")[1].rsplit(filename)[0]
                remote_path = join(target, directories)
                if directories and remote_path not in created_directories:
                    created_directories.add(remote_path)
                    execute_remote(
                        self._ssh, f"mkdir -p {remote_path}", dry_run=self._dry_run
                    )

                files_to_copy.append((full_filename, join(remote_path, filename)))

        return self.list_copy(files_to_copy)

    def _show_progress(self, filename, size, sent):
        """
        Show progress for file uploads.

        :param filename: name of the file being uploaded
        :param size: total size of the file
        :param sent: bytes sent so far
        """
        if sent / size == 1:
            print("\033[K", end="\r")
        else:
            print(
                "%s: %s/%s => %2d%%" % (filename.decode("utf-8"), sent, size, 100 * sent / size),
                end="\r",
            )

    def check_sha256(self, local_file, remote_file) -> FileSyncType:
        """
        Check the sha256 checksum of a file.

        :param local_file: path to the local file
        :param remote_file: path to the remote file
        :return: FileSyncType enum value
        """
        local_sha256 = self.get_local_sha256(local_file)
        remote_sha256 = self.get_remote_sha256(remote_file)

        if remote_sha256 is None:
            return FileSyncType.NEW

        if local_sha256 == remote_sha256:
            return FileSyncType.UNCHANGED

        if local_sha256 != remote_sha256:
            return FileSyncType.UPDATE

    def check_file_exists(self, file):
        """
        Check if a file exists on the remote server.

        :param file: path to the file relative to the home directory
        :return: True if the file exists, False otherwise
        """
        output = execute_remote(
            self._ssh,
            f"test -f {file} && echo 'File exists' || echo 'File does not exist'",
            get_output=True,
        )
        return output.strip() == "File exists"

    def list_remote_files(self, path):
        """
        List files in a remote directory.

        :param path: path to the directory
        :return: list of files
        """
        output = execute_remote(
            self._ssh,
            f"find {path} -maxdepth 1 -type f -printf '%f\n'",
            get_output=True,
        )
        files = output.splitlines()
        return [join(path, file) for file in files if file]

    def get_local_sha256(self, file):
        """
        Get the sha256 checksum of a local file.

        :param file: path to the file
        :return: sha256 checksum
        """
        sha256 = hashlib.sha256()
        with open(file, "rb") as f:
            while chunk := f.read(8192):
                sha256.update(chunk)
        return sha256.hexdigest()

    def get_remote_sha256(self, file):
        """
        Get the sha256 checksum of a remote file.

        :param file: path to the file
        :return: sha256 checksum
        """
        if self.check_file_exists(file):
            output = execute_remote(self._ssh, f"sha256sum {file}", get_output=True)
            return output.split()[0]
        else:
            return None

    @property
    def list_additional_files(self):
        """
        List additional files on the remote server that are not in the local list.

        :param sync_statistics: SyncStatistics object
        """
        additional_files = list(self._remote_files - set(self._uploaded_files))
        additional_files.sort()
        return additional_files

    def get_statistics(self):
        """
        Get the statistics of the sync process.

        :return: SyncStatistics object
        """
        for _ in self._remote_files - set(self._uploaded_files):
            self.final_statistics.update(FileSyncType.ADDITIONAL)

        return self.final_statistics

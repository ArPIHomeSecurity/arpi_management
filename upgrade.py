#!/usr/bin/env python3
import argparse
from dataclasses import dataclass
import json
import re
import requests
import tempfile
import tarfile
import shutil
import os
import subprocess

GITHUB_API_SERVER = "https://api.github.com/repos/ArPIHomeSecurity/arpi_server/releases"
GITHUB_API_WEBAPP = "https://api.github.com/repos/ArPIHomeSecurity/arpi_webapplication/releases"


class AssetNotFoundError(Exception):
    pass

@dataclass
class VersionInfo:
    version: str
    major: int
    minor: int
    patch: int
    prerelease: str | None
    prerelease_num: int | None
    commit_id: str


def get_latest_release(api_url, prerelease=False) -> dict:
    """
    Fetch the latest release from the GitHub API.
    """
    resp = requests.get(api_url)
    resp.raise_for_status()
    releases = resp.json()
    for release in releases:
        if prerelease or not release["prerelease"]:
            return release

    raise Exception("No suitable release found.")


def download_asset(release):
    """
    Download the tar.gz asset from the release.
    """
    for asset in release["assets"]:
        print(f"      🔎 Checking asset: {asset['name']}")
        if asset["name"].endswith(".tar.gz"):
            url = asset["browser_download_url"]
            local_path = os.path.join(tempfile.gettempdir(), asset["name"])
            print(f"      ⬇️  Downloading asset: {asset['name']} from {url}")
            with requests.get(url, stream=True) as r:
                r.raise_for_status()
                with open(local_path, "wb") as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        f.write(chunk)
            print(f"      ✅ Asset downloaded: {local_path}")
            return local_path

    if release["assets"]:
        # print all asset names for debugging
        print("      ⚠️  No .tar.gz asset found in release assets. Available assets:")
        for asset in release["assets"]:
            print(f"        - {asset['name']}")

    raise AssetNotFoundError(f"No tar.gz asset found in the release for {release['tag_name']}.")


def decompress_tar_gz(tar_path):
    """
    Extract the tar.gz archive to a temporary directory.
    """
    tmp_dir = tempfile.mkdtemp()
    with tarfile.open(tar_path, "r:gz") as tar:
        tar.extractall(tmp_dir)

    return tmp_dir


def get_server_version() -> VersionInfo | None:
    """
    Get the actual version of the server component.
    """
    try:
        with open("/home/argus/server/src/assets/version.json", "r", encoding="utf-8") as f:
            version_info = json.load(f)
            return VersionInfo(**version_info)
    except FileNotFoundError:
        print("⚠️  Warning: Server version file not found")


def get_webapplication_version() -> VersionInfo | None:
    """
    Get the actual version of the webapplication component.
    """
    try:
        with open("/home/argus/webapplication/en/assets/version.json", "r", encoding="utf-8") as f:
            version_info = json.load(f)
            return VersionInfo(**version_info)
    except FileNotFoundError:
        print("⚠️  Warning: Webapplication version file not found")


def upgrade_server(tmp_dir):
    """
    Execute install.py from the extracted server files.
    """
    install_config = {
        "PYTHONPATH": "src",
        "INSTALL_SOURCE": tmp_dir,
    }

    # deploy source code
    os.system(
        f"cd {tmp_dir}; "
        f"sudo -E {' '.join(f'{key}={value}' for key, value in install_config.items())} "
        f"python3 -m install install-code --backup;"
    )

    os.system(
        f"cd {tmp_dir}; "
        f"sudo -E {' '.join(f'{key}={value}' for key, value in install_config.items())} "
        f"python3 -m install full-install"
    )


def upgrade_webapplication(tmp_dir):
    """
    Copy the extracted webapplication code to /home/argus/webapplication.
    """
    dst_dir = "/home/argus/webapplication"
    # remove old webapplication dir if exists
    if os.path.exists(dst_dir):
        shutil.rmtree(dst_dir)

    # find the root of the extracted webapplication
    entries = os.listdir(tmp_dir)
    if len(entries) == 1 and os.path.isdir(os.path.join(tmp_dir, entries[0])):
        src_dir = os.path.join(tmp_dir, entries[0])
    else:
        src_dir = tmp_dir

    shutil.copytree(src_dir, dst_dir)


def compare_versions(v1: str, v2: VersionInfo):
    """
    Compare two versions: v1 as string, v2 as VersionInfo.
    Returns 1 if v1 > v2, -1 if v1 < v2, 0 if equal.
    """
    version_parser = re.compile(
        r"v(?P<major>\d+)\.(?P<minor>\d+)\.(?P<patch>\d+)"
        r"(?:_(?P<pre_release>[a-zA-Z]+)(?P<pre_release_num>\d{2}))?"
        r"(?::(?P<commit>[a-z0-9]{7}))?"
    )
    v1_match = version_parser.match(v1)
    if not v1_match:
        print(f"V1: {v1}")
        raise ValueError("Invalid version string format.")

    v1_parts = v1_match.groupdict()

    # Compare major, minor, patch
    for key in ["major", "minor", "patch"]:
        n1 = int(v1_parts[key])
        n2 = getattr(v2, key)
        if n1 > n2:
            return 1
        elif n1 < n2:
            return -1

    # Compare pre_release (None means stable, which is considered higher than any pre-release)
    pre1 = v1_parts["pre_release"]
    pre2 = v2.prerelease
    if pre1 != pre2:
        if pre1 is None:
            return 1
        if pre2 is None:
            return -1
        if pre1 > pre2:
            return 1
        elif pre1 < pre2:
            return -1

    # Compare pre_release_num (None is considered lower)
    num1 = v1_parts["pre_release_num"]
    num2 = v2.prerelease_num
    if num1 != (f"{num2:02}" if num2 is not None else None):
        if num1 is None:
            return -1
        if num2 is None:
            return 1
        n1 = int(num1)
        n2 = num2
        if n1 > n2:
            return 1
        elif n1 < n2:
            return -1

    return 0


def check_and_upgrade(api_url, get_version_func, project_name, prerelease):
    """
    Check for updates and upgrade the specified project if a newer version is available.
    """
    print(f"  🔍 Checking for {project_name} updates...")
    latest_release = get_latest_release(api_url, prerelease=prerelease)
    actual_version = get_version_func()

    # if we cannot determine the actual version, assume upgrade/reinstall is needed
    result = compare_versions(latest_release["tag_name"], actual_version) if actual_version else 1
    if result < 1:
        print(
            f"    ✅ No newer version, skipping {project_name} "
            f"{actual_version} < {latest_release['tag_name']}"
        )
    elif result == 1:
        print(f"    ⬆️  New version {latest_release['tag_name']} available for {project_name}")
        upgrade_project(latest_release, project_name)


def upgrade_project(release: dict, project: str):
    """
    Upgrade the specified project using the latest release.
    """
    print(f"    🚀 Upgrading {project}...")
    print(f"      🏷️  Found release: {release['tag_name']}")
    tar_path = download_asset(release)
    print(f"      📦 Downloaded to: {tar_path}")
    tmp_dir = decompress_tar_gz(tar_path)
    print(f"      📂 Decompressed to: {tmp_dir}")

    if project == "server":
        print("      ⚙️  Upgrading server files...")
        upgrade_server(tmp_dir)
    elif project == "webapplication":
        print("      ⚙️  Upgrading webapplication files...")
        upgrade_webapplication(tmp_dir)
    else:
        raise Exception("Unknown project type.")

    print(f"    ✅ {project} upgrade complete.")


def install_packages(packages):
    """
    Install the specified packages using apt-get.
    """
    print(f"  📦 Installing required packages: {', '.join(packages)}")
    subprocess.run(["sudo", "apt-get", "update"], check=True)
    subprocess.run(["sudo", "apt-get", "install", "-y"] + packages, check=True)
    print("  ✅ Packages installed.")


def main():
    """
    Main entry point for the upgrade script.
    """
    print("🔧 Starting ArPI upgrade process...")
    parser = argparse.ArgumentParser()
    parser.add_argument("--prerelease", action="store_true", help="Use latest prerelease")
    args = parser.parse_args()

    # ensure required packages are installed
    install_packages(["pipenv", "python3-click"])

    check_and_upgrade(GITHUB_API_SERVER, get_server_version, "server", args.prerelease)
    check_and_upgrade(
        GITHUB_API_WEBAPP, get_webapplication_version, "webapplication", args.prerelease
    )

    print("  🔄 Restarting services: argus_server, argus_monitor, nginx ...")
    os.system("sudo systemctl restart argus_server argus_monitor nginx")  # noqa: F821
    print("  ✅ Services restarted successfully")
    print("🎉 Upgrade process finished.")


if __name__ == "__main__":
    try:
        main()
        exit(0)
    except Exception as e:
        print(f"  ❌ Something went wrong: {e}")
        exit(1)

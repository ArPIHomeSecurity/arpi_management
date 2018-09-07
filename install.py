#!/usr/bin/env python
# encoding: utf-8
'''
install -- shortdesc

install is a description

It defines classes_and_methods

@author:     user_name

@copyright:  2017 organization_name. All rights reserved.

@license:    license

@contact:    user_email
@deffield    updated: Updated
'''

import os
import sys

from os.path import join
from pprint import pformat
from socket import gaierror

import paramiko
import yaml

from argparse import ArgumentParser
from argparse import RawDescriptionHelpFormatter
from paramiko.ssh_exception import NoValidConnectionsError
from scp import SCPClient

from utils import print_ssh_output, deep_copy, progress, uploaded_files,\
    print_lines

with open(__file__.replace('.py', '.yaml'), 'r') as stream:
    CONFIG = yaml.load(stream)

__all__ = []
__version__ = 0.1
__date__ = '2017-08-21'
__updated__ = '2017-08-21'


def get_connection():
    try:
        print("Connecting... configuration: %s" % CONFIG)
        ssh = paramiko.SSHClient()
        ssh.load_system_host_keys()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(CONFIG['arpi_hostname'], username=CONFIG['arpi_username'], password=CONFIG['arpi_password'])
        print("Connected with argus credential")
    except (NoValidConnectionsError, gaierror):
        try:
            ssh.connect(CONFIG['default_hostname'], username=CONFIG['default_username'], password=CONFIG['default_password'])
            print("Connected with default credential")
        except (NoValidConnectionsError, gaierror):
            raise Exception("Can't connect to the host!")

    return ssh


def install_environment():
    ssh = get_connection()

    scp = SCPClient(ssh.get_transport(), progress=progress)
    scp.put(join(os.environ['ROOT_PATH'], 'management', 'src', 'install_environment.sh'), remote_path='.')
    deep_copy(ssh, join(os.environ['ROOT_PATH'], 'server', 'etc'), '/tmp/etc', '**/*')

    channel = ssh.get_transport().open_session()
    channel.get_pty()
    channel.set_combine_stderr(True)
    output = channel.makefile('r', -1)
    channel.update_environment({
        "ARGUS_DB_SCHEMA": CONFIG['argus_db_schema'],
        "ARGUS_DB_USERNAME": CONFIG['argus_db_username'],
        "ARGUS_DB_PASSWORD":CONFIG['argus_db_password']
    })

    print("Starting install script...")
    channel.exec_command("./install_environment.sh",)
    print_lines(output)
    ssh.close()


def install_server():
    ssh = get_connection()
    scp = SCPClient(ssh.get_transport(), progress=progress)

    print("Create server directories...")
    _, stdout, stderr = ssh.exec_command("mkdir -p  server/scripts; mkdir -p server/etc; mkdir -p server/webapplication")
    print_ssh_output(stdout, stderr)

    scp.put(join(os.environ['ROOT_PATH'], 'server', 'requirements.txt'), remote_path='server')
    scp.put(join(os.environ['ROOT_PATH'], 'server', 'scripts/reset_database.sh'), remote_path='server/scripts')
    scp.put(join(os.environ['ROOT_PATH'], 'server', 'scripts/start_monitor.sh'), remote_path='server/scripts')
    scp.put(join(os.environ['ROOT_PATH'], 'server', 'scripts/stop_monitor.sh'), remote_path='server/scripts')
    scp.put(join(os.environ['ROOT_PATH'], 'server', 'scripts/start_server.sh'), remote_path='server/scripts')
    scp.put(join(os.environ['ROOT_PATH'], 'server', 'scripts/update_database_struct.sh'), remote_path='server/scripts')
    scp.put(join(os.environ['ROOT_PATH'], 'server', 'scripts/install.sh'), remote_path='server/scripts')
    scp.put(join(os.environ['ROOT_PATH'], 'server', 'etc/common.prod.env'), remote_path='server/etc')
    scp.put(join(os.environ['ROOT_PATH'], 'server', 'etc/server.prod.env'), remote_path='server/etc')
    scp.put(join(os.environ['ROOT_PATH'], 'server', 'etc/monitor.prod.env'), remote_path='server/etc')

    deep_copy(ssh, join(os.environ['ROOT_PATH'], 'server', 'src'), join('server', 'src'), '**/*.py')

    print('Files:\n%s' % pformat(uploaded_files))

    print("Starting install script...")
    _, stdout, stderr = ssh.exec_command("cd server; source ./etc/common.prod.env; ./scripts/install.sh")
    print_ssh_output(stdout, stderr)

    ssh.close()


def install_database():
    ssh = get_connection()

    print("Updating database structure...")
    _, stdout, stderr = ssh.exec_command("cd server; ./scripts/update_database_struct.sh prod")
    print_ssh_output(stdout, stderr)

    print("Reseting database content...")
    _, stdout, stderr = ssh.exec_command("cd server; ./scripts/reset_database.sh prod")
    print_ssh_output(stdout, stderr)

    ssh.close()


def install_webapplication():
    ssh = get_connection()

    print("Delete old webapplication on remote site...")
    _, stdout, stderr = ssh.exec_command("rm -R server/webapplication || true")
    print_ssh_output(stdout, stderr)

    scp = SCPClient(ssh.get_transport(), progress=progress)
    scp.put(join(CONFIG['webapplication_path'] + '-en'), remote_path=join('server', 'webapplication'), recursive=True)
    print('Files: %s' % pformat(uploaded_files))
    uploaded_files.clear()

    scp = SCPClient(ssh.get_transport(), progress=progress)
    scp.put(join(CONFIG['webapplication_path'] + '-hu'), remote_path=join('server', 'webapplication', 'hu'), recursive=True)
    print('Files: %s' % pformat(uploaded_files))


def main(argv=None):  # IGNORE:C0111
    '''Command line options.'''

    if argv is None:
        argv = sys.argv
    else:
        sys.argv.extend(argv)

    program_name = os.path.basename(sys.argv[0])
    program_shortdesc = __import__('__main__').__doc__.split("\n")[1]
    program_license = '''%s

  Created by user_name on %s.
  Copyright 2017 argus. All rights reserved.

USAGE
''' % (program_shortdesc, str(__date__))

    try:
        # Setup argument parser
        parser = ArgumentParser(description=program_license, formatter_class=RawDescriptionHelpFormatter)
        # parser.add_argument("-r", "--recursive", dest="recurse", action="store_true", help="recurse into subfolders [default: %(default)s]")
        parser.add_argument("-v", "--verbose", dest="verbose", action="count", help="set verbosity level [default: %(default)s]")
        # parser.add_argument("-i", "--include", dest="include", help="only include paths matching this regex pattern. Note: exclude is given preference over include. [default: %(default)s]", metavar="RE" )
        # parser.add_argument("-e", "--exclude", dest="exclude", help="exclude paths matching this regex pattern. [default: %(default)s]", metavar="RE" )
        # parser.add_argument('-V', '--version', action='version', version=program_version_message)
        # parser.add_argument(dest="action", help="install", metavar="action")
        parser.add_argument(dest="component", help="environment/server/webapplication/database", metavar="component")

        # Process arguments
        args = parser.parse_args()

        if args.verbose:
            print("Verbose mode on")

        if args.component == 'environment':
            install_environment()
        elif args.component == 'server':
            install_server()
        elif args.component == 'webapplication':
            install_webapplication()
        elif args.component == 'database':
            install_database()
        return 0
    except KeyboardInterrupt:
        ### handle keyboard interrupt ###
        return 0
    except Exception as e:
        indent = len(program_name) * " "
        sys.stderr.write(program_name + ": " + str(e) + "\n")
        sys.stderr.write(indent + "  for help use --help")
        return 2


if __name__ == "__main__":
    sys.exit(main())


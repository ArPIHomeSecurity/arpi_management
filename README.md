# ArPI Home Security system - build tools

## Getting the source

```bash
git clone --recurse-submodules https://github.com/ArPIHomeSecurity/arpi_management.git
```
This command will download the management project of the ArPI Home security system with the server and the webapplication components.

## Manage the software components

You need to install [python3](https://www.python.org/downloads/) and [pipenv](https://pypi.org/project/pipenv/) first!

1. Create the python environment
```bash
pipenv install
```
2. Activate the python environment
```bash
pipenv shell
```
3. Use install script for deploying your the software components to a live instance


```
usage: install.py [-h] [-v] [-e ENVIRONMENT] {environment,server,webapplication,database}

Script for installing the components of the ArPI home security system to a running Raspberry PI Zero Wifi host.
It uses the configuration file install.yaml!

  Created by gkovacs81@gmail.com on 2017-08-21.
  Copyright 2019 arpi-security.info. All rights reserved.

USAGE

positional arguments:
  {environment,server,webapplication,database}

optional arguments:
  -h, --help            show this help message and exit
  -v, --verbose         set verbosity level [default: None]
  -e ENVIRONMENT, --env ENVIRONMENT
                        Select a different config (install.{environment}.yaml)
```

## Deployment

1. Build the web application for production. See: https://github.com/ArPIHomeSecurity/arpi_webapplication

2. Deploy the environment

```bash
ROOT_PATH=$(pwd) python install.py -v environment
```
After installing the environment the host will be restarted automatically!

3. Deploy the database

```bash
ROOT_PATH=$(pwd) python install.py -v database
```

4. Deploy the server
```bash
ROOT_PATH=$(pwd) python install.py -v server
```

5. Deploy the web application

```bash
ROOT_PATH=$(pwd) python install.py -v webapplication
```

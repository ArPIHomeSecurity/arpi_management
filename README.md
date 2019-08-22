# ArPI Home Security system - build tools

## Manage Argus components

1. Create the python environment
```bash
pipenv install
```
2. Activate the python environment
```bash
pipenv shell
```
3. Use install script


```
usage: install.py [-h] [-v] component

Script for installing the components of the arpi security system to a running Raspberry PI Zero Wifi host.
It uses the configuration file install.yaml!

  Created by gkovacs81@gmail.com on 2017-08-21.
  Copyright 2019 arpi-security.info. All rights reserved.

USAGE

positional arguments:
  component      environment/server/webapplication/database

optional arguments:
  -h, --help     show this help message and exit
  -v, --verbose  set verbosity level [default: None]
```

## Run the DEMO with docker-compose

1. Download the docker compose file

```
wget https://raw.githubusercontent.com/ArPIHomeSecurity/arpi_management/master/docker/ArPI.yml
```

2. Run the application with docker-compose

```
# pull the images
docker-compose -f docker/ArPI.yml pull
# start up the database first
docker-compose -p ArPI -f docker/ArPI.yml up -d database
# start the system
docker-compose -p ArPI -f docker/ArPI.yml up
```

3. Open the application in your browser

[ArPI](http://localhost:8080)

<a href="https://www.paypal.me/gkovacs81/">
  <img alt="Support via PayPal" src="https://cdn.rawgit.com/twolfson/paypal-github-button/1.0.0/dist/button.svg"/>
</a>

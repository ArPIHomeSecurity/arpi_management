#!/bin/bash

# Install Argus onto a new Rapsbian system

set -x
PS4='+\t '

# print environment variables sorted
env -0 | sort -z | tr '\0' '\n'

export DEBIAN_FRONTEND=noninteractive

# Sytem update
printf "\n\n# Updating the system\n"
sudo DEBIAN_FRONTEND=noninteractive apt-get $QUIET update
sudo DEBIAN_FRONTEND=noninteractive apt-get $QUIET -y upgrade
sudo DEBIAN_FRONTEND=noninteractive apt-get $QUIET -y autoremove

printf "\n\n# User argus\n"
# Setup user with password
if ! id -u argus; then
  echo "## Creating user"
  sudo useradd -G sudo -m argus
  echo "argus:$ARPI_PASSWORD" | sudo chpasswd

  echo "## Install oh my zsh for argus"
  sudo DEBIAN_FRONTEND=noninteractive apt-get $QUIET -y install zsh curl git vim minicom net-tools telnet
  set +x
  sudo su -c "$(curl -fsSL https://raw.github.com/ohmyzsh/ohmyzsh/master/tools/install.sh) --unattended 2>&1 | cat" argus
  set -x
  sudo chsh -s /bin/zsh argus

  # move the version manamgement script to the argus user
  sudo mv ~/manage_versions.py /home/argus
fi

# CERTIFICATE
printf "\n\n## Create self signed certificate\n"
cd /tmp
openssl req -new -newkey rsa:4096 -nodes -x509 \
     -subj "/C=HU/ST=Fejér/L=Baracska/O=ArPI/CN=arpi.local" \
     -keyout arpi.local.key \
     -out arpi.local.cert
cd ~

# MQTT
printf "\n\n# Install MQTT broker\n"
echo "## Install mosquitto"
cd /tmp
wget http://repo.mosquitto.org/debian/mosquitto-repo.gpg.key
sudo apt-key add mosquitto-repo.gpg.key
cd ~
echo "deb https://repo.mosquitto.org/debian buster main" | sudo tee /etc/apt/sources.list.d/mosquitto-buster.list
sudo apt-get $QUIET update
sudo apt-get $QUIET -y install mosquitto
echo "## Configure mosquitto"
sudo cp $DHPARAM_FILE /etc/mosquitto/certs/
sudo cp -t /etc/mosquitto/certs/ /tmp/arpi.local.key /tmp/arpi.local.cert
sudo chown -R mosquitto: /etc/mosquitto/certs
sudo cp /tmp/etc/mosquitto/auth.conf /etc/mosquitto/conf.d/
sudo cp /tmp/etc/mosquitto/logging.conf /etc/mosquitto/conf.d/
sudo mkdir -p /etc/mosquitto/configs-available/
sudo cp /tmp/etc/mosquitto/ssl*.conf /etc/mosquitto/configs-available/
sudo ln -s /etc/mosquitto/configs-available/ssl-self-signed.conf /etc/mosquitto/conf.d/ssl.conf

# DATABASE
printf "\n\n# Database install\n"
echo "## Install postgres"
sudo DEBIAN_FRONTEND=noninteractive apt-get $QUIET -y install postgresql-${POSTGRESQL_VERSION} postgresql-server-dev-all
echo "## Create database"
sudo su -c "createdb -E UTF8 -e $ARGUS_DB_SCHEMA" postgres

# CERTBOT
printf "\n\n# Install certbot\n"
if uname -m | grep -q 'x86_64'; then
  echo "## Install snapd"
  sudo DEBIAN_FRONTEND=noninteractive apt-get $QUIET -y install snapd
  echo "## Update snapd"
  sudo snap install core < /dev/null
  sudo snap refresh core < /dev/null
  echo "## Update certbot snapd package"
  sudo snap install certbot --classic < /dev/null
  echo "## Prepare the command"
  sudo ln -s /snap/bin/certbot /usr/bin/certbot
elif uname -m | grep -q 'armv6l'; then
  echo "## Install certbot"
  sudo DEBIAN_FRONTEND=noninteractive apt-get $QUIET -y install certbot
fi


# RTC
# based on https://www.abelectronics.co.uk/kb/article/30/rtc-pi-on-raspbian-buster-and-stretch
printf "\n\n# Install RTC - DS1307\n"
sudo DEBIAN_FRONTEND=noninteractive apt-get $QUIET -y install i2c-tools
sudo i2cdetect -y 1
sudo bash -c "echo ds1307 0x68 > /sys/class/i2c-adapter/i2c-1/new_device"
echo "dtoverlay=i2c-rtc,ds1307" | sudo tee -a /boot/config.txt
echo "rtc-ds1307" | sudo tee -a /etc/modules
sudo cp /tmp/etc/cron/hwclock /etc/cron.d/
sudo chmod 644 /etc/cron.d/hwclock

# GSM
printf "\n\n# Install GSM\n"
# disable console on serial ports
sudo systemctl stop serial-getty@ttyAMA0.service
sudo systemctl disable serial-getty@ttyAMA0.service
sudo systemctl stop serial-getty@ttyS0.service
sudo systemctl disable serial-getty@ttyS0.service
sudo sed -i 's/console=serial0,115200 //g' /boot/cmdline.txt
echo "" | sudo tee -a /boot/config.txt
echo "# Enable UART" | sudo tee -a /boot/config.txt
echo "enable_uart=1" | sudo tee -a /boot/config.txt
echo "dtoverlay=uart0" | sudo tee -a /boot/config.txt
echo "dtoverlay=pi3-disable-bt" | sudo tee -a /boot/config.txt
echo "dtoverlay=pi3-miniuart-bt" | sudo tee -a /boot/config.txt

# Enable serial port
sudo systemctl stop hciuart
sudo systemctl disable hciuart

# NGINX installation
printf "\n\n# Install NGINX\n"
echo "## Download"
mkdir ~/nginx_build
cd ~/nginx_build
curl -s -O -J http://nginx.org/download/nginx-$NGINX_VERSION.tar.gz
tar xvf nginx-$NGINX_VERSION.tar.gz
cd nginx-$NGINX_VERSION
echo "## Install prerequisite"
sudo DEBIAN_FRONTEND=noninteractive apt-get $QUIET -y install \
	build-essential \
	libpcre3-dev \
	libssl-dev \
	zlib1g-dev
echo "## Build"
./configure --with-http_stub_status_module --with-http_ssl_module
make
echo "## Install"
sudo make install
# NGINX configurations
sudo mkdir -p /var/log/nginx
sudo rm -r /usr/local/nginx/conf/*
sudo cp -r /tmp/etc/nginx/* /usr/local/nginx/conf/
sudo mkdir -p /usr/local/nginx/conf/modules-enabled/
sudo ln -s /usr/local/nginx/conf/modules-available/* /usr/local/nginx/conf/modules-enabled/
sudo ln -s /usr/local/nginx/conf/snippets/self-signed.conf /usr/local/nginx/conf/snippets/certificates.conf
sudo mkdir -p /usr/local/nginx/conf/sites-enabled/
sudo ln -s /usr/local/nginx/conf/sites-available/argus.conf /usr/local/nginx/conf/sites-enabled/argus.conf

sudo mkdir -p /usr/local/nginx/conf/ssl
sudo cp $DHPARAM_FILE /usr/local/nginx/conf/ssl/
sudo cp -t /usr/local/nginx/conf/ssl/ /tmp/arpi.local.key /tmp/arpi.local.cert
sudo chown -R www-data:www-data /usr/local/nginx/conf/ssl
cd ~

printf "\n\n# Install and configure common tools\n"
echo "## Install python3 and packages"
sudo DEBIAN_FRONTEND=noninteractive apt-get $QUIET -y install \
  dnsutils \
	python3 \
  python3-cryptography \
	python3-dev \
	python3-gpiozero \
	python3-gi \
  gcc \
  libgirepository1.0-dev \
  libcairo2-dev \
  pkg-config \
  gir1.2-gtk-3.0 \
  fail2ban

echo "## Install wiringpi for pywiegand"
git clone $QUIET https://github.com/WiringPi/WiringPi.git ~/wiringpi
cd ~/wiringpi
./build
sudo ldconfig
cd ~

echo "## Install pip packages"
curl -OJ https://bootstrap.pypa.io/get-pip.py
# install pip but supress the output to avoid error in ssh installer
# "UnicodeDecodeError: 'utf-8' codec can't decode byte 0xe2 in position 2047: unexpected end of data"
sudo python3 get-pip.py --quiet
sudo pip3 install --progress-bar $PROGRESS pipenv importlib-resources GitPython

echo "## Configure systemd services"
sudo cp -r /tmp/etc/systemd/* /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable argus_server argus_monitor nginx

printf "\n\n# Generate secrets\n"
if [ -z "$ARGUS_DB_PASSWORD" ]; then
  ARGUS_DB_PASSWORD="$(tr -dc 'A-Za-z0-9!#*+' </dev/urandom | head -c 24  ; echo)"
fi
if [ -z "$SALT" ]; then
  SALT="$(tr -dc 'A-Za-z0-9!#$*+-' </dev/urandom | head -c 24  ; echo)"
fi 
if [ -z "$SECRET" ]; then
  SECRET="$(tr -dc 'A-Za-z0-9!#$&()*+-.:;<=>?@{}' </dev/urandom | head -c 24  ; echo)"
fi
if [ -z "$ARGUS_MQTT_PASSWORD" ]; then
  ARGUS_MQTT_PASSWORD="$(tr -dc 'A-Za-z0-9!#*+' </dev/urandom | head -c 24  ; echo)"
fi

echo "## Configure MQTT access"
sudo mosquitto_passwd -b -c /etc/mosquitto/.passwd argus $ARGUS_MQTT_PASSWORD
echo "## Configure Database access"
sudo su -c "psql -c \"CREATE USER $ARGUS_DB_USERNAME WITH PASSWORD '$ARGUS_DB_PASSWORD';\"" postgres

sudo mkdir /home/argus/server
sudo tee /home/argus/server/secrets.env > /dev/null <<EOL
SALT="$SALT"
DB_PASSWORD="$ARGUS_DB_PASSWORD"
SECRET="$SECRET"
ARGUS_MQTT_PASSWORD="$ARGUS_MQTT_PASSWORD"
EOL
sudo chown -R argus:argus /home/argus/server

echo "## Configure /run folder"
# configuring the /run/argus temporary folder to create after every reboot
echo "# Type Path                     Mode    UID     GID     Age     Argument" | sudo tee /usr/lib/tmpfiles.d/argus.conf
echo "d /run/argus 0755 argus argus" | sudo tee /usr/lib/tmpfiles.d/argus.conf

echo "## Setup hostname"
echo $ARPI_HOSTNAME | sudo tee /etc/hostname

#!/bin/bash

# Install Argus onto a new Rapsbian system

set -x

printenv

export DEBIAN_FRONTEND=noninteractive

# Sytem update
printf "\n\n# Updating the system"
sudo apt-get update
sudo apt-get -y upgrade
sudo apt-get -y autoremove

printf "\n\n# User argus"
# Setup user with password
if ! id -u argus; then
  echo "## Creating user"
  sudo useradd -G sudo -m argus
  echo "argus:$ARPI_PASSWORD" | sudo chpasswd
  echo "argus ALL=(ALL) NOPASSWD: ALL" | sudo tee -a /etc/sudoers

  echo "## Install oh my zsh for argus"
  sudo apt-get -y install zsh curl git vim
  sudo su -c "git clone https://github.com/robbyrussell/oh-my-zsh.git ~/.oh-my-zsh" argus
  sudo su -c "cp ~/.oh-my-zsh/templates/zshrc.zsh-template ~/.zshrc" argus
  sudo chsh -s /bin/zsh argus

  # create ssh keys for git access
  # ssh-keygen -t rsa -N "" -f ~/.ssh/id_rsa
fi

# DATABASE
printf "\n\n# Database install"
echo "## Install postgres"
sudo apt-get install -y postgresql postgresql-server-dev-all
echo "## Configure access"
sudo su -c "psql -c \"CREATE USER $ARGUS_DB_USERNAME WITH PASSWORD '$ARGUS_DB_PASSWORD';\"" postgres
echo "## Create database"
sudo su -c "createdb -E UTF8 -e $ARGUS_DB_SCHEMA" postgres

# CERTBOT
printf "\n\n# Install certbot"
printf "## Install snapd"
sudo apt-get -y install snapd
printf "## Update snapd"
sudo snap install core; sudo snap refresh core
printf "## Update certbot snapd package"
sudo snap install certbot --classic
printf "## Prepare the command"
sudo ln -s /snap/bin/certbot /usr/bin/certbot

# RTC
# based on https://www.abelectronics.co.uk/kb/article/30/rtc-pi-on-raspbian-buster-and-stretch
printf "\n\n# Install RTC - DS1307"
sudo apt-get install -y i2c-tools
sudo i2cdetect -y 1
sudo bash -c "echo ds1307 0x68 > /sys/class/i2c-adapter/i2c-1/new_device"
echo "dtoverlay=i2c-rtc,ds1307" | sudo tee -a /boot/config.txt
echo "rtc-ds1307" | sudo tee -a /etc/modules
sudo cp /tmp/etc/cron/hwclock /etc/cron.d/
sudo chmod 644 /etc/cron.d/hwclock

# GSM
printf "\n\n# Install GSM"
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
printf "\n\n# Install NGINX"
echo "## Download"
mkdir ~/nginx_build
cd ~/nginx_build
wget http://nginx.org/download/nginx-1.19.5.tar.gz
tar xvf nginx-1.19.5.tar.gz
cd nginx-1.19.5
echo "## Install prerequisite"
sudo apt-get -y install \
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

echo "## Create self signed certificate"
openssl req -new -newkey rsa:4096 -nodes -x509 \
     -subj "/C=HU/ST=Fejér/L=Baracska/O=ArPI/CN=arpi.local" \
     -keyout arpi.local.key \
     -out arpi.local.cert
openssl dhparam -out arpi_dhparam.pem 2048
sudo mkdir -p /usr/local/nginx/conf/ssl
sudo mv -t /usr/local/nginx/conf/ssl/ arpi_dhparam.pem arpi.local.key arpi.local.cert
sudo chown -R www-data:www-data /usr/local/nginx/conf/ssl
cd ~

print "\n\n# Install and configure common tools"
echo "## Install python3 and packages"
sudo apt-get -y install \
	python3 \
	python3-gpiozero \
	python3-gi \
	python3-dev \
	python-virtualenv

echo "## Configure systemd services"
sudo cp -r /tmp/etc/systemd/* /etc/systemd/system/
sudo systemctl daemon-reload

# only enable services if the python virtualenv is installed (otherwise after reboot the service will start to install it with sudo)
# sudo systemctl enable nginx.service argus_server.service argus_monitor.service

echo "## Configure /run folder"
# configuring the /run/argus temporary folder to create after every reboot
echo "# Type Path                     Mode    UID     GID     Age     Argument" | sudo tee /usr/lib/tmpfiles.d/argus.conf
echo "d /run/argus 0755 argus argus" | sudo tee /usr/lib/tmpfiles.d/argus.conf

echo "## Setup hostname"
echo "arpi.local" | sudo tee /etc/hostname

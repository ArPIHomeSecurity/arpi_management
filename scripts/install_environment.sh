#!/bin/bash

# Install Argus onto a new Rapsbian system

set -x

printenv

export DEBIAN_FRONTEND=noninteractive

# Sytem update
print "\n\n# Updating the system"
sudo apt-get update
sudo apt-get -y upgrade
sudo apt-get -y autoremove

printf "\n\n# User argus"
# Setup user with password
if ! id -u argus; then
  echo "# Creating user"
  sudo useradd -G sudo -m argus
  echo "argus:argus1" | sudo chpasswd
  echo "argus ALL=(ALL) NOPASSWD: ALL" | sudo tee -a /etc/sudoers

  echo "# Install oh my zsh for argus"
  sudo apt-get -y install zsh curl git
  sudo su -c "git clone https://github.com/robbyrussell/oh-my-zsh.git ~/.oh-my-zsh" argus
  sudo su -c "cp ~/.oh-my-zsh/templates/zshrc.zsh-template ~/.zshrc" argus
  sudo chsh -s /bin/zsh argus

  # create ssh keys for git access
  # ssh-keygen -t rsa -N "" -f ~/.ssh/id_rsa
fi

# DATABASE
printf "\n\n# Database install"
echo "# Install postgres"
sudo apt-get install -y postgresql
echo "# Configure access"
sudo su -c "psql -c \"CREATE USER $ARGUS_DB_USERNAME WITH PASSWORD '$ARGUS_DB_PASSWORD';\"" postgres
echo "# Create database"
sudo su -c "createdb -E UTF8 -e $ARGUS_DB_SCHEMA" postgres

# CERTBOT
print "\n\n# Install certbot"
wget https://dl.eff.org/certbot-auto
sudo mv certbot-auto /usr/local/bin/certbot-auto
sudo chown root /usr/local/bin/certbot-auto
sudo chmod 0755 /usr/local/bin/certbot-auto

# RTC
# based on https://www.abelectronics.co.uk/kb/article/30/rtc-pi-on-raspbian-buster-and-stretch
print "\n\n# Install RTC - DS1307"
sudo apt-get install -y i2c-tools
sudo i2cdetect -y 1
sudo bash -c "echo ds1307 0x68 > /sys/class/i2c-adapter/i2c-1/new_device"
echo "dtoverlay=i2c-rtc,ds1307" | sudo tee -a /boot/config.txt
echo "rtc-ds1307" | sudo tee -a /etc/modules
sudo cp /tmp/etc/cron/hwclock /etc/cron.d/
sudo chmod 644 /etc/cron.d/hwclock

# GSM
print "\n\n# Install GSM"
# disable console on serial ports
sudo systemctl stop serial-getty@ttyAMA0.service
sudo systemctl disable serial-getty@ttyAMA0.service
sudo systemctl stop serial-getty@ttyS0.service
sudo systemctl disable serial-getty@ttyS0.service
# Enable serial port
sudo systemctl stop hciuart
sudo systemctl disable hciuart

# NGINX installation
printf "\n\n#### NGINX ####\n"
echo "# Download"
mkdir ~/nginx_build
cd ~/nginx_build
wget http://nginx.org/download/nginx-1.16.1.tar.gz
tar xvf nginx-1.16.1.tar.gz
cd nginx-1.16.1
echo "# Install prerequisite"
sudo apt-get -y install \
	build-essential \
	libpcre3-dev \
	libssl-dev \
	zlib1g-dev
echo "# Build"
./configure --with-http_stub_status_module --with-http_ssl_module
make
echo "# Install"
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

echo "# Create ssl files"
openssl req -new -newkey rsa:4096 -nodes -x509 \
     -subj "/C=HU/ST=Fejér/L=Baracska/O=ArPI/CN=arpi.local" \
     -keyout arpi.local.key \
     -out arpi.local.cert
openssl dhparam -out arpi_dhparam.pem 2048
sudo mkdir -p /usr/local/nginx/conf/ssl
sudo mv -t /usr/local/nginx/conf/ssl/ arpi_dhparam.pem arpi.local.key arpi.local.cert
sudo chown -R www-data:www-data /usr/local/nginx/conf/ssl
cd ~

# COMMON
sudo apt-get -y install \
	python3 \
	python3-gpiozero \
	python3-gi \
	python3-dev \
	python-virtualenv

# SYSTEMD configuration
sudo cp -r /tmp/etc/systemd/* /etc/systemd/system/
sudo systemctl daemon-reload

# only enable services if the python virtualenv is installed (otherwise after reboot the service will start to install it with sudo)
# sudo systemctl enable nginx.service argus_server.service argus_monitor.service

# configuring the /run/argus temporary folder to create after every reboot
echo "# Type Path                     Mode    UID     GID     Age     Argument" | sudo tee /usr/lib/tmpfiles.d/argus.conf
echo "d /run/argus 0755 argus argus" | sudo tee /usr/lib/tmpfiles.d/argus.conf

# Setup hostname
echo "Change hostname"
echo "arpi.local" | sudo tee /etc/hostname

sudo reboot

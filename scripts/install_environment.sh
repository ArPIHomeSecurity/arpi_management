#!/bin/bash

# Install Argus onto a new Rapsbian system


export DEBIAN_FRONTEND=noninteractive

printf "\n\n#### USER ####\n"
# Setup user with password
if ! id -u argus; then
  echo "# Creating user"
  sudo useradd -G sudo -m argus
  echo "argus:argus1" | sudo chpasswd

  echo "# Install oh my zsh for argus"
  sudo apt-get update
  sudo apt-get -y upgrade
  sudo apt-get -y install zsh curl git
  sudo su -c "git clone https://github.com/robbyrussell/oh-my-zsh.git ~/.oh-my-zsh" argus
  sudo su -c "cp ~/.oh-my-zsh/templates/zshrc.zsh-template ~/.zshrc" argus
  sudo chsh -s /bin/zsh argus

  echo "# Install certbot"
  sudo su -c "wget -P /home/argus/ https://dl.eff.org/certbot-auto" argus
  sudo su -c "chmod a+x /home/argus/certbot-auto" argus
  sudo su -c "/home/argus/certbot-auto help" argus
  sudo apt-get -y install \
    augeas-lenses \
    ca-certificates \
    libaugeas0 \
    libffi-dev \
    libpython-dev \
    libpython2.7 \
    libpython2.7-dev \
    python-dev \
    python2.7-dev

  # create ssh keys for git access
  # ssh-keygen -t rsa -N "" -f ~/.ssh/id_rsa
fi


printf "\n\n#### DATABASE ####\n"
echo "# Install postgres"
sudo apt-get install -y postgresql
echo "# Configure access"
sudo su -c "psql -c \"CREATE USER $ARGUS_DB_USERNAME WITH PASSWORD '$ARGUS_DB_PASSWORD';\"" postgres
echo "# Create database"
sudo su -c "createdb -E UTF8 -e $ARGUS_DB_SCHEMA" postgres

# RTC
sudo apt-get install i2c-tools
#sudo i2cdetect -y 1
sudo bash -c "echo ds1307 0x68 > /sys/class/i2c-adapter/i2c-1/new_device"

# GSM
# disable console on serial ports
sudo systemctl stop serial-getty@ttyAMA0.service
sudo systemctl disable serial-getty@ttyAMA0.service
sudo systemctl stop serial-getty@ttyS0.service
sudo systemctl disable serial-getty@ttyS0.service


printf "\n\n#### NGINX ####\n"
echo "# Download"
mkdir ~/nginx_build
cd ~/nginx_build
wget http://nginx.org/download/nginx-1.14.0.tar.gz
tar xvf nginx-1.14.0.tar.gz
cd nginx-1.14.0
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
sudo systemctl enable nginx.service argus_server.service argus_monitor.service

echo "# Type Path                     Mode    UID     GID     Age     Argument" | sudo tee /usr/lib/tmpfiles.d/argus.conf
echo "d /run/argus 0755 argus argus" | sudo tee /usr/lib/tmpfiles.d/argus.conf

# Setup hostname
echo "Change hostname"
echo "arpi.local" | sudo tee /etc/hostname

sudo reboot

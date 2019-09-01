This tutorial describes the installation steps of the Arpi home security system to an SD Card from source.

Prepare SD card from Raspbian image
========
1. Download the image: https://www.raspberrypi.org/downloads/raspbian/
2. Preferred: Raspbian Buster Lite
3. Write the image to SD card with Etcher: https://github.com/resin-io/etcher/
4. Enable ssh connection: create a file with the name "ssh" in the boot partition of th SD card
5. Create the WIFI configuration file
```bash
wpa_passphrase <ssid>
```
6. Save the WIFI configuration into /etc/wpa_supplicant/wpa_supplicant.conf on your SD card
7. Insert the SD card into the raspberry and start it
8. Connect to the device
```bash
ssh pi@raspberry.local
```
9. Expand files system

```bash
sudo raspi-config --expand-rootfs
sudo reboot
```

Install ArPI on the SD card
========
1. Start the Raspberry PI Zero with the prepared SD card
2. Check the installation configuration file: install.yaml
3. Install the ArPI components with the management project from your development host (not the raspi)
```bash
# activate the python virtual environment
pipenv shell
# install the prerequisites
./install.py environment
./install.py server
# build the production webapplication before install
./install.py webaplication
./install.py database
```
4. You enable the services
```bash
# after login to your raspi
sudo systemctl enable argus_server argus_monitor nginx
sudo systemctl start argus_server argus_monitor
# wait some seconds
sudo systemctl start nginx
```
5. You can access the web application

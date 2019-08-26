This tutorial describes the installation steps of the Arpi home security system to an SD Card from source.

Create SD card from Raspbian image
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


Configure RTC
========

Based on https://thepihut.com/blogs/raspberry-pi-tutorials/17209332-adding-a-real-time-clock-to-your-raspberry-pi

```bash
sudo i2cdetect -y 1
sudo modprobe rtc-ds1307
```


Install Argus home security software
========
Deploy the code.

1. Setup server

* Copy code [src] -> [/home/argus/server]
* Copy systemd service [etc/systemd/argus_server.service] -> [/etc/systemd/system/]

2. Build and deploy web application

* npm run build-release
* Copy build result [webapplication/dist-release] -> [/home/argus/server/webapplication]

3. setup monitor

* Copy code [src] -> [/home/argus/server]
* Copy systemd service [etc/systemd/argus_monitor.service] -> [/etc/systemd/system/]
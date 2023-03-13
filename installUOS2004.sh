#!/bin/bash

# for Ubuntu 20.04
# warning. Befor start script need set permissions: chmod uog+x installUOS2004.sh
# make OS release file
lsb_release -a > ~/OS_ver.txt 2> /dev/null

# connect to wifi on GalaxyS20FE
nmcli dev wifi connect GalaxyS20FE password 'wifi221255#'

# install NoMachine
mkdir ./Downloads
cd ~/Downloads
wget https://download.nomachine.com/download/8.4/Arm/nomachine_8.4.2_1_arm64.deb
echo "orangepi" | sudo -S dpkg -i ~/Downloads/nomachine_8.4.2_1_arm64.deb
rm ~/Downloads/nomachine_8.4.2_1_arm64.deb

# update/upgrade apt
echo "orangepi" | sudo -S apt update;
#                          apt upgrade
                          
# install OnBoard
echo "orangepi" | sudo -S apt -y install onboard;
echo "orangepi" | sudo -S apt clean

# install russian language
echo "orangepi" | sudo -S apt -y install language-pack-ru-base;
echo "orangepi" | sudo -S apt clean

# install timezone
echo "orangepi" | sudo -S cp /etc/localtime /etc/localtime.bak;
echo "orangepi" | sudo -S ln -sf /usr/share/zoneinfo/Europe/Moscow /etc/localtime

# install package manager pip3
echo "orangepi" | sudo -S apt -y install python3-pip;
echo "orangepi" | sudo -S pip3 install --user --upgrade pip
echo "orangepi" | sudo -S apt clean

# install Arduino
echo "orangepi" | sudo -S sudo apt purge brltty
echo "orangepi" | sudo -S sudo apt -y install arduino
echo "orangepi" | sudo -S apt clean

# install video library for python
pip3 install opencv-python

# install Git
echo "orangepi" | sudo -S apt -y install git-all
echo "orangepi" | sudo -S apt clean

# install soft for virtual environment
echo "orangepi" | sudo -S pip3 install --user virtualenv virtualenvwrapper
echo "# virtual environment variables" >> ~/.bashrc
echo "export VIRTUALENVWRAPPER_PYTHON=/usr/bin/python3" >> ~/.bashrc
echo "source ~/.local/bin/virtualenvwrapper.sh" >> ~/.bashrc

# install comand line for Geany
echo "orangepi" | sudo -S sudo apt -y install libvte-dev


# delete firefox browser
#echo "orangepi" | sudo -S apt -y purge firefox;
#                          apt autoremove;

# install chromium browser
#echo "orangepi" | sudo -S apt -y install chromium-browser;
#echo "orangepi" | sudo -S apt clean

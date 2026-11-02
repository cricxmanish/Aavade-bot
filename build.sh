#!/usr/bin/env bash
# exit on error
set -o errexit

# install system dependencies for pygame
apt-get update && apt-get install -y libsdl2-dev libsdl2-image-dev libsdl2-mixer-dev libsdl2-ttf-dev libfreetype6-dev

# install python dependencies
pip install -r requirements.txt

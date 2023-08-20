#!/bin/bash

cd server
tar -cvzf arpi-server.tar.gz --exclude="__pycache__" etc scripts src Pipfile Pipfile.lock
cd ..
mv server/arpi-server.tar.gz .
#!/bin/bash
cd webapplication
tar -cvzf arpi-webapplication.tar.gz -C dist-production .
cd ..
mv webapplication/arpi-webapplication.tar.gz .

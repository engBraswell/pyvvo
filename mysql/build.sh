#!/usr/bin/env bash
# Simple helper for building the MySQL image.
docker build -t gridappsd/pyvvo:mysql-latest .
docker push gridappsd/pyvvo:mysql-latest
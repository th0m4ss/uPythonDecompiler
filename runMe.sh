#!/usr/bin/env bash
mkdir -p in out
rm -rf out/*
docker build -t upy-dec ./docker
docker run -it -v $PWD/in:/code/in -v $PWD/out:/code/out upy-dec


FROM ubuntu:20.04

ARG DEBIAN_FRONTEND=noninteractive
ENV TZ=Etc/UTC

RUN apt update && apt install -y npm python curl
RUN npm install -g n
RUN n nightly

RUN npm install -g typescript ts-node child_process fs @types/watch

RUN mkdir -p /code
COPY . /code

WORKDIR /code
CMD ./entrypoint.sh

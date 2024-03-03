# docker-volume-backup

[![Python unit tests](https://github.com/qaldak/docker-volume-backup/actions/workflows/python-tests.yml/badge.svg)](https://github.com/qaldak/docker-volume-backup/actions/workflows/python-tests.yml)

## Description

Creates a backup of a Docker volume to a target path.
If an error occurs, a message is sent to a defined Slack channel and/or MQTT broker. </br>
With option "--restore", it restores from existing volume backup file to a Docker volume. If Docker volume not already
exist, new Docker volume will be created (e.g. for restoring on another host).

## Getting started

### Install

1. Clone code from GitHub https://github.com/qaldak/docker-volume-backup.git (or Download it)
2. Install Python libs `pip install .`

### Configuration (.env file)

| Param              | Description                                                                                                                                |
|:-------------------|:-------------------------------------------------------------------------------------------------------------------------------------------|
| BACKUP_DIR         | Target path to save the backup                                                                                                             |      
| BACKUP_FILE_OWNER  | (optional) Define owner for created backup file. User id is needed, e.g. 1000 <br> Without this param, backup file created as root user.   |
| BACKUP_FILE_GROUP  | (optional) Define group for created backup file. Group id is needed, e.g. 1000 <br> Without this param, backup file created as root group. |
| BACKUP_FILE_PERMS  | (optional) Define permissions for created backup file, numeric mode only, e.g. 741                                                         |
| LOG_DIR            | Path for log directory                                                                                                                     |
| COMPRESSION_METHOD | (optional) Define the compression method for tar file. Possible values are: <br> GZIP (default, if undefined) <br> BZIP2                   |
| CHAT_ALERTING      | Define in which case a message should be sent. Possible values are: <br> ALWAYS <br> ON_FAILURE <br> NEVER                                 |
| CHAT_SERVICE       | Define Chat service for alerting. Possible values are: <br> SLACK                                                                          |
| SLACK_AUTH_TOKEN   | Required if CHAT_SERVICE=SLACK                                                                                                             |
| SLACK_CHANNEL_ID   | Required if CHAT_SERVICE=SLACK                                                                                                             |
| MQTT_ALERTING      | Define in which case a MQTT message should be sent. Possible values are: <br> ALWAYS <br> ON_FAILURE <br> NEVER                            |
| MQTT_BROKER        | Address of MQTT Broker (Receiver). Mandatory, if MQTT_ALERTING is enabled.                                                                 |
| MQTT_PORT          | Port of MQTT Broker (Receiver). Mandatory, if MQTT_ALERTING is enabled.                                                                    |
| MQTT_TOPIC         | Topic for MQTT message. Mandatory, if MQTT_ALERTING is enabled. <br> Wildcards {HOSTNAME} and {CONTAINER} will be replaced at runtime      |

See example in [.env](.env)

### Execute

#### Command line

__create backup__

`python3 -m src.main <Docker container name> [-p|--path <target path>] [-r|--restart] [--debug]`

optional parameter:

* "-p" set backup directory path, e.g. "-p /backup/container/foo"
* "-r" stops container for backup and restart after work
* "--debug" set loglevel to DEBUG

__restore backup__

`python3 -m src.main --restore <path to backup file> <Docker container name> [-r|--restart] [--debug]`

optional parameter:

* "-r" stops container for backup and restart after work
* "--debug" set loglevel to DEBUG

#### Cronjob

`05 0 * * * cd <PATH> ; python3 -m src.main <Docker container name> [-p|--path <target path>] [-r|--restart] [--debug]`

optional parameter: see Command line

### Requirements

* Python 3.09 or higher
* Python modules, see [requirements.txt](requirements.txt)

### Links

#### Python libraries

* [python-on-whales](https://github.com/gabrieldemarmiesse/python-on-whales)

#### Tools

* [busybox](https://busybox.net/)
* [eclipse-mosquitto](https://mosquitto.org/)
* [slack](https://slack.com)
* [slack api](https://slack.dev)

#### Docker images

there are much more Docker images for the same purpose. This here I used for this project:<br>

* [busybox](https://hub.docker.com/_/busybox) Official Busybox base image by Docker Community
* [eclipse-mosquitto](https://hub.docker.com/_/eclipse-mosquitto) Official eclipse-mosquitto by Eclipse Foundation

## Contribute

Contributions are welcome!

## Licence

Unless otherwise specified, all code is released under the MIT License (MIT).<br>
for used or linked components the respective license terms apply.


# docker-volume-backup

[![Python unit tests](https://github.com/qaldak/docker-volume-backup/actions/workflows/python-tests.yml/badge.svg)](https://github.com/qaldak/docker-volume-backup/actions/workflows/python-tests.yml)

## Description

Creates a backup of a Docker volume to a target path.
If an error occurs, a message is sent to a defined Slack channel.

## Getting started

### Install

1. Clone code from GitHub https://github.com/qaldak/docker-volume-backup.git (or Download it)
2. Install Python libs `pip install -r requirements.txt`

### Configuration (.env file)

| Param              | Description                                                                                                                    |
|:-------------------|:-------------------------------------------------------------------------------------------------------------------------------|
| BACKUP_DIR         | Target path to save the backup                                                                                                 |      
| LOG_DIR            | Path for log directory                                                                                                         |
| COMPRESSION_METHOD | (optional) Define the compression method for tar file. If undefined: Default = GZIP. Possible values are: <br> GZIP <br> BZIP2 |
| CHAT_ALERTING      | Define in which case a message should be sent. Possible values are: <br> ALWAYS <br> ON_FAILURE <br> NEVER                     |
| CHAT_SERVICE       | Define Chat service for alerting. Possible values are: <br> SLACK                                                              |
| SLACK_AUTH_TOKEN   | Required if CHAT_SERVICE=SLACK                                                                                                 |
| SLACK_CHANNEL_ID   | Required if CHAT_SERVICE=SLACK                                                                                                 |

See example in [.env](.env)

### Execute

#### Command line

`python3 -m src.main <Docker container name> [-p|--path <target path>] [-r|--restart] [--debug]`

optional parameter:

* "-p" set backup directory path, e.g. "-p /backup/container/foo"
* "-r" stops container for backup and restart after work
* "--debug" set loglevel to DEBUG

#### Cronjob

`05 0 * * * cd <PATH> ; python3 -m src.main <Docker container name> [-p|--path <target path>] [-r|--restart] [--debug]`

optional parameter: see Command line

### Requirements

* Python 3.10 or higher
* Python modules, see [requirements.txt](requirements.txt)

### Links

#### Python libraries

* [python-on-whales](https://github.com/gabrieldemarmiesse/python-on-whales)

#### Tools

* [busybox](https://busybox.net/)
* [slack](https://slack.com)
* [slack api](https://slack.dev)

#### Docker images

there are much more Docker images for the same purpose. This here I used for this project:<br>

* [busybox](https://hub.docker.com/_/busybox) Official Busybox base image by Docker Community

## Contribute

Contributions are welcome!

## Licence

Unless otherwise specified, all code is released under the MIT License (MIT).<br>
for used or linked components the respective license terms apply.


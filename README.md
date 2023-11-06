# docker-volume-backup

## Description

Creates a backup of a Docker volume to a target path.
If an error occurs, a message is send to a defined Slack channel.

## Getting started

### Install

% t.b.d.

### Configuration (.env file)

% t.b.d.

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

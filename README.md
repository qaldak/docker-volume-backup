# docker-volume-backup


## Description

Creates a backup of a Docker volume to a target path.
If an error occurs, a message is send to a defined Slack channel.

## Getting started

### Execute

#### Command line

`python3 -m src.main <Docker container name> <target path> [--debug]`

optional parameter:

* "--debug" set loglevel to DEBUG

#### Cronjob

`05 0 * * * cd <PATH> ; python3 -m src.main <Docker container name> <target path> [--debug]`

### Requirements

* Python 3.10 or higher
* Python modules, see [requirements.txt](requirements.txt)

### Links

#### Pyhton libraries

* [python-on-whales](https://github.com/gabrieldemarmiesse/python-on-whales)

#### Tools

* [eclipse mosquito](https://mosquitto.org/)
* [unbound](https://nlnetlabs.nl/projects/unbound/about/)

#### Docker images

there are much more Docker images for the same purpose. These here I used for this project:<br>

* [eclipse mosquito](https://hub.docker.com/_/eclipse-mosquitto) by the Eclipse Foundation
* [Unbound DNS Server Docker Image](https://hub.docker.com/r/mvance/unbound) by Matthew Vance

## Contribute

Contributions are welcome!

## Licence

Unless otherwise specified, all code is released under the MIT License (MIT).<br>
for used or linked components the respective license terms apply.

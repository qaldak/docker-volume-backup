# docker-volume-backup

[![Python unit tests](https://github.com/qaldak/docker-volume-backup/actions/workflows/python-tests.yml/badge.svg)](https://github.com/qaldak/docker-volume-backup/actions/workflows/python-tests.yml)

## Description

Creates a backup of a Docker volume to a target path.
If an error occurs, a message is sent to a defined Slack channel and/or MQTT broker. </br>
With option "--restore", it restores from existing volume backup file to a Docker volume. If Docker volume not already
exists, new Docker volume will be created (e.g. for restoring on another host).

It is also possible to restore a Docker volume from a backup file.

## Getting started

### Install

1. Clone code from GitHub https://github.com/qaldak/docker-volume-backup.git (or Download it)
2. Run **[setup.sh](setup.sh)** to install with venv (recommended)

### Configuration (.env file)

| Param              | Description                                                                                                                                |
|:-------------------|:-------------------------------------------------------------------------------------------------------------------------------------------|
| BACKUP_DIR         | Target path to save the backup                                                                                                             |      
| BACKUP_FILE_OWNER  | (optional) Define owner for created backup file. User id is needed, e.g. 1000 <br> Default (if BACKUP_FILE_OWNER and BACKUP_FILE_GROUP are undefined): the user who runs the backup (the backup file is not owned by root). |
| BACKUP_FILE_GROUP  | (optional) Define group for created backup file. Group id is needed, e.g. 1000 <br> Default (if BACKUP_FILE_OWNER and BACKUP_FILE_GROUP are undefined): the primary group of the user who runs the backup. |
| BACKUP_FILE_PERMS  | (optional) Define permissions for created backup file, numeric mode only, e.g. 741 <br> Default: 640 (read/write for the owner, read for the group, nothing for others). The file is created with these permissions, it is never readable by others, not even for a short time. |
| BACKUP_DIR_PERMS   | (optional) Define permissions for the backup directory, if it is created, numeric mode only, e.g. 700 <br> Default: 750. The permissions of an already existing directory are not changed. |
| LOG_DIR            | Path for log directory                                                                                                                     |
| COMPRESSION_METHOD | (optional) Define the compression method for tar file. Possible values are: <br> GZIP (default, if undefined) <br> BZIP2                   |
| IMAGE_REFRESH_DAY  | (optional) Day of month on which the `busybox` base image is pulled from the registry, e.g. `1`. <br> Default (if undefined or invalid): `1`. On all other days the locally cached image is reused. |
| CHAT_ALERTING      | Define in which case a message should be sent. Possible values are: <br> ALWAYS <br> ON_FAILURE <br> NEVER                                 |
| CHAT_SERVICE       | Define Chat service for alerting. Possible values are: <br> SLACK                                                                          |
| SLACK_AUTH_TOKEN   | Required if CHAT_SERVICE=SLACK                                                                                                             |
| SLACK_CHANNEL_ID   | Required if CHAT_SERVICE=SLACK                                                                                                             |
| MQTT_ALERTING      | Define in which case a MQTT message should be sent. Possible values are: <br> ALWAYS <br> ON_FAILURE <br> NEVER                            |
| MQTT_BROKER        | Address of MQTT Broker (Receiver). Mandatory, if MQTT_ALERTING is enabled.                                                                 |
| MQTT_PORT          | Port of MQTT Broker (Receiver). Mandatory, if MQTT_ALERTING is enabled.                                                                    |
| MQTT_TOPIC         | Topic for MQTT message. Mandatory, if MQTT_ALERTING is enabled. <br> Wildcards {HOSTNAME} and {CONTAINER} will be replaced at runtime      |

See example in [.env_example](.env_example)

#### File permissions and security

Backups usually contain secrets (databases, tokens, certificates), so they are not readable by other users by default:
the backup file is created with `640`, the backup directory with `750` and the file belongs to the user who runs the backup.
The volumes of the container are mounted read-only for the backup, so a backup can not modify the data.

* Restrict the permissions of the `.env` file as well, it contains the Slack token: `chmod 600 .env`
* Other users or services that need to read the backups: add them to the group of the backup file (`BACKUP_FILE_GROUP`)
  or set `BACKUP_FILE_PERMS`.
* Behaviour of earlier versions: the backup file was owned by root and readable by everyone (`644`), the directory was created
  with `777` (reduced by the umask). To get this behaviour back, set `BACKUP_FILE_OWNER=0`, `BACKUP_FILE_GROUP=0`,
  `BACKUP_FILE_PERMS=644` and `BACKUP_DIR_PERMS=755`. Backup files created by older versions are not changed.

### Execute

#### Command line

__create backup__

`python3 -m docker_volume_backup.main --backup <Docker container name> [-p|--path <target path>] [-r|--restart] [--debug]`

optional parameter:

* "-p" set backup directory path, e.g. "-p /backup/container/foo"
* "-r" stops container for backup and restart after work (the container is also restarted if the backup fails)
* "--debug" set loglevel to DEBUG

The backup is first written to `<backup file>.tmp` and replaces the existing backup file only after `tar` finished successfully. A failed run leaves the last good backup untouched.

__restore backup__

`python3 -m docker_volume_backup.main --restore --backupfile <path to backup file> --volume <Docker volume name> --targetpath <target path in Docker volume> [-sp|--sourcepath <path in backup file>] [--debug]`

optional parameter:

* "-y" / "--yes" restore into an existing Docker volume that already contains files without asking for confirmation
* "-sp" / "--sourcepath" path of the mount in the backup file to restore, e.g. "-sp /foo/data". A backup file contains all
  volumes and bindings of the container. If it contains more than one path, the restore is rejected without this
  parameter (the error message lists the available paths), because otherwise the content of all paths would be mixed up
  in one volume. Not needed if the backup file contains only one path.
* "--debug" set loglevel to DEBUG

Restore each path of a container into its own volume, e.g.:

`python3 -m docker_volume_backup.main --restore --backupfile /backup/host-foo-volume-backup.tar.gz --volume foo_data --targetpath /foo/data -sp /foo/data`

`python3 -m docker_volume_backup.main --restore --backupfile /backup/host-foo-volume-backup.tar.gz --volume foo_config --targetpath /foo/config -sp /foo/config`

Behaviour for the target Docker volume:

| Docker volume                                            | Restore                                                                                                |
|:---------------------------------------------------------|:-------------------------------------------------------------------------------------------------------|
| does not exist                                           | is created                                                                                             |
| exists, used by a **running** container                  | rejected with an error message and exit code 1, nothing is restored. Stop the container first          |
| exists, used by stopped containers only                  | restored, a warning names the containers                                                               |
| exists and contains files                                | in a terminal: asks for confirmation (`-y` skips it). Without a terminal (cron, scripts): restored, with a warning in the log. Files with the same name are overwritten, other files stay |

The content of the source path is restored directly into the root of the volume. Without `--sourcepath` the number of
path components of `--targetpath` is removed from the paths in the backup file, so it has to match the depth of the
original path.

#### Cronjob

`05 0 * * * cd <PATH> ; python3 -m docker_volume_backup.main --backup <Docker container name> [-p|--path <target path>] [-r|--restart] [--debug]`

optional parameter: see Command line

#### Exit codes

| Exit code | Meaning                                                                                                   |
|:----------|:----------------------------------------------------------------------------------------------------------|
| 0         | Backup: completed successfully (no output on stdout/stderr). <br> Restore: completed, all restored entries found in the volume |
| 1         | Backup: failed, e.g. Docker daemon/container not available, tar error or container could not be restarted. The error is written to the log file and reported via the configured notifications. <br> Restore: rejected or canceled (nothing restored), or finished, but entries of the backup file are missing in the Docker volume (listed in the error message) |

Other errors (e.g. invalid `.env` settings or command line parameters) end with a Python error message and a non-zero exit code.
A restore that is rejected (Docker volume used by a running container) or canceled ends with exit code 1.

After a restore, every restored entry of the backup file is looked up in the Docker volume. Entries that already existed in the volume and are not part of the backup file are ignored.

#### MQTT message

The message is published to `MQTT_TOPIC` as **JSON**, e.g.:

```json
{"time": 1793000000, "host": "myhost", "container": "foo_bar", "backupFile": "myhost-foo_bar-volume-backup.tar.gz",
 "backupSize": 987654321, "duration": "0:02:13", "hasError": false, "msg": "Docker volume backup successful"}
```

| Field      | Description                                                                      |
|:-----------|:---------------------------------------------------------------------------------|
| time       | Unix time (seconds) when the message was created                                 |
| host       | Host name (lower case)                                                           |
| container  | Name of the backed up container                                                  |
| backupFile | Name of the backup file                                                          |
| backupSize | Size of the backup file in bytes (`null` if it could not be determined)          |
| duration   | Duration of the job as `H:MM:SS`                                                 |
| hasError   | `true` if an error occurred                                                      |
| msg        | `Docker volume backup successful` or the error message                           |

Note: older versions sent the message as Python dict text (single quotes, `True`/`False`), which is not valid JSON.

### Requirements

* Python 3.10 or higher
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

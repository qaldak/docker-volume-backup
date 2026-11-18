# docker-volume-backup

[![Python unit tests](https://github.com/qaldak/docker-volume-backup/actions/workflows/python-tests.yml/badge.svg)](https://github.com/qaldak/docker-volume-backup/actions/workflows/python-tests.yml)

Backs up the volumes and bind mounts of a Docker container to a compressed tar file, restores them into a Docker
volume and reports the result via Slack and/or MQTT. Meant to run on the Docker host, e.g. as a cron job.

- One archive per container with all its writable volumes and bind mounts (gzip or bzip2)
- Optional stop and start of the container during the backup
- Restore into a new or existing volume, also on another host
- Alerting via Slack and MQTT (always or on failure)
- Runs `tar` in a short-lived helper container, no extra tools needed on the host
- Safe defaults: restricted file permissions, data mounted read-only, a failed run keeps the last good backup

## Requirements

Docker (CLI and daemon on the same host) and Python 3.10+ (tested with 3.10 to 3.14).

## Installation

```bash
git clone https://github.com/qaldak/docker-volume-backup.git
cd docker-volume-backup
./setup.sh               # creates a venv and installs the package
cp .env_example .env     # adjust, see Configuration
chmod 600 .env           # contains the Slack token
```

The `.env` file has to be in the project directory (next to `setup.sh`). The working directory does not matter.

## Configuration

Settings in `.env`, see [.env_example](.env_example). Use absolute paths (`BACKUP_DIR`, `LOG_DIR`, option `-p`),
e.g. `/var/backups/docker`. `~` is not supported, relative paths depend on the working directory.

| Setting                                  | Description                                                           | Default                  |
|:-----------------------------------------|:----------------------------------------------------------------------|:-------------------------|
| `BACKUP_DIR`                             | Directory for the backups (or option `-p`)                            | -                        |
| `LOG_DIR`                                | Directory for the log files                                           | working directory        |
| `BACKUP_FILE_OWNER`, `BACKUP_FILE_GROUP` | User and group id of the backup file                                  | user who runs the backup |
| `BACKUP_FILE_PERMS`, `BACKUP_DIR_PERMS`  | Octal permissions of the backup file / of a created directory         | `640` / `750`            |
| `COMPRESSION_METHOD`                     | `GZIP` or `BZIP2`                                                     | `GZIP`                   |
| `BASE_IMAGE`                             | Helper image, needs `sh`, `tar`, `mv`, `rm`, `chown`, `chmod`, `find` | `busybox:latest`         |
| `VERIFY_BACKUP`                          | `false` skips the check of the new archive (see Backup)               | `true`                   |
| `IMAGE_REFRESH_DAY`                      | Day of the month on which the helper image is pulled again            | `1`                      |
| `CHAT_ALERTING`, `MQTT_ALERTING`         | `ALWAYS`, `ON_FAILURE` or `NEVER`                                     | no alerting              |
| `CHAT_SERVICE`                           | `SLACK`                                                               | -                        |
| `SLACK_AUTH_TOKEN`, `SLACK_CHANNEL_ID`   | Required for Slack                                                    | -                        |
| `MQTT_BROKER`, `MQTT_PORT`, `MQTT_TOPIC` | Required for MQTT. Topic placeholders: `{HOSTNAME}`, `{CONTAINER}`    | -                        |

## Usage

Run the commands with `venv/bin/python` (or activate the venv with `source venv/bin/activate`).

### Backup

```bash
python -m docker_volume_backup.main --backup <container> [-p <dir>] [-r] [--debug]
```

- `-p` backup directory (default: `BACKUP_DIR`)
- `-r` stop the container during the backup and start it afterwards, also if the backup fails
- `--debug` verbose log

Result: `<dir>/<host>-<container>-volume-backup.tar.gz`. The file is replaced on every run. It is written as
`.tmp` first and read back completely (`tar -t`, not empty) before it replaces the last backup. A failed run, or an
archive that fails this check, is reported as error and does not destroy the last good backup. The check takes about
as long as the backup itself, `VERIFY_BACKUP=false` switches it off.

Backed up are the writable volumes and bind mounts. Not backed up: read-only mounts and sockets, FIFOs and devices
(e.g. `docker.sock`). For a bind-mounted file with an extension (`file.conf`) the directory of the file is backed up.

### Restore

```bash
python -m docker_volume_backup.main --restore --backupfile <file> --volume <volume> --targetpath <path> [-sp <path>] [-y] [--debug]
```

- `--volume` target volume, created if it does not exist
- `--targetpath` mount path of the volume during the restore. Without `-sp` it needs as many path components as
  the original path
- `-y` do not ask for confirmation if the volume already contains files
- `-sp` path inside the backup, e.g. `/foo/data`. Required if the backup holds more than one path (the error message
  lists them). Restore each path into its own volume:

```bash
python -m docker_volume_backup.main --restore --backupfile /backup/host-foo-volume-backup.tar.gz \
  --volume foo_data --targetpath /foo/data -sp /foo/data
```

Existing files with the same name are overwritten. In a terminal the restore asks first if the volume already contains
files (`-y` skips the question), without a terminal (cron, scripts) it continues and logs a warning. A volume used by a
**running** container is rejected, containers that are stopped only give a warning. Afterwards every restored file is
looked up in the volume.

### Cron

```
PATH=/usr/local/bin:/usr/bin:/bin
0 2 * * * /opt/docker-volume-backup/venv/bin/python -m docker_volume_backup.main --backup <container>
```

Cron sends mail only if there is output: a successful backup is silent. `docker` has to be in the `PATH`.

### Exit codes

`0` success, `1` backup failed, restore rejected or canceled, or restored volume incomplete. The reason is in the log
and the alert.
Invalid settings or parameters end with an error message and a non-zero exit code.

## Alerting

Slack receives a short text. MQTT receives JSON on `MQTT_TOPIC`:

```json
{"time": 1793000000, "host": "myhost", "container": "foo", "backupFile": "myhost-foo-volume-backup.tar.gz",
 "backupSize": 987654321, "duration": "0:02:13", "hasError": false, "msg": "Docker volume backup successful"}
```

`msg` holds the error text on failure. A notification that fails is only logged, it does not change the result or the
exit code of the backup and does not stop the other notification. The broker address must be reachable from inside a container (not
`localhost`). The message is sent through a running container with `mqtt` or `mosquitto` in its name, otherwise through
a temporary `eclipse-mosquitto` container.

## Notes and limitations

- **Consistency:** without `-r` the files are copied while the container runs. Databases may be inconsistent: use `-r`
  (the container is stopped for the duration of the backup) or create a dump of the database before the backup. There is
  no pause or pre/post command function.
- **Docker Compose:** for containers started with Compose, `-r` stops and starts the whole Compose project (files, project
  name and directory are read from the labels of the container). Services of the project that were stopped before can
  be started as well.
- **No history:** one backup file per container. Copy it elsewhere if you need older versions.
- **Permissions:** backups are `640` and owned by the user who runs the backup, the data is mounted read-only. Others
  that need access: use `BACKUP_FILE_GROUP`, or set `BACKUP_FILE_OWNER=0`, `BACKUP_FILE_GROUP=0`,
  `BACKUP_FILE_PERMS=644` for root-owned, world-readable files as in earlier versions.
- **Logs:** `<LOG_DIR>/<container>-volume-backup.log` (restore: `restore-<volume>-volume-backup.log`), rotated at
  1 MB, one old file is kept.

## Contribute

Contributions are welcome. Open an issue or a pull request.

## License

MIT, see [LICENSE](LICENSE). Uses [python-on-whales](https://github.com/gabrieldemarmiesse/python-on-whales),
[busybox](https://hub.docker.com/_/busybox), [eclipse-mosquitto](https://hub.docker.com/_/eclipse-mosquitto)
and the [Slack SDK](https://slack.dev); their license terms apply.

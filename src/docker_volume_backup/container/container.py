import logging
import os.path
import posixpath
import re
import stat
import time

import python_on_whales.exceptions
from python_on_whales import docker, DockerClient

from docker_volume_backup.util import cfg

logger = logging.getLogger(__name__)


class Container:
    def __init__(self, name: str):
        self.name = name
        self.id = ""
        self.is_running = False
        self.has_docker_volume = False
        self.has_docker_bindings = False
        self.docker_volumes = []
        self.docker_bindings = []

    def exists(self) -> bool:
        """Checks whether Docker Container exists.
        :return: boolean
        """
        if docker.container.exists(str(self.name)):
            self.id = str(docker.container.inspect(self.name))
            logger.debug(f"Container '{self.name}' found with id '{self.id}'")
            return True
        logger.debug(f"Container '{self.name}' not found")
        return False

    def determine_volume(self):
        logger.debug(f"determining volumes ...")
        try:
            mounts = docker.container.inspect(self.name).mounts or []

        except python_on_whales.exceptions.NoSuchContainer as err:
            logger.error(f"No such container found: {self.name}. Error: {err}")
            raise

        except Exception as err:
            logger.error(f"Error while determining the mounts of container '{self.name}': {err}")
            raise

        if len(mounts) == 0:
            logger.debug(f"No mounts defined in Docker container.")
            return False

        volumes = []
        bindings = []

        for mount in mounts:

            if not mount.rw:
                continue

            if mount.type not in ("volume", "bind"):
                continue

            destination = posixpath.normpath(mount.destination)
            if destination in (".", "/"):
                logger.warning(f"Mount '{mount.destination}' is not backed up: not a path of a volume or file")
                continue

            if mount.type == "volume":
                if destination not in volumes:
                    volumes.append(destination)
                continue

            backup_path = self._determine_binding_path(destination, mount.source)
            if backup_path and backup_path not in bindings:
                bindings.append(backup_path)

        self.docker_volumes, self.docker_bindings = self._remove_nested_paths(volumes, bindings)
        self.has_docker_volume = bool(self.docker_volumes)
        self.has_docker_bindings = bool(self.docker_bindings)

    @staticmethod
    def _determine_source_kind(source) -> str | None:
        """
        :param source: path of a bind mount on the Docker host (this tool runs on the Docker host)
        :return: "dir", "file", "special" (socket, FIFO or device) or None if the source can not be looked at
            (e.g. no permission)
        """
        try:
            mode = os.stat(source).st_mode

        except (OSError, TypeError, ValueError):
            return None

        if stat.S_ISDIR(mode):
            return "dir"

        if stat.S_ISREG(mode):
            return "file"

        return "special"

    @staticmethod
    def _determine_binding_path(destination: str, source) -> str | None:
        """
        Determine the path to back up for a bind mount.
        - directory: the directory itself, also if its name has a "file extension" (conf.d, v1.2)
        - file: as always, a name with an extension is a file and its directory is backed up (e.g. the config
          directory of a config file), a name without extension is backed up itself
        - socket, FIFO, device (e.g. docker.sock): not backed up, tar can not archive them
        - file directly below "/" (e.g. /config.json): the file itself, its directory would be the whole file system

        :param destination: path in the container (normalized)
        :param source: path on the Docker host
        :return: path to back up, None if nothing is to be backed up
        """
        kind = Container._determine_source_kind(source)

        if kind == "special":
            logger.warning(f"Bind mount '{destination}' ({source}) is a socket, FIFO or device and is not backed up")
            return None

        has_extension = re.search(r"[^\/]+?(?=\.\w+$).*", destination) is not None
        path = posixpath.dirname(destination) if has_extension and kind != "dir" else destination

        return path if path != "/" else destination

    @staticmethod
    def _remove_nested_paths(volumes: list[str], bindings: list[str]) -> tuple[list[str], list[str]]:
        """
        A path inside another path to back up is already part of it: tar would archive it twice.

        :return: volumes and bindings without the paths that are inside another path (same order)
        """
        paths = volumes + bindings
        nested = {path for path in paths if any(path != other and path.startswith(f"{other}/") for other in paths)}

        if nested:
            logger.debug(f"Paths inside another path to back up are not added: {sorted(nested)}")

        return [path for path in volumes if path not in nested], [path for path in bindings if path not in nested]

    def is_volume_available(self) -> bool:
        self.determine_volume()

        if self.has_docker_volume or self.has_docker_bindings:
            logger.debug(f"Volumes found: {self.has_docker_volume}, Bindings found: {self.has_docker_bindings}")
            return True

        return False

    def stop(self):
        logger.debug("Stop docker container")
        try:
            docker_compose = self._create_compose_client()
            if docker_compose:
                docker_compose.compose.stop()
            else:
                docker.container.stop(str(self.name))

        except python_on_whales.exceptions.NoSuchContainer as err:
            logger.error(f"Error on stopping Container '{self.name}'. {err}")
            raise

        if not self._is_container_stopped():
            warning_msg = f"Container {self.name} not stopped properly. Continue backup anyway."
            cfg.hasWarning = True
            cfg.warningMsg = warning_msg
            logger.warning(warning_msg)

    def start(self):
        logger.debug("Start docker container")
        try:
            docker_compose = self._create_compose_client()
            if docker_compose:
                docker_compose.compose.start()
            else:
                docker.container.start(str(self.name))

        except Exception as err:
            logger.error(f"Error on restarting container '{self.name}'. {err}")
            raise

        if not self._is_container_running():
            error_msg = f"Container {self.name} not (re)started properly. Check container state"
            cfg.hasError = True
            cfg.errorMsg = error_msg
            raise RuntimeError(error_msg)

    def _is_container_running(self) -> bool:
        """
        :return: True if the container is running (checked up to 4 times, see _wait_for_container_state)
        """
        return self._wait_for_container_state(running=True)

    def _is_container_stopped(self) -> bool:
        """
        :return: True if the container is stopped (checked up to 4 times, see _wait_for_container_state)
        """
        return self._wait_for_container_state(running=False)

    def _wait_for_container_state(self, running: bool, attempts: int = 4, delay: int = 3) -> bool:
        """
        Check whether the container is running (or stopped). The state needs some time after start or stop, so the
        check is repeated with a delay.

        :param running: expected state: True = running, False = stopped
        :param attempts: number of checks
        :param delay: seconds to wait between two checks
        :return: True if the container has the expected state, False if not after all attempts
        """
        state = "running" if running else "stopped"

        try:
            for attempt in range(attempts):
                logger.debug(f"Check is container {state}, attempt: {attempt}")

                if docker.container.inspect(self.name).state.running == running:
                    logger.debug(f"Container is {state}")
                    return True

                if attempt < attempts - 1:
                    logger.debug(f"Attempt {attempt} not successful. Try again...")
                    time.sleep(delay)

            logger.debug(f"Container is still not {state} after {attempts} attempts")
            return False

        except python_on_whales.exceptions.NoSuchContainer as err:
            logger.error(f"No such container found: {self.name}. Error: {err}")
            raise

        except Exception as err:
            logger.error(f"Error occurred while check {self.name} is {state}. Error: {err}")
            raise

    def _read_compose_labels(self) -> dict:
        """
        :return: labels of the container (dict), e.g. com.docker.compose.project
        """
        try:
            labels = docker.container.inspect(self.name).config.labels or {}
            logger.debug(f"labels of container '{self.name}': {labels}")
            return labels

        except Exception as err:
            logger.error(f"Error while inspect container: {err}")
            raise

    def _is_container_started_by_compose(self):
        compose_files = self._read_compose_labels().get("com.docker.compose.project.config_files")
        logger.debug(f"compose_files: {compose_files}")

        if compose_files is None:
            logger.debug("Container not started by docker compose")
            return False, compose_files

        logger.debug("Container started by docker compose")
        return True, compose_files

    def _create_compose_client(self) -> DockerClient | None:
        """
        Docker Compose client for the project of a container that was started by docker compose. Files, project name
        and project directory are taken from the labels of the container, so docker compose works with the project the
        container belongs to:
        - the label holds several compose files separated by "," (e.g. docker-compose.yml and an override file),
          each file needs its own --file parameter.
        - without the project name docker compose derives it from the directory of the compose file. It is another
          one if the project was started with -p or COMPOSE_PROJECT_NAME: docker compose would find no containers.

        :return: client, None if the container was not started by docker compose
        """
        labels = self._read_compose_labels()
        compose_files = labels.get("com.docker.compose.project.config_files")

        if compose_files is None:
            logger.debug("Container not started by docker compose")
            return None

        files = [file for file in compose_files.split(",") if file]
        project_name = labels.get("com.docker.compose.project")
        project_directory = labels.get("com.docker.compose.project.working_dir")
        logger.debug(f"Container started by docker compose. Files: {files}, project: {project_name}, "
                     f"directory: {project_directory}")

        return DockerClient(compose_files=files, compose_project_name=project_name,
                            compose_project_directory=project_directory)

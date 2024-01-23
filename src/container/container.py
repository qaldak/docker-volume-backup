import json
import logging
import os.path
import re
import subprocess
import time
from json import JSONDecodeError

import docker as docker_cli
import python_on_whales.exceptions
from python_on_whales import docker, DockerClient

from util import cfg

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
            mounts = json.loads(subprocess.check_output(["docker", "inspect", "-f", "{{json .Mounts}}", self.name],
                                                        stderr=subprocess.STDOUT))
        except subprocess.CalledProcessError as err:
            logger.error(err)
            raise
        except TypeError as err:
            logger.error(err)
            raise
        except json.JSONDecodeError as err:
            logger.error(err)
            raise

        if len(mounts) == 0:
            logger.debug(f"No mounts defined in Docker container.")
            return False

        for mount in mounts:

            if not mount["RW"]:
                continue

            if mount["Type"] == "volume" and mount["Destination"] not in self.docker_volumes:
                self.docker_volumes.append(mount["Destination"].rstrip("/"))
                self.has_docker_volume = True

            if mount["Type"] == "bind":
                regex_pattern = "[^\/]+?(?=\.\w+$).*"

                filename = re.search(regex_pattern, mount["Destination"])
                if filename is None:
                    destination_path = mount["Destination"].rstrip("/")
                else:
                    destination_path, _ = os.path.split(mount["Destination"])

                if destination_path not in self.docker_bindings:
                    self.docker_bindings.append(destination_path)

                self.has_docker_bindings = True

    def is_volume_available(self) -> bool:
        self.determine_volume()

        if self.has_docker_volume or self.has_docker_bindings:
            logger.debug(f"Volumes found: {self.has_docker_volume}, Bindings found: {self.has_docker_bindings}")
            return True

        return False

    def stop(self):
        logger.debug("Stop docker container")
        try:
            started_by_compose, compose_file_path = self._is_container_started_by_compose()
            logger.debug(f"started by compose: {started_by_compose}, docker compose file: {compose_file_path}")
            if started_by_compose:
                docker_compose = DockerClient(compose_files=compose_file_path)
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
            started_by_compose, compose_file_path = self._is_container_started_by_compose()
            if started_by_compose:
                docker_compose = DockerClient(compose_files=compose_file_path)
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

    def _is_container_running(self, counter: int = 0):
        logger.debug(f"Check is container running, attempt: {counter}")
        try:
            if docker.container.inspect(self.name).state.running:
                logger.debug("Container is running")
                return True

            elif counter > 2:
                logger.debug(f"Container still not running after {counter} attempts")
                return False

            else:
                logger.debug(f"Attempt {counter} not successful. Try again...")
                counter += 1
                time.sleep(3)
                self._is_container_running(counter)

        except python_on_whales.exceptions.NoSuchContainer as err:
            logger.error(f"No such container found: {self.name}. Error:", err)
            raise

        except Exception as err:
            logger.error(f"Error occurred while check {self.name} is running. Error:", err)
            raise

    def _is_container_stopped(self, counter: int = 0):
        logger.debug(f"Check is container stopped, attempt: {counter}")
        try:
            if not docker.container.inspect(self.name).state.running:
                logger.debug("Container is stopped")
                return True

            elif counter > 2:
                logger.debug(f"Container still running after {counter} attempts")
                return False

            else:
                logger.debug(f"Attempt {counter} not successful. Try again...")
                counter += 1
                time.sleep(3)
                self._is_container_running(counter)

        except python_on_whales.exceptions.NoSuchContainer as err:
            logger.error(f"No such container found: {self.name}. Error:", err)
            raise

        except Exception as err:
            logger.error(f"Error occurred while check {self.name} is stopped. Error:", err)
            raise

    def _is_container_started_by_compose(self):
        try:
            client = docker_cli.from_env()
            response = client.inspect_container(container=self.name)

            response_json = json.loads(json.dumps(response))
            logger.debug(f"response_json: {response_json}")

            compose_files = response_json.get("Config").get("Labels").get("com.docker.compose.project.config_files")
            logger.debug(f"compose_files: {compose_files}")

            if compose_files is None:
                logger.debug("Container not started by docker compose")
                return False, compose_files

            logger.debug("Container started by docker compose")
            return True, compose_files

        except JSONDecodeError as err:
            logger.error(f"Error while decoding json: {err}")
            raise

        except Exception as err:
            logger.error(f"Error while inspect container: {err}")
            raise

import json
import logging
import os.path
import re
import subprocess
from json import JSONDecodeError

import docker as docker_cli
import python_on_whales.exceptions
from python_on_whales import docker, DockerClient

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
            self.id = str(docker.container.inspect(x=self.name))
            logger.debug(f"Container '{self.name}' found with id '{self.id}'")
            return True
        logger.debug(f"Container '{self.name}' not found")
        return False

    def determine_volume(self) -> bool:
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

        if self.has_docker_volume or self.has_docker_bindings:
            logger.debug(f"Volumes found: {self.has_docker_volume}, Bindings found: {self.has_docker_bindings}")
            return True

        return False

    def is_volume_available(self):
        # Todo: calculate boolean instead simple return determine_volume()
        return self.determine_volume()

    # Todo: implement stop and start again
    def stop(self):
        try:
            started_by_compose, compose_file_path = self.is_container_started_by_compose()
            if started_by_compose:
                docker_compose = DockerClient(compose_files=compose_file_path)
                docker_compose.compose.down(quiet=True)
            else:
                docker.container.start(str(self.name))
        except python_on_whales.exceptions.NoSuchContainer as err:
            logger.error(f"Error on stopping Container '{self.name}'. {err}")
            raise

    def start(self):
        try:
            started_by_compose, compose_file_path = self.is_container_started_by_compose()
            if started_by_compose:
                docker_compose = DockerClient(compose_files=compose_file_path)
                docker_compose.compose.up(detach=True, quiet=True)
            else:
                docker.container.start(str(self.name))
        except Exception as err:
            logger.error(f"Error on restarting container '{self.name}'. {err}")
            raise

    def is_container_started_by_compose(self):
        try:
            client = docker_cli.from_env()
            response = client.inspect_container(container=self.name)

            response_json = json.loads(json.dumps(response))

            compose_files = response_json.get("Config").get("Labels").get("com.docker.compose.project.config_files")

            if compose_files is None:
                return False

            return True, compose_files

        except JSONDecodeError as err:
            logger.error(f"Error while decoding json: {err}")
            raise

        except Exception as err:
            logger.error(f"Error while inspect container: {err}")
            raise

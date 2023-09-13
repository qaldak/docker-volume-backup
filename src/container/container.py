import json
import logging
import os.path
import re
import subprocess

from python_on_whales import docker

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
        if docker.container.exists(str(self.name)):
            self.id = str(docker.container.inspect(x=self.name))
            logger.debug(f"Container '{self.name}' found with id '{self.id}'")
            return True

        logger.debug(f"Container '{self.name}' not found")
        return False

    @property
    def determine_volume(self):

        try:
            mounts = json.loads(subprocess.check_output(["docker", "inspect", "-f", "{{json .Mounts}}", self.name],
                                                        stderr=subprocess.STDOUT))
            # print("Mounts: ", mounts)
        except subprocess.CalledProcessError as err:
            print(err)
            raise
        except TypeError as err:
            print(err)
            raise
        except json.JSONDecodeError as err:
            print(err)
            raise

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
            return True

        return False

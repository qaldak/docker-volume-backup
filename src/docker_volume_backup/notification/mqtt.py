import json
import logging
import os
import uuid

from python_on_whales import docker, DockerException

logger = logging.getLogger(__name__)


class MQTT:
    def __init__(self, topic: str, msg):
        self.topic = topic
        self.msg = msg

    @staticmethod
    def _build_payload(msg) -> str:
        """
        :param msg: message to send. A dict or list is sent as JSON, everything else as text.
        :return: payload of the MQTT message (str)
        """
        if isinstance(msg, (dict, list)):
            return json.dumps(msg, default=str)

        return str(msg)

    def send_msg(self):
        mqtt_cmd = ["mosquitto_pub", "-h", f"{os.getenv('MQTT_BROKER')}", "-p", f"{os.getenv('MQTT_PORT')}", "-t",
                    f"{self.topic}", "-m", self._build_payload(self.msg)]

        logger.debug(f"MQTT command: {mqtt_cmd}")

        try:
            mqtt_container = self.determine_mqtt_container()

            if mqtt_container:
                logger.debug(f"Running MQTT container found: {mqtt_container}")

                docker.container.execute(mqtt_container, mqtt_cmd)
                return True
            else:
                logger.info("No running mosquitto container found. Download image and create a temporary container")

                # unique name: backups of several containers can run at the same time (cron). The container
                # is removed by docker when it exits.
                docker.container.run(image="eclipse-mosquitto", name=f"tmp-mosquitto-{uuid.uuid4().hex[:8]}",
                                     remove=True, command=mqtt_cmd, log_driver="none")
                return True

        except DockerException as err:
            logger.error(f"Error occurred while sending MQTT message.")
            logger.error(err)
            return False

        except Exception as err:
            logger.error(f"Error occurred while sending MQTT message: {err}")
            raise

    @staticmethod
    def determine_mqtt_container() -> str:
        running_containers = docker.container.list()
        for container in running_containers:
            if "mqtt" in container.name.lower() or "mosquitto" in container.name.lower():
                return container.name

        return ""

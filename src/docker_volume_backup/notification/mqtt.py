import logging
import os

from python_on_whales import docker, DockerException

logger = logging.getLogger(__name__)


class MQTT:
    def __init__(self, topic: str, msg):
        self.topic = topic
        self.msg = msg

    def send_msg(self):
        mqtt_cmd = ["mosquitto_pub", "-h", f"{os.getenv('MQTT_BROKER')}", "-p", f"{os.getenv('MQTT_PORT')}", "-t",
                    f"{self.topic}", "-m", f"{self.msg}"]

        logger.debug(f"MQTT command: {mqtt_cmd}")

        try:
            mqtt_container = self.determine_mqtt_container()

            if mqtt_container:
                logger.debug(f"Running MQTT container found: {mqtt_container}")

                docker.container.execute(mqtt_container, mqtt_cmd)
                return True
            else:
                logger.info("No running mosquitto container found. Download image and create a temporary container")

                if docker.container.exists("tmp-mosquitto"):
                    logger.debug("Remove existing container 'tmp-mosquitto'.")
                    docker.container.remove("tmp-mosquitto")

                docker.container.run(image="eclipse-mosquitto", name="tmp-mosquitto", remove=True,
                                     command=mqtt_cmd, log_driver="none")
                return True

        except DockerException as err:
            logger.error(f"Error occurred while sending MQTT message.")
            logger.error(err)
            return False

        except Exception as err:
            logger.error("Error occurred while sending MQTT message.", {err})
            raise

    @staticmethod
    def determine_mqtt_container() -> str:
        running_containers = docker.container.list()
        for container in running_containers:
            if "mqtt" in container.name.lower() or "mosquitto" in container.name.lower():
                return container.name

        return ""

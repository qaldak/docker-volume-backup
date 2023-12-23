import logging
import os
import time

from util import cfg
from util.accessor import LocalHost, calc_duration

logger = logging.getLogger(__name__)


class Builder:

    @staticmethod
    def build_chat_message(container_name: str) -> str:
        logger.debug(f"start build chat message")

        if cfg.hasError:
            msg = (
                f"[{LocalHost.get_hostname()}] An error occurred while backing up container '{container_name}'"
                f"\nError: {cfg.errorMsg}\nCheck log file for more details.")

        else:
            msg = f"[{LocalHost.get_hostname()}] Volume backup of container '{container_name}' successful"

        logger.debug(f"chat message generated: {msg}")
        return msg

    @staticmethod
    def build_mqtt_msg(container_name: str) -> dict:

        if cfg.hasError:
            mqtt_msg = cfg.errorMsg

        else:
            mqtt_msg = "Docker volume backup successful"

        value = {
            "time": int(time.time()),
            "host": LocalHost.get_hostname(),
            "container": container_name,
            "duration": str(calc_duration(cfg.job_start_time, cfg.job_end_time)),
            "hasError": cfg.hasError,
            "msg": mqtt_msg
        }

        logger.debug(f"MQTT message generated: {value}")

        return value

    @staticmethod
    def build_mqtt_topic(container) -> str:
        try:
            topic = os.getenv("MQTT_TOPIC")

            if topic in (None, ""):
                logger.error("MQTT_TOPIC undefined in .env file")
                raise ValueError("MQTT_TOPIC undefined in .env file")

            values = {"HOSTNAME": LocalHost.get_hostname().upper(), "CONTAINER": container}
            topic = topic.format(**values)

            logger.debug(f"MQTT topic: {topic}")
            return topic

        except ValueError as err:
            logger.error(f"Error occurred while building MQTT topic: {err}")
            raise

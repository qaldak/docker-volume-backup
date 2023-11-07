import logging

from util import cfg
from util.accessor import LocalHost

logger = logging.getLogger(__name__)


class Builder:

    @staticmethod
    def build_chat_message(container_name: str) -> str:
        logger.debug(f"start build chat message")

        msg = ""
        if cfg.hasError:
            msg = (
                f"[{LocalHost.get_hostname()}] An error occurred while backing up container '{container_name}'"
                f"\nError: {cfg.errorMsg}\nCheck log file for more details.")

        else:
            msg = f"[{LocalHost.get_hostname()}] Volume backup of container '{container_name}' successful"

        logger.debug(f"chat message generated: {msg}")
        return msg

    # Todo: implement mqtt
    @staticmethod
    def build_mqtt_msg(orig_err: str):
        # print(__name__, orig_err)
        # print(__name__, "Bar")
        value = {
            "time": "int(time.time())",
            "container": "xyz",
            "msg": orig_err
        }
        return "Mqtt Msg: Foo"

    @staticmethod
    def build_mqtt_topic(container) -> str:
        topic = f"apps/{LocalHost.get_hostname_upper()}/{container.name}/backup/"

        print(topic)
        return topic

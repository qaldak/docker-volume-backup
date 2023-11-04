import logging
import os
from enum import Enum

from notification.builder import Builder
from notification.chat import Slack

logger = logging.getLogger(__name__)


class Dispatcher:
    def __init__(self, container_name: str):
        self.receiver = self.__determine_receiver()
        self.container = container_name
        self.msg = ""
        self.mqtt_msg = ""
        self.send_mqtt = True if os.getenv("MQTT_NOTIFICATION") else False

    @staticmethod
    def __determine_receiver() -> Enum:
        try:
            return Receiver[os.getenv("CHAT_SERVICE")]

        except KeyError as err:
            logger.error(err)
            logger.error(f"CHAT_SERVICE={os.getenv('CHAT_SERVICE')} unknown.")

            return Receiver.UNDEFINED

        except Exception as err:
            logger.error(err)
            raise

    def __send_message(self):
        match self.receiver:
            case Receiver.SLACK:
                Slack().post_message(self.msg)
            case _:
                logger.error(f"Receiver '{self.receiver.name}' not implemented yet.")

    @staticmethod
    def __send_mqtt_message():
        print(__name__, "Bar")

    def notify_receiver(self):
        logger.debug(f"ready to build the chat message")

        self.msg = Builder.build_chat_message(self.container)

        logger.debug(f"post message to chat tool: {self.msg[:100]}...")
        self.__send_message()

        if self.send_mqtt:
            self.__send_mqtt_message()


class Receiver(Enum):
    SLACK = 1
    MQTT = 80
    UNDEFINED = 99

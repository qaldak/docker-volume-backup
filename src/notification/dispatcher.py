import logging
import os
from enum import Enum

from notification.builder import Builder
from notification.chat import Slack

logger = logging.getLogger(__name__)


class Dispatcher:
    def __init__(self, receiver: Enum, container_name: str):
        self.receiver = receiver
        self.container = container_name
        self.msg = ""
        self.mqtt_msg = ""
        self.send_mqtt = True if os.getenv("MQTT_NOTIFICATION") else False

    def __send_message(self):
        match self.receiver:
            case Receiver.SLACK:
                print(__name__, "Foo")
            case _:
                print(__name__, "Foobar")

    @staticmethod
    def __send_mqtt_message():
        print(__name__, "Bar")

    def notify_receiver(self):
        logger.debug(f"ready to build the chat message")

        self.msg = Builder.build_chat_message(self.container)
        logger.debug(f"message to send: '{self.msg}'")

        Slack().post_message(self.msg)

        if self.send_mqtt:
            self.__send_mqtt_message()
        print(__name__, "Baz")


class Receiver(Enum):
    SLACK = 1
    MQTT = 99

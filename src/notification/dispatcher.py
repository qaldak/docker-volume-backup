import logging
import os
from enum import Enum

from notification.builder import Builder
from notification.slack import Slack
from util import cfg

logger = logging.getLogger(__name__)


class Dispatcher:
    def __init__(self, container_name: str):
        self.alerting = self.__determine_alerting()
        self.receiver = self.__determine_receiver()
        self.container = container_name
        self.msg = ""
        self.mqtt_msg = ""
        self.send_mqtt = True if os.getenv("MQTT_NOTIFICATION") == "True" else False

    @staticmethod
    def __determine_alerting() -> Enum:
        try:
            logger.debug(f"Defined alerting: {os.getenv('CHAT_ALERTING')}")

            if not os.getenv("CHAT_ALERTING"):
                logger.debug(f"Alerting undefined or empty: {os.getenv('CHAT_ALERTING')}. Return {Alerting.UNDEFINED}")
                return Alerting.UNDEFINED

            return Alerting[os.getenv("CHAT_ALERTING")]

        except KeyError as err:
            logger.warning(f"Alerting not defined properly: {os.getenv('CHAT_ALERTING')}")
            return Alerting.UNDEFINED

        except Exception as err:
            logger.error(err)
            raise

    @staticmethod
    def __determine_receiver() -> Enum:
        try:
            logger.debug(f"Defined receiver: {os.getenv('CHAT_SERVICE')}")

            if not os.getenv("CHAT_SERVICE"):
                logger.debug(f"Receiver undefined or empty: {os.getenv('CHAT_SERVICE')}. Return {Receiver.UNDEFINED}")
                return Receiver.UNDEFINED

            return Receiver[os.getenv("CHAT_SERVICE")]

        except KeyError as err:
            logger.error(f"Defined CHAT_SERVICE={os.getenv('CHAT_SERVICE')} unknown. Return {Receiver.UNDEFINED}")

            return Receiver.UNDEFINED

        except Exception as err:
            logger.error(err)
            raise

    def __send_message(self):
        match self.receiver:
            case Receiver.SLACK:
                # Todo: Validate settings before post message Slack().is_config_valid() slack = Slack()
                Slack().post_message(self.msg)
            case _:
                logger.error(f"Receiver '{self.receiver.name}' not implemented yet.")

    @staticmethod
    def __send_mqtt_message():
        print(__name__, "Bar")

    def notify_receiver(self):
        match self.alerting:
            case Alerting.NEVER | Alerting.UNDEFINED:
                logger.debug("No alerting defined. Nothing to post.")
                return
            case Alerting.ON_FAILURE:
                if not cfg.hasError:
                    logger.debug("No errors occurred. Nothing to post.")
                    return
            case Alerting.ALWAYS:
                pass

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


class Alerting(Enum):
    ALWAYS = 10
    ON_FAILURE = 20
    NEVER = 90
    UNDEFINED = 99

import logging
import os
from enum import Enum

from docker_volume_backup.notification.builder import Builder
from docker_volume_backup.notification.mqtt import MQTT
from docker_volume_backup.notification.slack import Slack
from docker_volume_backup.util import cfg
from docker_volume_backup.util.accessor import Alerting, Receiver

logger = logging.getLogger(__name__)


class Dispatcher:
    def __init__(self, container_name: str):
        self.alerting = self.__determine_alerting("CHAT_ALERTING")
        self.receiver = self.__determine_receiver("CHAT_SERVICE")
        self.container = container_name
        self.msg = ""
        self.mqtt_alerting = self.__determine_alerting("MQTT_ALERTING")

    @staticmethod
    def __determine_alerting(comm_type: str) -> Enum:
        try:
            logger.debug(f"Defined alerting: {os.getenv(comm_type)}")

            if not os.getenv(comm_type):
                logger.debug(f"Alerting undefined or empty: {os.getenv(comm_type)}. Return {Alerting.UNDEFINED}")
                return Alerting.UNDEFINED

            return Alerting[os.getenv(comm_type)]

        except KeyError:
            logger.warning(f"Alerting not defined properly: {os.getenv(comm_type)}")
            return Alerting.UNDEFINED

        except Exception as err:
            logger.error(err)
            raise

    @staticmethod
    def __determine_receiver(comm_type: str) -> Enum:
        try:
            logger.debug(f"Defined receiver: {os.getenv(comm_type)}")

            if not os.getenv(comm_type):
                logger.debug(f"Receiver undefined or empty: {os.getenv(comm_type)}. Return {Receiver.UNDEFINED}")
                return Receiver.UNDEFINED

            return Receiver[os.getenv(comm_type)]

        except KeyError:
            logger.error(f"CHAT_SERVICE={os.getenv(comm_type)} unknown. Return {Receiver.UNDEFINED}")

            return Receiver.UNDEFINED

        except Exception as err:
            logger.error(err)
            raise

    def __send_message(self, receiver: Enum):
        if receiver == Receiver.SLACK:
            Slack().post_message(self.msg)

        elif receiver == Receiver.MQTT:
            mqtt_msg = Builder.build_mqtt_msg(self.container)

            mqtt_topic = Builder.build_mqtt_topic(self.container)

            if MQTT(mqtt_topic, mqtt_msg).send_msg():
                logger.info("MQTT message sent successfully.")
            else:
                logger.warning("Error occurred while sending MQTT message")
        else:
            logger.error(f"Receiver '{os.getenv('CHAT_SERVICE')}' not implemented yet.")

    @staticmethod
    def __need_alerting(alerting: Enum) -> bool:
        if alerting in (Alerting.NEVER, Alerting.UNDEFINED):
            logger.debug("No alerting defined. Nothing to post.")
            return False
        if alerting == Alerting.ON_FAILURE:
            if not cfg.hasError:
                logger.debug("No errors occurred. Nothing to post.")
                return False
        if alerting == Alerting.ALWAYS:
            pass

        return True

    def notify_chat_receiver(self):
        if not self.__need_alerting(self.alerting):
            logger.debug(f"Chat message not needed. Config: {self.alerting.name}")
            return

        logger.debug(f"ready to build the chat message")

        self.msg = Builder.build_chat_message(self.container)

        logger.debug(f"post message to chat tool: {self.msg[:100]}...")
        self.__send_message(self.receiver)

    def notify_mqtt_receiver(self):
        if not self.__need_alerting(self.mqtt_alerting):
            logger.debug(f"MQTT message not needed. Config: {self.mqtt_alerting.name}")
            return

        logger.debug(f"ready to build the communication message")

        self.__send_message(Receiver.MQTT)

from enum import Enum

from notification.builder import Builder


class Dispatcher:
    def __init__(self, receiver: Enum, orig_msg: str, mqtt=True):
        self.receiver = receiver
        self.original_msg = orig_msg
        self.msg = ""
        self.mqtt_msg = ""
        self.send_mqtt = mqtt

    def __send_message(self):
        match self.receiver:
            case Receiver.SLACK:
                print("Foo")
            case _:
                print("Foobar")

    def __send_mqtt_message(self):
        print("Bar")

    def notify_receiver(self):

        self.msg = Builder.build_info_msg(self.original_msg)

        if self.send_mqtt:
            self.__send_mqtt_message()
        print("Baz")


class Receiver(Enum):
    SLACK = 1
    MQTT = 99

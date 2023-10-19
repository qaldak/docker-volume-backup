import json
from datetime import time

from util.accessor import LocalHost


class Builder:

    @staticmethod
    def build_info_msg(orig_err: str) -> str:
        print(orig_err)
        return "Info Msg: Foo"

    @staticmethod
    def build_mqtt_msg(orig_err: str):
        print(orig_err)
        print("Bar")
        value = {
            "time": int(time.time()),
            "container": "xyz",
            "msg": orig_err
        }
        print(json.dumps(value))
        return "Mqtt Msg: Foo"

    @staticmethod
    def build_mqtt_topic(container) -> str:
        topic = f"apps/{LocalHost.get_hostname_upper()}/{container.name}/backup/error/"
        print(topic)
        return topic

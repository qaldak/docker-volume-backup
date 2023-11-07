from unittest import TestCase
from unittest.mock import patch

from notification.builder import Builder
from util import cfg


class MockContainer(TestCase):
    def __init__(self) -> None:
        super().__init__()
        self.name = "foo_bar"


class TestBuilder(TestCase):

    @patch("src.notification.builder.LocalHost.get_hostname", return_value="foo")
    def test_build_chat_message_error(self, host):
        container = MockContainer()
        cfg.hasError = True
        cfg.errorMsg = "Error occurred for tests only."

        msg = Builder.build_chat_message(container.name)
        self.assertEqual("[foo] An error occurred while backing up container 'foo_bar'"
                         "\nError: Error occurred for tests only.\nCheck log file for more details.", msg,
                         "Invalid chat message (error)")

    @patch("src.notification.builder.LocalHost.get_hostname", return_value="foo")
    def test_build_chat_message_success(self, host):
        container = MockContainer()
        cfg.hasError = False

        msg = Builder.build_chat_message(container.name)
        self.assertEqual("[foo] Volume backup of container 'foo_bar' successful", msg, "Invalid chat message (success)")

    @patch("src.notification.builder.LocalHost.get_hostname_upper", return_value="FOO")
    def test_build_mqtt_topic(self, host):
        container = MockContainer()
        topic = Builder.build_mqtt_topic(container)
        self.assertEqual("apps/FOO/foo_bar/backup/", topic, "Invalid MQTT topic")

    def test_build_mqtt_msg(self):
        mqtt_msg = Builder.build_mqtt_msg("Foo")
        self.assertEqual("Mqtt Msg: Foo", mqtt_msg, "Invalid MQTT message")

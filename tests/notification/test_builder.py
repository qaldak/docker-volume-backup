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

    @patch.dict("src.notification.dispatcher.os.environ",
                {"MQTT_TOPIC": "apps/{HOSTNAME}/{CONTAINER}/backup/"})
    @patch("src.notification.builder.LocalHost.get_hostname", return_value="Foo")
    def test_build_mqtt_topic_with_placeholders(self, host):
        container = MockContainer()
        topic = Builder.build_mqtt_topic(container)
        self.assertEqual("apps/FOO/foo_bar/backup/", topic, "Invalid MQTT topic")

    @patch.dict("src.notification.dispatcher.os.environ",
                {"MQTT_TOPIC": "apps/{HOSTNAME}/backup/"})
    @patch("src.notification.builder.LocalHost.get_hostname", return_value="Foo")
    def test_build_mqtt_topic_one_placeholder(self, host):
        container = MockContainer()
        topic = Builder.build_mqtt_topic(container)
        self.assertEqual("apps/FOO/backup/", topic, "Invalid MQTT topic")

    @patch.dict("src.notification.dispatcher.os.environ",
                {"MQTT_TOPIC": "apps/container/backup/"})
    @patch("src.notification.builder.LocalHost.get_hostname", return_value="Foo")
    def test_build_mqtt_topic_without_placeholders(self, host):
        container = MockContainer()
        topic = Builder.build_mqtt_topic(container)
        self.assertEqual("apps/container/backup/", topic, "Invalid MQTT topic")

    @patch.dict("src.notification.dispatcher.os.environ",
                {"MQTT_TOPIC": ""})
    @patch("src.notification.builder.LocalHost.get_hostname", return_value="Foo")
    def test_build_mqtt_topic_undefined(self, host):
        container = MockContainer()
        with self.assertRaises(ValueError) as err:
            topic = Builder.build_mqtt_topic(container)

        self.assertEqual("MQTT_TOPIC undefined in .env file", str(err.exception))

    @patch("src.notification.builder.time.time", return_value=4102398000)
    @patch("src.notification.builder.LocalHost.get_hostname", return_value="myHost")
    def test_build_mqtt_msg(self, host, time):
        cfg.job_start_time = 1924945200
        cfg.job_end_time = 1924952401

        mqtt_msg = Builder.build_mqtt_msg("Foo")
        self.assertEqual(
            {"time": 4102398000,
             "host": "myHost",
             "container": "Foo",
             "duration": "2:00:01",
             "hasError": False,
             "msg": "Docker volume backup successful"},
            mqtt_msg,
            "Invalid MQTT message object")

from unittest import TestCase
from unittest.mock import patch

from notification.builder import Builder


class TestBuilder(TestCase):

    @patch("src.notification.builder.LocalHost.get_hostname_upper", return_value="FOO")
    def test_build_mqtt_topic(self, host):
        topic = Builder.build_mqtt_topic()
        self.assertEqual(topic, "apps/FOO//backup/error/", "Invalid MQTT topic")

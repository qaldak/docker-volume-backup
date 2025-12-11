import os
import unittest
from unittest import TestCase
from unittest.mock import patch

from python_on_whales import DockerException

from docker_volume_backup.notification.mqtt import MQTT


class MockContainer(TestCase):
    @unittest.expectedFailure
    def __init__(self, uid=None, name=None) -> None:
        super().__init__()
        self.id = uid
        self.name = name


class TestMQTT(TestCase):
    @unittest.skipIf(os.getenv("GITHUB_ACTIONS") == "true", "Skip on Github")
    @patch("docker_volume_backup.notification.mqtt.docker.container.execute", return_value="Well done")
    @patch("docker_volume_backup.notification.mqtt.docker.container.list",
           return_value=[MockContainer(uid="abc1", name="my_mosquitto_container")])
    @patch("docker_volume_backup.notification.mqtt.MQTT.determine_mqtt_container", return_value="mock_container")
    @patch.dict("docker_volume_backup.notification.mqtt.os.environ",
                {"MQTT_BROKER": "my.mqtt.broker", "MQTT_PORT": "1883"})
    def test_send_msg_running_container(self, mock_container, mock_docker_container, mock_exists):
        self.assertTrue(MQTT("testing/topic", "my message from running container").send_msg(),
                        "Sending MQTT with running container failed")

    @patch("docker_volume_backup.notification.mqtt.docker.container.run", return_value="Well done")
    @patch("docker_volume_backup.notification.mqtt.docker.container.remove", return_value=None)
    @patch("docker_volume_backup.notification.mqtt.docker.container.exists", return_value=True)
    @patch("docker_volume_backup.notification.mqtt.docker.container.list",
           return_value=[MockContainer(uid="abc1", name="foo")])
    @patch.dict("docker_volume_backup.notification.mqtt.os.environ",
                {"MQTT_BROKER": "my.mqttbroker.home", "MQTT_PORT": "1883"})
    def test_send_msg_create_container(self, mock_container, mock_exists, mock_remove, mock_run):
        '''
        :param mock_container: there is no running mosquitto container available
        :param mock_exists: mock returns True, so existing container would be removed
        :param mock_remove: mock returns None (remove successful)
        :param mock_run: mock success
        :return: True: test successful
        '''
        with self.assertLogs("docker_volume_backup.notification.mqtt", level="DEBUG") as log:
            self.assertTrue(MQTT("testing/topic", "my message from new container").send_msg(),
                            "Sending MQTT with temp container failed")
            self.assertEqual(["DEBUG:docker_volume_backup.notification.mqtt:MQTT command: ['mosquitto_pub', '-h', "
                              "'my.mqttbroker.home', '-p', '1883', '-t', 'testing/topic', '-m', 'my message "
                              "from new container']",
                              "INFO:docker_volume_backup.notification.mqtt:No running mosquitto container found. Download image and create "
                              "a temporary container",
                              "DEBUG:docker_volume_backup.notification.mqtt:Remove existing container 'tmp-mosquitto'."],
                             log.output)

    @patch("docker_volume_backup.notification.mqtt.docker.container.remove", side_effect=DockerException(
        command_launched=["/usr/bin/docker container run --log-driver none --name tmp-mosquitto eclipse-mosquitto "
                          "mosquitto_pub -h my.mqttbroker.home -p 1883 -t testing/foo -m error occurred"],
        return_code=125))
    @patch("docker_volume_backup.notification.mqtt.docker.container.exists", return_value=True)
    @patch("docker_volume_backup.notification.mqtt.docker.container.list",
           return_value=[MockContainer(uid="abc1", name="foo")])
    @patch.dict("docker_volume_backup.notification.mqtt.os.environ",
                {"MQTT_BROKER": "my.mqttbroker.home", "MQTT_PORT": "1883"})
    def test_send_msg_error_remove_temp_container(self, mock_container, mock_exists, mock_remove):
        # with self.assertLogs("notification.mqtt", level="DEBUG") as log:
        with self.assertLogs("docker_volume_backup.notification.mqtt", level="ERROR") as log:
            self.assertFalse(MQTT("testing/topic", "error occurred").send_msg(), "Error while remove temp container")
            self.assertIn("ERROR:docker_volume_backup.notification.mqtt:Error occurred while sending MQTT message.",
                          str(log.output))
            self.assertIn("/usr/bin/docker container run --log-driver none --name tmp-mosquitto eclipse-mosquitto "
                          "mosquitto_pub -h my.mqttbroker.home -p 1883 -t testing/foo -m error occurred",
                          str(log.output))

    @patch("docker_volume_backup.notification.mqtt.docker.container.run", side_effect=DockerException(
        command_launched=["/usr/bin/docker container run --log-driver none --name tmp-mosquitto eclipse-mosquitto "
                          "mosquitto_pub -h None -p 1883 -t testing/foo -m error occurred"],
        return_code=115))
    @patch("docker_volume_backup.notification.mqtt.docker.container.exists", return_value=False)
    @patch("docker_volume_backup.notification.mqtt.docker.container.list",
           return_value=[MockContainer(uid="abc1", name="foo")])
    @patch.dict("docker_volume_backup.notification.mqtt.os.environ",
                {"MQTT_BROKER": "my.mqttbroker.home", "MQTT_PORT": "1883"})
    def test_send_msg_error_with_temp_container(self, mock_container, mock_exists, mock_remove):
        with self.assertLogs("docker_volume_backup.notification.mqtt", level="ERROR") as log:
            self.assertFalse(MQTT("testing/topic", "error occurred").send_msg(), "Error while remove temp container")
            self.assertIn("ERROR:docker_volume_backup.notification.mqtt:Error occurred while sending MQTT message.",
                          str(log.output))
            self.assertIn("It returned with code 115", str(log.output))

    @patch("docker_volume_backup.notification.mqtt.docker.container.list",
           return_value=[MockContainer(uid="abc1", name="foo"),
                         MockContainer(uid="abc2", name="my_mosquitto_container")])
    def test_determine_mqtt_container_mosquitto(self, mock_list):
        mqtt_container = MQTT("foo", "bar").determine_mqtt_container()
        self.assertEqual("my_mosquitto_container", mqtt_container, "Mosquitto container not found, but expected.")

    @patch("docker_volume_backup.notification.mqtt.docker.container.list",
           return_value=[MockContainer(uid="abc1", name="mqtt"),
                         MockContainer(uid="abc2", name="my_mosquitto_container")])
    def test_determine_mqtt_container_mqtt(self, mock_list):
        mqtt_container = MQTT("foo", "bar").determine_mqtt_container()
        self.assertEqual("mqtt", mqtt_container, "MQTT container not found, but expected.")

    @patch("docker_volume_backup.notification.mqtt.docker.container.list",
           return_value=[MockContainer(uid="abc1", name="ttqm"), MockContainer(uid="abc2", name="mojito")])
    def test_determine_mqtt_container_notfound(self, mock_list):
        mqtt_container = MQTT("foo", "bar").determine_mqtt_container()
        self.assertEqual("", mqtt_container, "Container found, but not expected.")

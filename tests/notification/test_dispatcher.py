import json
from unittest import TestCase
from unittest.mock import patch

from docker_volume_backup.notification.dispatcher import Dispatcher
from docker_volume_backup.util import cfg
from docker_volume_backup.util.accessor import Alerting, Receiver


class TestDispatcher(TestCase):
    @patch.dict("docker_volume_backup.notification.dispatcher.os.environ",
                {"CHAT_ALERTING": "FOO", "CHAT_SERVICE": "MESSENGER", "COMM_ALERTING": ""})
    def test_dispatcher_init_env_undefined(self):
        dispatcher = Dispatcher("Foo")
        self.assertEqual(dispatcher.alerting, Alerting.UNDEFINED)
        self.assertEqual(dispatcher.receiver, Receiver.UNDEFINED)
        self.assertEqual(dispatcher.container, "Foo")

    @patch.dict("docker_volume_backup.notification.dispatcher.os.environ",
                {"CHAT_ALERTING": "ALWAYS", "CHAT_SERVICE": "SLACK"})
    def test_dispatcher_init_env_successful(self):
        dispatcher = Dispatcher("Foo")
        self.assertEqual(Alerting.ALWAYS, dispatcher.alerting)
        self.assertEqual(Receiver.SLACK, dispatcher.receiver)
        self.assertEqual("Foo", dispatcher.container)

    @patch.dict("docker_volume_backup.notification.dispatcher.os.environ",
                {"CHAT_ALERTING": "NEVER", "CHAT_SERVICE": "SLACK", "COMM_ALERTING": "NEVER"})
    @patch("docker_volume_backup.notification.dispatcher.Builder.build_chat_message", return_value="Foo")
    def test_dispatcher_notify_receiver_unknown(self, msg):
        Dispatcher("Foo").notify_chat_receiver()
        self.assertEqual("", Dispatcher("Foo").msg)  # Todo: check

    @patch.dict("docker_volume_backup.notification.dispatcher.os.environ",
                {"CHAT_ALERTING": "ON_FAILURE", "CHAT_SERVICE": "SLACK", "COMM_ALERTING": "NEVER"})
    @patch("docker_volume_backup.notification.dispatcher.Builder.build_chat_message", return_value="Bar")
    def test_dispatcher_notify_receiver_onfailure_noerror(self, msg):
        cfg.hasError = False
        Dispatcher("Foo").notify_chat_receiver()
        self.assertEqual("", Dispatcher("Foo").msg)  # Todo: check

    @patch.dict("docker_volume_backup.notification.dispatcher.os.environ",
                {"CHAT_ALERTING": "ON_FAILURE", "CHAT_SERVICE": "SLACK", "COMM_ALERTING": "NEVER"})
    @patch("docker_volume_backup.notification.dispatcher.Builder.build_chat_message", return_value="Foobar")
    @patch("docker_volume_backup.notification.dispatcher.Slack.post_message", return_value="")
    def test_dispatcher_notify_receiver_slack_onfailure(self, msg, post):
        cfg.hasError = True
        dispatcher = Dispatcher("Foo")
        with self.assertLogs("docker_volume_backup.notification.dispatcher", level="DEBUG") as log:
            dispatcher.notify_chat_receiver()
            self.assertEqual(
                ["DEBUG:docker_volume_backup.notification.dispatcher:ready to build the chat message",
                 "DEBUG:docker_volume_backup.notification.dispatcher:post message to chat tool: Foobar..."],
                log.output)

    @patch.dict("docker_volume_backup.notification.dispatcher.os.environ",
                {"CHAT_ALERTING": "ON_FAILURE", "CHAT_SERVICE": "SIGNAL", "COMM_ALERTING": "NEVER"})
    @patch("docker_volume_backup.notification.dispatcher.Builder.build_chat_message", return_value="Foobar")
    def test_dispatcher_notify_receiver_onfailure(self, msg):
        cfg.hasError = True
        dispatcher = Dispatcher("Foo")
        with self.assertLogs("docker_volume_backup.notification.dispatcher", level="DEBUG") as log:
            dispatcher.notify_chat_receiver()
            self.assertEqual("Foobar", dispatcher.msg)
            self.assertEqual(
                ["DEBUG:docker_volume_backup.notification.dispatcher:ready to build the chat message",
                 "DEBUG:docker_volume_backup.notification.dispatcher:post message to chat tool: Foobar...",
                 "ERROR:docker_volume_backup.notification.dispatcher:Receiver 'SIGNAL' not implemented yet."],
                log.output)


class TestDispatcherMqttPayload(TestCase):
    """the message of a backup run arrives at the MQTT broker as valid JSON (real Dispatcher, Builder and MQTT)"""

    def setUp(self):
        self._saved = {name: getattr(cfg, name) for name in
                       ("hasError", "errorMsg", "backup_file", "backup_size", "job_start_time", "job_end_time")}
        self.addCleanup(lambda: [setattr(cfg, name, value) for name, value in self._saved.items()])

    def _published(self):
        """:return: arguments of the mosquitto_pub command that was sent"""
        env = {"MQTT_ALERTING": "ALWAYS", "MQTT_BROKER": "my.mqttbroker.home", "MQTT_PORT": "1883",
               "MQTT_TOPIC": "apps/{HOSTNAME}/{CONTAINER}/volume_backup"}

        with patch.dict("docker_volume_backup.notification.dispatcher.os.environ", env, clear=True), \
                patch.dict("docker_volume_backup.notification.mqtt.os.environ", env, clear=True), \
                patch("docker_volume_backup.notification.mqtt.MQTT.determine_mqtt_container", return_value=""), \
                patch("docker_volume_backup.notification.mqtt.docker.container.exists", return_value=False), \
                patch("docker_volume_backup.notification.builder.LocalHost.get_hostname", return_value="myhost"), \
                patch("docker_volume_backup.notification.mqtt.docker.container.run") as run:
            Dispatcher("foo_bar").notify_mqtt_receiver()

        return run.call_args.kwargs["command"]

    def test_successful_backup(self):
        cfg.hasError = False
        cfg.backup_file = "myhost-foo_bar-volume-backup.tar.gz"
        cfg.backup_size = 4711
        cfg.job_start_time, cfg.job_end_time = 1000, 1005

        command = self._published()
        payload = json.loads(command[-1])

        self.assertEqual("apps/MYHOST/foo_bar/volume_backup", command[command.index("-t") + 1])
        self.assertEqual("foo_bar", payload["container"])
        self.assertIs(False, payload["hasError"])
        self.assertEqual(4711, payload["backupSize"])
        self.assertEqual("0:00:05", payload["duration"])
        self.assertEqual("Docker volume backup successful", payload["msg"])

    def test_failed_backup_with_exception(self):
        cfg.hasError = True
        cfg.errorMsg = FileNotFoundError(2, "No such file or directory: '/backup/foo \"bar\".tar.gz'")
        cfg.backup_file = ""
        cfg.backup_size = None
        cfg.job_start_time, cfg.job_end_time = 1000, 1001

        payload = json.loads(self._published()[-1])

        self.assertIs(True, payload["hasError"])
        self.assertIsNone(payload["backupSize"])
        self.assertIn('/backup/foo "bar".tar.gz', payload["msg"])

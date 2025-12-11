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

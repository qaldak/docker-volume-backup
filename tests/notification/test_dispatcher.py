from unittest import TestCase
from unittest.mock import patch

from notification.dispatcher import Dispatcher, Alerting, Receiver
from util import cfg


class TestDispatcher(TestCase):
    @patch.dict("src.notification.dispatcher.os.environ",
                {"CHAT_ALERTING": "FOO", "CHAT_SERVICE": "MESSANGER", "MQTT_NOTIFICATION": ""})
    def test_dispatcher_init_env_undefined(self):
        dispatcher = Dispatcher("Foo")
        self.assertEqual(dispatcher.alerting, Alerting.UNDEFINED)
        self.assertEqual(dispatcher.receiver, Receiver.UNDEFINED)
        self.assertFalse(dispatcher.send_mqtt)
        self.assertEqual(dispatcher.container, "Foo")

    @patch.dict("src.notification.dispatcher.os.environ",
                {"CHAT_ALERTING": "ALWAYS", "CHAT_SERVICE": "SLACK", "MQTT_NOTIFICATION": "True"})
    def test_dispatcher_init_env_successful(self):
        dispatcher = Dispatcher("Foo")
        self.assertEqual(Alerting.ALWAYS, dispatcher.alerting)
        self.assertEqual(Receiver.SLACK, dispatcher.receiver)
        self.assertTrue(dispatcher.send_mqtt)
        self.assertEqual("Foo", dispatcher.container)

    @patch.dict("src.notification.dispatcher.os.environ",
                {"CHAT_ALERTING": "NEVER", "CHAT_SERVICE": "SLACK", "MQTT_NOTIFICATION": "False"})
    @patch("src.notification.dispatcher.Builder.build_chat_message", return_value="Foobar")
    def test_dispatcher_notify_receiver_unknown(self, msg):
        Dispatcher("Foo").notify_receiver()
        self.assertEqual("", Dispatcher("Foo").msg)

    @patch.dict("src.notification.dispatcher.os.environ",
                {"CHAT_ALERTING": "ON_FAILURE", "CHAT_SERVICE": "SLACK", "MQTT_NOTIFICATION": "False"})
    @patch("src.notification.dispatcher.Builder.build_chat_message", return_value="Foobar")
    @patch("src.util.cfg.hasError", return_value=False)
    def test_dispatcher_notify_receiver_onfailure_noerror(self, msg, has_error):
        Dispatcher("Foo").notify_receiver()
        self.assertEqual("", Dispatcher("Foo").msg)

    @patch.dict("src.notification.dispatcher.os.environ",
                {"CHAT_ALERTING": "ON_FAILURE", "CHAT_SERVICE": "SIGNAL", "MQTT_NOTIFICATION": "False"})
    @patch("src.notification.dispatcher.Builder.build_chat_message", return_value="Foobar")
    def test_dispatcher_notify_receiver_onfailure(self, msg):
        cfg.hasError = True
        dispatcher = Dispatcher("Foo")
        with self.assertLogs("notification.dispatcher", level="DEBUG") as log:
            dispatcher.notify_receiver()
            self.assertEqual("Foobar", dispatcher.msg)
            self.assertEqual(
                ["DEBUG:notification.dispatcher:ready to build the chat message",
                 "DEBUG:notification.dispatcher:post message to chat tool: Foobar...",
                 "ERROR:notification.dispatcher:Receiver 'UNDEFINED' not implemented yet."],
                log.output)

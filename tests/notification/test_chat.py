from unittest import TestCase
from unittest.mock import patch

from slack_sdk.errors import SlackApiError

from notification.chat import Slack


class TestSlack(TestCase):

    @patch("src.notification.chat.WebClient.chat_postMessage", return_value={'ok': True}, side_effect=None)
    def test_post_message_successful(self, res):
        with self.assertLogs("notification.chat", level="INFO") as log:
            self.assertIsNone(Slack().post_message("Foobar"))
            self.assertEqual(
                ["INFO:notification.chat:Message sent successfully"],
                log.output)

    @patch("src.notification.chat.WebClient.chat_postMessage",
           side_effect=SlackApiError("auth failed", {'ok': False}))
    def test_post_message_failed(self, res):
        with self.assertLogs("notification.chat", level="ERROR") as log:
            Slack().post_message("Foobar")
            self.assertRaises(SlackApiError)
            self.assertEqual(
                ["ERROR:notification.chat:auth failed\n" "The server responded with: {'ok': False}"],
                log.output)

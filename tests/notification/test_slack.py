from unittest import TestCase
from unittest.mock import patch

from slack_sdk.errors import SlackApiError

from notification.slack import Slack


class TestSlack(TestCase):

    @patch("src.notification.slack.WebClient.chat_postMessage", return_value={'ok': True}, side_effect=None)
    def test_post_message_successful(self, res):
        with self.assertLogs("notification.slack", level="INFO") as log:
            self.assertIsNone(Slack().post_message("Foobar"))
            self.assertEqual(
                ["INFO:notification.slack:Message sent successfully"],
                log.output)

    @patch("src.notification.slack.WebClient.chat_postMessage",
           side_effect=SlackApiError("The request to the Slack API failed.",
                                     {'ok': False, 'error': 'channel_not_found'}))
    def test_post_message_failed(self, res):
        with self.assertLogs("notification.slack", level="ERROR") as log:
            Slack().post_message("Foobar")
            self.assertRaises(SlackApiError)
            self.assertEqual(
                [
                    "ERROR:notification.slack:The request to the Slack API failed.\n"
                    "The server responded with: {'ok': False, 'error': 'channel_not_found'}"],
                log.output)

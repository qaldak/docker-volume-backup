from unittest import TestCase
from unittest.mock import patch

from notification.chat import Slack


class TestSlack(TestCase):

    @patch("src.notification.chat.WebClient.chat_postMessage", return_value={'ok': True})
    def test_post_message_successful(self, res):
        self.assertIsNone(Slack().post_message("Foobar"))

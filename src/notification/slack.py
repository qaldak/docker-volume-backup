import logging
import os

from dotenv import load_dotenv
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

from util import cfg

logger = logging.getLogger(__name__)


class Slack:
    """
    Initialize Slack to post message to a defined channel.
    Following params need to be defined in .env file:
    'SLACK_CHANNEL_ID' and 'SLACK_AUTH_TOKEN'
    """

    def __init__(self):
        load_dotenv()
        self.auth_token = os.getenv("SLACK_AUTH_TOKEN")
        self.channel = os.getenv("SLACK_CHANNEL_ID")
        self.client = WebClient(token=self.auth_token)
        self.emoji = ":exclamation:" if cfg.hasError else ""

    def post_message(self, msg):
        """
        Post message to defined Slack channel

        :param msg: message to send
        """
        try:
            response = self.client.chat_postMessage(
                channel=self.channel,
                text=f"{self.emoji}{msg}"
            )

            if response["ok"]:
                logger.info(f"Message sent successfully")

            logger.debug(f"{str(response)[1:66]} ...")

        except SlackApiError as err:
            logger.error(err)
            cfg.hasError = True

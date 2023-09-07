from unittest import TestCase
from unittest.mock import patch

from docker.container import Container


class TestContainer(TestCase):

    @patch("src.docker.container.docker.container.exists", return_value=True)
    def test_container_valid(self, mock_container_state):
        self.assertTrue(Container.validate_container_exists('Container'), "Container not exist! Expected: 'True'")

    def test_container_not_valid(self):
        self.assertFalse(Container.validate_container_exists('Container'), "Container not exist! Expected: 'False'")

from unittest import TestCase
from unittest.mock import patch

from docker.container import Container


class TestContainer(TestCase):

    @patch("src.container.container.container.container.exists", return_value=True)
    def test_container_valid(self, mock_container_state):
        container = Container("Foo")
        self.assertTrue(container.exists(), "Container not exist! Expected: 'True'")

    def test_container_not_valid(self):
        container = Container("Foo")
        self.assertFalse(container.exists(), "Container not exist! Expected: 'False'")

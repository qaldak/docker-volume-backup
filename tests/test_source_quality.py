import ast
import pathlib
import warnings
from unittest import TestCase

import docker_volume_backup

SOURCE_DIR = pathlib.Path(docker_volume_backup.__file__).parent
LOG_METHODS = ("debug", "info", "warning", "error", "exception", "critical")


class TestSourceFiles(TestCase):

    def test_source_files_compile_without_warnings(self):
        """e.g. an invalid escape sequence in a string prints a warning on stderr (cron mail) when compiled"""
        for source_file in SOURCE_DIR.rglob("*.py"):
            with self.subTest(file=source_file.name), warnings.catch_warnings():
                warnings.simplefilter("error")
                compile(source_file.read_text(), str(source_file), "exec")

    def test_logger_calls_have_no_stray_arguments(self):
        """logger.error("message", err) without a %s placeholder breaks the log record (error on stderr)"""
        for source_file in SOURCE_DIR.rglob("*.py"):
            tree = ast.parse(source_file.read_text())

            for node in ast.walk(tree):
                if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                        and node.func.attr in LOG_METHODS and isinstance(node.func.value, ast.Name)
                        and node.func.value.id == "logger" and len(node.args) > 1):
                    continue

                message = node.args[0]
                has_placeholder = (isinstance(message, ast.Constant) and "%" in str(message.value)) or \
                                  any(isinstance(part, ast.Constant) and "%" in str(part.value)
                                      for part in ast.walk(message))

                with self.subTest(file=source_file.name, line=node.lineno):
                    self.assertTrue(has_placeholder, f"{source_file.name}:{node.lineno}: logger call with extra "
                                                     f"argument but no placeholder in the message")

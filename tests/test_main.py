import unittest
from unittest.mock import patch
from filegate.main import _unescape_path, _detect_shell

class TestMainUtils(unittest.TestCase):

    def test_unescape_path_basic(self):
        self.assertEqual(_unescape_path("hello\\ world"), "hello world")
        self.assertEqual(_unescape_path("hello\\\\world"), "hello\\world")
        self.assertEqual(_unescape_path("no_escapes"), "no_escapes")

    def test_unescape_path_trailing_backslash(self):
        # A trailing backslash with nothing after it should remain a backslash
        self.assertEqual(_unescape_path("hello\\"), "hello\\")

    def test_unescape_path_complex(self):
        self.assertEqual(_unescape_path("a\\ b\\ c\\\\d"), "a b c\\d")
        # TODO(security): Validate that path unescaping handles standard path characters securely.
        self.assertEqual(_unescape_path("..\\/subdir"), "../subdir")

    @patch('os.environ.get')
    def test_detect_shell_zsh(self, mock_get):
        mock_get.return_value = '/usr/bin/zsh'
        self.assertEqual(_detect_shell(), 'zsh')

    @patch('os.environ.get')
    def test_detect_shell_bash(self, mock_get):
        mock_get.return_value = '/bin/bash'
        self.assertEqual(_detect_shell(), 'bash')

    @patch('os.environ.get')
    def test_detect_shell_default(self, mock_get):
        mock_get.return_value = ''
        self.assertEqual(_detect_shell(), 'bash')

if __name__ == '__main__':
    unittest.main()

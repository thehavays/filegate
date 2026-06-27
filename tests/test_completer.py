import unittest
import tempfile
import shutil
import os
from pathlib import Path

from filegate.completer import RemoteCompleter, LocalCompleter, generate_bash_completion, generate_zsh_completion
from filegate.protocols.base import BaseServer, FSEntry, EntryType

class MockServer(BaseServer):
    def __init__(self):
        # Pass a dummy config to the BaseServer initializer
        super().__init__({'host': 'localhost', 'user': 'test'})
        self.dirs = {
            '/': [
                FSEntry('docs', '/docs', EntryType.DIR),
                FSEntry('file.txt', '/file.txt', EntryType.FILE),
            ],
            '/docs': [
                FSEntry('report.pdf', '/docs/report.pdf', EntryType.FILE),
                FSEntry('notes', '/docs/notes', EntryType.DIR),
            ]
        }

    def connect(self, password=None):
        self._connected = True

    def disconnect(self):
        self._connected = False

    def listdir(self, directory):
        if directory in self.dirs:
            return self.dirs[directory]
        raise Exception("Directory not found")

    def exists(self, path):
        return True

    def isdir(self, path):
        return path in self.dirs or path == '/'

    def home(self):
        return '/'

    def mkdir(self, path):
        pass

    def get_size(self, path):
        return 0

    def pull(self, remote_path, local_path, progress=None):
        pass

    def push(self, local_path, remote_path, progress=None):
        pass

    def open_file(self, path, mode='rb'):
        pass


class TestCompleter(unittest.TestCase):
    def setUp(self):
        self.mock_server = MockServer()
        self.remote_completer = RemoteCompleter(self.mock_server)
        
        # Local completer temp filesystem setup
        self.temp_dir = tempfile.mkdtemp()
        self.temp_path = Path(self.temp_dir)
        
        # Create temp files/folders
        self.sub_dir = self.temp_path / 'subdir'
        self.sub_dir.mkdir()
        self.file1 = self.temp_path / 'file1.txt'
        self.file1.touch()
        self.file2 = self.temp_path / 'file2.log'
        self.file2.touch()
        
        self.local_completer = LocalCompleter()

    def tearDown(self):
        shutil.rmtree(self.temp_dir)

    def test_remote_completer_matching(self):
        # Match directory at root
        matches = self.remote_completer._build_matches('/d')
        self.assertEqual(matches, ['/docs/'])
        
        # Match file at root
        matches = self.remote_completer._build_matches('/f')
        self.assertEqual(matches, ['/file.txt'])
        
        # Match nested file
        matches = self.remote_completer._build_matches('/docs/re')
        self.assertEqual(matches, ['/docs/report.pdf'])
        
        # Match nested directory
        matches = self.remote_completer._build_matches('/docs/no')
        self.assertEqual(matches, ['/docs/notes/'])

    def test_remote_completer_readline_interface(self):
        # Test state 0 initializes matches and returns first match
        first = self.remote_completer.complete('/d', 0)
        self.assertEqual(first, '/docs/')
        
        # Test state 1 returns None (no more matches)
        second = self.remote_completer.complete('/d', 1)
        self.assertIsNone(second)

    def test_local_completer_matching(self):
        # Match files inside temp directory
        prefix = os.path.join(self.temp_dir, 'file')
        first = self.local_completer.complete(prefix, 0)
        # Sort candidates check: file1.txt should come before file2.log
        self.assertEqual(first, os.path.join(self.temp_dir, 'file1.txt'))
        
        second = self.local_completer.complete(prefix, 1)
        self.assertEqual(second, os.path.join(self.temp_dir, 'file2.log'))
        
        third = self.local_completer.complete(prefix, 2)
        self.assertIsNone(third)

    def test_local_completer_directory_trailing_slash(self):
        # Match directory inside temp directory
        prefix = os.path.join(self.temp_dir, 'sub')
        first = self.local_completer.complete(prefix, 0)
        # Should append a trailing slash since it's a directory
        self.assertEqual(first, os.path.join(self.temp_dir, 'subdir') + '/')

    def test_completion_generators(self):
        bash_script = generate_bash_completion()
        zsh_script = generate_zsh_completion()
        
        self.assertTrue(isinstance(bash_script, str))
        self.assertTrue(len(bash_script) > 0)
        self.assertIn('_filegate_complete', bash_script)
        
        self.assertTrue(isinstance(zsh_script, str))
        self.assertTrue(len(zsh_script) > 0)
        self.assertIn('_filegate_subcommands', zsh_script)

if __name__ == '__main__':
    unittest.main()

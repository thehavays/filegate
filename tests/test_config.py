import unittest
from unittest.mock import patch, MagicMock
import tempfile
import shutil
from pathlib import Path
import json

import filegate.config as cfg

class TestConfig(unittest.TestCase):
    def setUp(self):
        # Create a temporary directory
        self.test_dir = tempfile.mkdtemp()
        self.test_path = Path(self.test_dir)
        
        # Save original config paths
        self.orig_config_dir = cfg.CONFIG_DIR
        self.orig_config_file = cfg.CONFIG_FILE
        self.orig_key_file = cfg.KEY_FILE
        self.orig_secrets_file = cfg.SECRETS_FILE
        
        # Override with temp paths
        cfg.CONFIG_DIR = self.test_path
        cfg.CONFIG_FILE = self.test_path / 'servers.json'
        cfg.KEY_FILE = self.test_path / 'key'
        cfg.SECRETS_FILE = self.test_path / 'secrets.enc'
        
        # Mock keyring storage
        self.mock_keyring_store = {}

    def tearDown(self):
        # Restore original paths
        cfg.CONFIG_DIR = self.orig_config_dir
        cfg.CONFIG_FILE = self.orig_config_file
        cfg.KEY_FILE = self.orig_key_file
        cfg.SECRETS_FILE = self.orig_secrets_file
        
        # Clean up temporary directory
        shutil.rmtree(self.test_dir)

    def test_default_port(self):
        self.assertEqual(cfg.default_port('sftp'), 22)
        self.assertEqual(cfg.default_port('ftp'), 21)
        self.assertEqual(cfg.default_port('smb'), 445)
        self.assertEqual(cfg.default_port('unknown_protocol'), 22)

    def test_add_and_get_servers(self):
        # Starts empty
        self.assertEqual(cfg.get_servers(), {})
        self.assertIsNone(cfg.get_server('myserver'))
        self.assertEqual(cfg.server_names(), [])
        
        # Add server
        srv_config = {'host': '1.2.3.4', 'user': 'admin', 'protocol': 'sftp'}
        cfg.add_server('myserver', srv_config)
        
        self.assertEqual(cfg.server_names(), ['myserver'])
        self.assertEqual(cfg.get_server('myserver'), srv_config)
        self.assertEqual(cfg.get_servers(), {'myserver': srv_config})

    def test_remove_server(self):
        srv_config = {'host': '1.2.3.4', 'user': 'admin'}
        cfg.add_server('myserver', srv_config)
        self.assertTrue(cfg.remove_server('myserver'))
        self.assertIsNone(cfg.get_server('myserver'))
        self.assertFalse(cfg.remove_server('myserver'))

    @patch('keyring.get_password')
    @patch('keyring.set_password')
    @patch('keyring.delete_password')
    @patch('keyring.get_keyring')
    def test_password_storage_keyring_success(self, mock_get_keyring, mock_del, mock_set, mock_get):
        # Mock active keyring
        mock_get_keyring.return_value = MagicMock() # not fail.Keyring
        
        def mock_get_pwd(service, name):
            return self.mock_keyring_store.get((service, name))
            
        def mock_set_pwd(service, name, pwd):
            self.mock_keyring_store[(service, name)] = pwd
            
        def mock_del_pwd(service, name):
            self.mock_keyring_store.pop((service, name), None)
            
        mock_get.side_effect = mock_get_pwd
        mock_set.side_effect = mock_set_pwd
        mock_del.side_effect = mock_del_pwd
        
        cfg.set_password('myserver', 'super_secret')
        self.assertEqual(cfg.get_password('myserver'), 'super_secret')
        self.assertEqual(self.mock_keyring_store[(cfg.KEYRING_SERVICE, 'myserver')], 'super_secret')
        
        # Verify secrets.enc was NOT created because keyring succeeded
        self.assertFalse(cfg.SECRETS_FILE.exists())
        
        # Remove server clears the password
        cfg.add_server('myserver', {'host': '1.2.3.4'})
        cfg.remove_server('myserver')
        self.assertIsNone(cfg.get_password('myserver'))

    @patch('keyring.get_keyring')
    @patch('keyring.get_password')
    @patch('keyring.set_password')
    def test_password_storage_keyring_fallback(self, mock_set_pwd, mock_get_pwd, mock_get_keyring):
        mock_get_keyring.side_effect = Exception("Keyring unavailable")
        mock_get_pwd.side_effect = Exception("Keyring unavailable")
        mock_set_pwd.side_effect = Exception("Keyring unavailable")
        
        # Set password
        cfg.set_password('myserver', 'local_secret')
        
        # Should be saved to SECRETS_FILE and encrypted
        self.assertTrue(cfg.SECRETS_FILE.exists())
        
        # Retrieve password
        retrieved = cfg.get_password('myserver')
        self.assertEqual(retrieved, 'local_secret')
        
        # Verify master key was created
        self.assertTrue(cfg.KEY_FILE.exists())
        
        # Clean up / remove
        cfg.add_server('myserver', {'host': '1.2.3.4'})
        cfg.remove_server('myserver')
        self.assertIsNone(cfg.get_password('myserver'))

    @patch('keyring.get_keyring')
    @patch('keyring.get_password')
    @patch('keyring.set_password')
    def test_password_master_key_env_var(self, mock_set_pwd, mock_get_pwd, mock_get_keyring):
        mock_get_keyring.side_effect = Exception("Keyring unavailable")
        mock_get_pwd.side_effect = Exception("Keyring unavailable")
        mock_set_pwd.side_effect = Exception("Keyring unavailable")
        
        # Set master password env var
        with patch.dict('os.environ', {'FILEGATE_MASTER_PASSWORD': 'mypassword'}):
            cfg.set_password('myserver', 'env_secret')
            
            # Retrieve password using the same master password env var
            retrieved = cfg.get_password('myserver')
            self.assertEqual(retrieved, 'env_secret')
            
            # Since env var is used, key file shouldn't be read or created
            self.assertFalse(cfg.KEY_FILE.exists())

if __name__ == '__main__':
    unittest.main()

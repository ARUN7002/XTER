import os
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.andrews.config import Settings


class SettingsTests(unittest.TestCase):
    def test_defaults_use_dedicated_data_root(self):
        with patch.dict(os.environ, {}, clear=True):
            settings = Settings.from_environment()
        self.assertEqual(settings.data_root, Path(r"E:\ANDREWS"))
        self.assertEqual(settings.log_level, "INFO")

    def test_invalid_log_level_is_rejected(self):
        with patch.dict(os.environ, {"ANDREWS_LOG_LEVEL": "TRACE"}, clear=True):
            with self.assertRaises(ValueError):
                Settings.from_environment()

    def test_required_directories_are_scoped_to_data_root(self):
        with patch.dict(os.environ, {"ANDREWS_DATA_ROOT": r"D:\ANDREWS"}, clear=True):
            settings = Settings.from_environment()
        self.assertIn(Path(r"D:\ANDREWS\guardian"), settings.required_directories())
        self.assertTrue(all(str(path).startswith(r"D:\ANDREWS") for path in settings.required_directories()))


if __name__ == "__main__":
    unittest.main()


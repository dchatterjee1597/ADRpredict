import subprocess
import sys
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]

class TestSmoke(unittest.TestCase):
    def _run_help(self, rel):
        p = subprocess.run([sys.executable, str(ROOT / rel), "--help"], capture_output=True, text=True)
        self.assertEqual(p.returncode, 0, msg=p.stderr)

    def test_scripts_help(self):
        for rel in [
            "scripts/download_sider.py",
            "scripts/import_drugbank.py",
            "scripts/build_catalog.py",
            "scripts/validate_raw_data.py",
        ]:
            self._run_help(rel)

if __name__ == "__main__":
    unittest.main()

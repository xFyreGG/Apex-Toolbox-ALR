import tempfile, unittest, sys
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import build_release

class ReleaseNamingTests(unittest.TestCase):
    def label(self, suffix):
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory)
            (folder/'__init__.py').write_text("bl_info = {'version': (3, 11, 0)}\nRELEASE_SUFFIX = " + repr(suffix))
            with patch.object(build_release, 'ADDON', folder):
                return build_release.release_label()
    def test_stable(self):
        self.assertEqual(self.label(''), '3.11.0')
    def test_beta(self):
        self.assertEqual(self.label('-beta.12'), '3.11.0-beta.12')
    def test_invalid(self):
        for suffix in ['-beta.0', '-beta.01', '-beta', '../file', '-rc.1', 1]:
            with self.subTest(suffix=suffix), self.assertRaises(ValueError): self.label(suffix)

if __name__ == '__main__': unittest.main()

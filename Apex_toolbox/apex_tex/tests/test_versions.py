import unittest
from apex_tex.versions import newer_version


class VersionsTest(unittest.TestCase):
    def test_multi_digit_release(self):
        self.assertTrue(newer_version('v3.10.0', 'v3.9.0'))
        self.assertFalse(newer_version('v3.9.0', 'v3.10.0'))

    def test_equivalent_short_version(self):
        self.assertFalse(newer_version('3.9', '3.9.0'))
        self.assertFalse(newer_version('3.9.0', 'v.3.9'))

    def test_prerelease_order(self):
        self.assertTrue(newer_version('3.9.0', '3.9.0-beta.2'))
        self.assertTrue(newer_version('3.9.0-rc1', '3.9.0-beta4'))
        self.assertTrue(newer_version('3.9.0-beta10', '3.9.0-beta9'))
        self.assertFalse(newer_version('3.9.0-beta1', '3.9.0'))

    def test_unrecognised_feed_is_ignored(self):
        for value in ('nightly', '', None, 'unexpected release title'):
            self.assertFalse(newer_version(value, '3.9'))

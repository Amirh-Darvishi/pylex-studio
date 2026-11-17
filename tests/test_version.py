"""Release-version consistency checks."""

import unittest

from pylex import __version__


class VersionTests(unittest.TestCase):
    def test_package_version_matches_the_2_6_release_line(self):
        self.assertEqual(__version__, "2.6.0")


if __name__ == "__main__":
    unittest.main()

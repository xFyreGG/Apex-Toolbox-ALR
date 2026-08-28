# -*- coding: utf-8 -*-
"""Standalone runner for the Auto_tex resolver tests.

    python Apex_toolbox/apex_tex/tests/run_tests.py

Blender is not required: only the ``bpy``-free modules are imported.  The
add-on's own ``__init__.py`` is deliberately *not* imported, so ``apex_tex`` is
put on ``sys.path`` as a top level package instead.
"""

import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ADDON_ROOT = os.path.dirname(os.path.dirname(HERE))   # .../Apex_toolbox
if ADDON_ROOT not in sys.path:
    sys.path.insert(0, ADDON_ROOT)


def main():
    loader = unittest.TestLoader()
    suite = loader.discover(start_dir=HERE, pattern="test_*.py",
                            top_level_dir=ADDON_ROOT)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())

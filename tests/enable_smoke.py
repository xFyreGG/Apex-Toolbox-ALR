"""Exercise Blender's add-on enable, disable and changed-on-disk reload path.

Run in a separate Blender with --factory-startup --python-exit-code 1.
Pass -- --ui to leave an isolated Preferences window open for visual inspection.
No preferences or project files are saved.
"""
from pathlib import Path
import sys
import time

import addon_utils
import bpy

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def raise_error():
    raise RuntimeError('Blender could not enable Apex Toolbox') from sys.exc_info()[1]


for attempt in range(3):
    if attempt:
        # Emulate replacing the ZIP while this Blender session is still open.
        sys.modules['Apex_toolbox'].__time__ = -1
    started = time.perf_counter()
    module = addon_utils.enable('Apex_toolbox', default_set=True, handle_error=raise_error)
    assert module is not None and module.__addon_enabled__
    assert bpy.context.preferences.addons.get('Apex_toolbox')
    assert hasattr(bpy.types.Scene, 'my_prefs')
    print('ENABLE %d PASSED in %.3f seconds' % (attempt + 1, time.perf_counter() - started), flush=True)
    if attempt != 2 or '--ui' not in sys.argv:
        addon_utils.disable('Apex_toolbox', default_set=True, handle_error=raise_error)
        assert not hasattr(bpy.types.Scene, 'my_prefs')

if '--ui' in sys.argv:
    bpy.context.preferences.active_section = 'ADDONS'
    bpy.context.window_manager.addon_search = 'Apex Toolbox'
    bpy.ops.screen.userpref_show()
else:
    print('ENABLE / DISABLE / CHANGED-ON-DISK RELOAD PASSED', flush=True)

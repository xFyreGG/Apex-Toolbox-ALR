# -*- coding: utf-8 -*-
"""Apex Toolbox texture resolution package.

Split out of the monolithic ``Apex_toolbox/__init__.py`` so that Auto_tex can
understand both the legacy Legion+ export convention and current RSX / CAST
exports, and so that the filename and path logic can be unit tested without
Blender.

Modules
-------
``roles``     canonical semantic roles and their name aliases (no ``bpy``)
``naming``    file name normalisation, role detection, family matching (no ``bpy``)
``paths``     cached, cross platform texture file discovery (no ``bpy``)
``resolver``  the shared, ranked resolution hierarchy (no ``bpy``)
``graph``     reads roles out of an imported material's node graph (``bpy``)
``shaders``   per-shader socket maps and material construction (``bpy``)
``autotex``   the operator body (``bpy``)
"""

#: Internal API revision of this package.
#:
#: ``Apex_toolbox/__init__.py`` checks this against the value it was written
#: for.  Blender reloads an add-on's top level module when it is re-enabled but
#: leaves submodules already in ``sys.modules`` alone, so installing a new
#: version over a running old one used to leave a new caller talking to an old
#: ``autotex.run``.  Bump this whenever the signatures the add-on calls change.
API_VERSION = 13

#: Reload order: dependencies before the modules that import them.
RELOAD_ORDER = (
    "roles", "naming", "paths", "roots", "shaders", "resolver", "graph",
    "autotex", "diagnostics", "health", "versions", "cast_index", "workflows", "animation_names", "animations", "attachments",
)

__all__ = [
    "roles", "naming", "paths", "roots", "resolver", "graph", "shaders",
    "autotex", "diagnostics", "health", "versions", "cast_index", "workflows", "animation_names", "animations", "attachments", "API_VERSION", "RELOAD_ORDER",
]
